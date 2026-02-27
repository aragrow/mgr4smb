"""
Resume Service - Handle interrupted conversation resumption

Provides capability to find and resume timed-out or interrupted conversations
from their last checkpoint.
"""

import logging
from datetime import datetime as dt
from typing import List, Optional, Dict, Any
from src.models.conversation_state import ConversationState
from src.workers.db_worker.conversation_state_repo import ConversationStateRepository
from src.services.conversation_state_manager import ConversationStateManager

logger = logging.getLogger(__name__)


class ResumeService:
    """
    Service for resuming interrupted conversations

    Handles finding resumable sessions and restoring their state
    for continued processing.

    Examples:
        service = ResumeService()

        # Find sessions that can be resumed
        resumable = await service.find_resumable_sessions(
            status="timeout",
            max_age_hours=24
        )

        # Resume a specific session
        result = await service.resume_session(session_id)
    """

    def __init__(self):
        """Initialize with repository and manager"""
        self.repo = ConversationStateRepository()
        self.manager = ConversationStateManager()

    async def find_resumable_sessions(
        self,
        status: Optional[str] = None,
        max_age_hours: int = 24,
        channel: Optional[str] = None
    ) -> List[ConversationState]:
        """
        Find conversation sessions that can be resumed

        Args:
            status: Filter by status ("timeout", "in_progress", or None for both)
            max_age_hours: Maximum age in hours (default 24)
            channel: Optional filter by channel (email/phone)

        Returns:
            List of resumable ConversationState objects
        """
        try:
            # Get incomplete sessions
            sessions = await self.repo.find_incomplete_sessions(max_age_hours=max_age_hours)

            # Filter by status if specified
            if status:
                sessions = [s for s in sessions if s.status == status]

            # Filter by channel if specified
            if channel:
                sessions = [s for s in sessions if s.channel == channel]

            logger.info(
                f"Found {len(sessions)} resumable sessions "
                f"(status={status or 'any'}, channel={channel or 'any'})"
            )

            return sessions

        except Exception as e:
            logger.error(f"Failed to find resumable sessions: {e}", exc_info=True)
            return []

    async def resume_session(
        self,
        session_id: str,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Resume a conversation session from its last checkpoint

        Args:
            session_id: Session UUID to resume
            force: Force resume even if not in resumable state (default False)

        Returns:
            Dictionary with resume result:
            {
                "success": bool,
                "session_id": str,
                "status": str,
                "checkpoint": dict,
                "next_action": str,
                "message": str
            }
        """
        try:
            # Get session
            session = await self.manager.get_session(session_id)
            if not session:
                logger.error(f"Session {session_id} not found")
                return {
                    "success": False,
                    "session_id": session_id,
                    "message": "Session not found"
                }

            # Check if resumable
            if not force and session.status not in ["timeout", "in_progress"]:
                logger.warning(f"Session {session_id} is {session.status}, not resumable")
                return {
                    "success": False,
                    "session_id": session_id,
                    "status": session.status,
                    "message": f"Session is {session.status}, cannot resume"
                }

            # Get last checkpoint
            if not session.last_checkpoint:
                logger.warning(f"Session {session_id} has no checkpoint")
                return {
                    "success": False,
                    "session_id": session_id,
                    "status": session.status,
                    "message": "No checkpoint available for resume"
                }

            checkpoint = session.last_checkpoint

            # Log resume event
            await self.manager.log_event(
                session_id=session_id,
                event_type="agent_routed",  # Treat resume as routing
                agent_name="resume_service",
                data={
                    "action": "resume",
                    "previous_status": session.status,
                    "checkpoint_timestamp": checkpoint.timestamp.isoformat() if checkpoint.timestamp else None,
                    "current_agent": checkpoint.current_agent,
                    "next_action": checkpoint.next_action
                }
            )

            # Update session status to in_progress
            session.status = "in_progress"
            session.timeout_at = None  # Clear timeout
            await self.repo.update(session)

            logger.info(
                f"Resumed session {session_id} from checkpoint "
                f"(agent: {checkpoint.current_agent}, action: {checkpoint.next_action})"
            )

            return {
                "success": True,
                "session_id": session_id,
                "status": "in_progress",
                "checkpoint": {
                    "current_agent": checkpoint.current_agent,
                    "next_action": checkpoint.next_action,
                    "context": checkpoint.context,
                    "pending_actions": checkpoint.pending_actions
                },
                "next_action": checkpoint.next_action,
                "message": f"Session resumed from {checkpoint.current_agent}"
            }

        except Exception as e:
            logger.error(f"Failed to resume session {session_id}: {e}", exc_info=True)
            return {
                "success": False,
                "session_id": session_id,
                "message": f"Resume failed: {str(e)}"
            }

    async def restore_checkpoint(
        self,
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get checkpoint data for manual restore

        Args:
            session_id: Session UUID

        Returns:
            Checkpoint data dictionary or None if not available
        """
        try:
            session = await self.manager.get_session(session_id)
            if not session or not session.last_checkpoint:
                return None

            checkpoint = session.last_checkpoint

            return {
                "session_id": session_id,
                "channel": session.channel,
                "contact_identifier": session.contact_identifier,
                "contact_name": session.contact_name,
                "classification": session.classification,
                "current_agent": checkpoint.current_agent,
                "next_action": checkpoint.next_action,
                "context": checkpoint.context,
                "pending_actions": checkpoint.pending_actions,
                "events_count": len(session.events),
                "last_event": session.events[-1].type if session.events else None
            }

        except Exception as e:
            logger.error(f"Failed to restore checkpoint for {session_id}: {e}")
            return None

    async def auto_resume_timeouts(
        self,
        max_age_hours: int = 24,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        """
        Automatically resume all timed-out sessions

        Args:
            max_age_hours: Maximum age in hours (default 24)
            max_retries: Maximum number of resume attempts (default 3)

        Returns:
            Dictionary with resume summary:
            {
                "total_found": int,
                "resumed": int,
                "failed": int,
                "skipped": int,
                "results": [...]
            }
        """
        try:
            # Find timed-out sessions
            sessions = await self.find_resumable_sessions(
                status="timeout",
                max_age_hours=max_age_hours
            )

            total_found = len(sessions)
            resumed = 0
            failed = 0
            skipped = 0
            results = []

            logger.info(f"Starting auto-resume for {total_found} timed-out sessions")

            for session in sessions:
                # Check retry count (from events)
                resume_attempts = len([
                    e for e in session.events
                    if e.type == "agent_routed" and
                       e.agent_name == "resume_service" and
                       e.data.get("action") == "resume"
                ])

                if resume_attempts >= max_retries:
                    logger.warning(f"Session {session.session_id} exceeded max retries ({max_retries})")
                    skipped += 1
                    results.append({
                        "session_id": session.session_id,
                        "status": "skipped",
                        "reason": f"Exceeded max retries ({resume_attempts}/{max_retries})"
                    })
                    continue

                # Attempt resume
                result = await self.resume_session(session.session_id)

                if result["success"]:
                    resumed += 1
                    results.append({
                        "session_id": session.session_id,
                        "status": "resumed",
                        "next_action": result.get("next_action")
                    })
                else:
                    failed += 1
                    results.append({
                        "session_id": session.session_id,
                        "status": "failed",
                        "reason": result.get("message")
                    })

            summary = {
                "total_found": total_found,
                "resumed": resumed,
                "failed": failed,
                "skipped": skipped,
                "results": results
            }

            logger.info(
                f"Auto-resume completed: {resumed} resumed, "
                f"{failed} failed, {skipped} skipped"
            )

            return summary

        except Exception as e:
            logger.error(f"Auto-resume failed: {e}", exc_info=True)
            return {
                "total_found": 0,
                "resumed": 0,
                "failed": 0,
                "skipped": 0,
                "error": str(e)
            }

    async def mark_abandoned(
        self,
        session_id: str,
        reason: Optional[str] = None
    ) -> bool:
        """
        Mark a session as abandoned (stop trying to resume)

        Args:
            session_id: Session UUID
            reason: Optional reason for abandonment

        Returns:
            True if successful, False otherwise
        """
        try:
            # Log abandonment event
            await self.manager.log_event(
                session_id=session_id,
                event_type="error",
                agent_name="resume_service",
                data={
                    "action": "mark_abandoned",
                    "reason": reason or "Session marked as abandoned after multiple resume attempts"
                }
            )

            # Mark as error status
            await self.manager.mark_error(
                session_id=session_id,
                error_data={"abandoned": True, "reason": reason}
            )

            logger.info(f"Marked session {session_id} as abandoned")
            return True

        except Exception as e:
            logger.error(f"Failed to mark session {session_id} as abandoned: {e}")
            return False
