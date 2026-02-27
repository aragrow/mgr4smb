"""
Conversation State Manager - High-level API for conversation tracking

Provides a simple interface for managing conversation lifecycle including:
- Starting sessions for email and phone conversations
- Logging events during conversation processing
- Creating checkpoints for resume capability
- Completing or timing out conversations
"""

import logging
from datetime import datetime as dt
from typing import Optional, Dict, Any, List
from src.models.conversation_state import ConversationState, ConversationEvent, ConversationCheckpoint
from src.workers.db_worker.conversation_state_repo import ConversationStateRepository

logger = logging.getLogger(__name__)


class ConversationStateManager:
    """
    High-level manager for conversation state tracking

    Simplifies conversation tracking by providing convenient methods
    for common operations. Handles MongoDB operations via repository.

    Examples:
        # Start email conversation
        manager = ConversationStateManager()
        session_id = await manager.start_session(
            channel="email",
            email_id="gmail-123",
            contact_identifier="client@example.com"
        )

        # Log event
        await manager.log_event(
            session_id=session_id,
            event_type="agent_routed",
            agent_name="orchestrator",
            data={"target_agent": "contact_agent"}
        )

        # Complete conversation
        await manager.complete_session(session_id)
    """

    def __init__(self):
        """Initialize manager with repository"""
        self.repo = ConversationStateRepository()

    async def start_session(
        self,
        channel: str,
        contact_identifier: str,
        contact_name: Optional[str] = None,
        classification: Optional[str] = None,
        # Email-specific
        email_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        # Phone-specific
        call_id: Optional[str] = None,
        phone_number: Optional[str] = None,
        call_direction: Optional[str] = None,
        # Initial event data
        data: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Start a new conversation session

        Args:
            channel: "email" or "phone"
            contact_identifier: Email address or phone number
            contact_name: Contact's name
            classification: "client", "vendor", or "lead"
            email_id: Gmail message ID (if channel=email)
            thread_id: Gmail thread ID (if channel=email)
            call_id: GoHighLevel call ID (if channel=phone)
            phone_number: Phone number (if channel=phone)
            call_direction: "inbound" or "outbound" (if channel=phone)
            data: Initial event data

        Returns:
            session_id: UUID for the created session

        Raises:
            ValueError: If required fields are missing
            Exception: If creation fails
        """
        try:
            # Validate channel-specific requirements
            if channel == "email":
                if not email_id:
                    raise ValueError("email_id required for email conversations")
            elif channel == "phone":
                if not call_id:
                    raise ValueError("call_id required for phone conversations")
            else:
                raise ValueError(f"Invalid channel: {channel}. Must be 'email' or 'phone'")

            # Create conversation state
            state = ConversationState(
                channel=channel,
                contact_identifier=contact_identifier,
                contact_name=contact_name,
                classification=classification,
                email_id=email_id,
                thread_id=thread_id,
                call_id=call_id,
                phone_number=phone_number,
                call_direction=call_direction
            )

            # Add initial event
            event_type = "email_received" if channel == "email" else "call_received"
            state.add_event(
                event_type=event_type,
                data=data or {}
            )

            # Save to database
            doc_id = await self.repo.create(state)

            logger.info(
                f"Started {channel} conversation session: {state.session_id} "
                f"for {contact_identifier}"
            )

            return state.session_id

        except Exception as e:
            logger.error(f"Failed to start conversation session: {e}", exc_info=True)
            raise

    async def log_event(
        self,
        session_id: str,
        event_type: str,
        agent_name: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        checkpoint: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Log an event to a conversation session

        Args:
            session_id: Session UUID
            event_type: Type of event (email_received, agent_routed, llm_call, etc.)
            agent_name: Agent that generated the event
            data: Event-specific data
            checkpoint: Optional state snapshot

        Returns:
            True if successful, False otherwise
        """
        try:
            # Create event
            event = ConversationEvent(
                type=event_type,
                agent_name=agent_name,
                data=data or {},
                checkpoint=checkpoint
            )

            # Add to database
            success = await self.repo.add_event(session_id, event)

            if success:
                logger.debug(f"Logged {event_type} event to session {session_id}")
            else:
                logger.warning(f"Failed to log event to session {session_id}")

            return success

        except Exception as e:
            logger.error(f"Failed to log event: {e}", exc_info=True)
            return False

    async def create_checkpoint(
        self,
        session_id: str,
        current_agent: str,
        state: str = "in_progress",
        next_action: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        pending_actions: Optional[List[str]] = None
    ) -> bool:
        """
        Create a state checkpoint for resume capability

        Args:
            session_id: Session UUID
            current_agent: Agent currently handling conversation
            state: Current conversation state (default: in_progress)
            next_action: Next action to take
            context: Contextual information
            pending_actions: List of pending actions

        Returns:
            True if successful, False otherwise
        """
        try:
            # Create checkpoint
            checkpoint = ConversationCheckpoint(
                current_agent=current_agent,
                state=state,
                next_action=next_action,
                context=context or {},
                pending_actions=pending_actions or []
            )

            # Update in database
            success = await self.repo.update_checkpoint(session_id, checkpoint)

            if success:
                logger.debug(f"Created checkpoint for session {session_id}")
            else:
                logger.warning(f"Failed to create checkpoint for session {session_id}")

            return success

        except Exception as e:
            logger.error(f"Failed to create checkpoint: {e}", exc_info=True)
            return False

    async def complete_session(self, session_id: str) -> bool:
        """
        Mark a conversation session as completed

        Args:
            session_id: Session UUID

        Returns:
            True if successful, False otherwise
        """
        try:
            success = await self.repo.mark_completed(session_id)

            if success:
                logger.info(f"Completed conversation session: {session_id}")
            else:
                logger.warning(f"Failed to complete session {session_id}")

            return success

        except Exception as e:
            logger.error(f"Failed to complete session: {e}", exc_info=True)
            return False

    async def mark_timeout(self, session_id: str, timeout_at: Optional[dt] = None) -> bool:
        """
        Mark a conversation session as timed out

        Args:
            session_id: Session UUID
            timeout_at: Timeout timestamp (defaults to now)

        Returns:
            True if successful, False otherwise
        """
        try:
            success = await self.repo.mark_timeout(session_id, timeout_at)

            if success:
                logger.info(f"Marked session {session_id} as timeout")
            else:
                logger.warning(f"Failed to mark session {session_id} as timeout")

            return success

        except Exception as e:
            logger.error(f"Failed to mark timeout: {e}", exc_info=True)
            return False

    async def mark_error(self, session_id: str, error_data: Optional[Dict[str, Any]] = None) -> bool:
        """
        Mark a conversation session as errored

        Args:
            session_id: Session UUID
            error_data: Optional error details

        Returns:
            True if successful, False otherwise
        """
        try:
            # Log error event
            event_logged = await self.log_event(
                session_id=session_id,
                event_type="error",
                data=error_data or {}
            )

            # Get current state and update status
            state = await self.repo.find_by_session_id(session_id)
            if state:
                state.mark_error(error_data)
                await self.repo.update(state)

            logger.info(f"Marked session {session_id} as error")
            return event_logged

        except Exception as e:
            logger.error(f"Failed to mark error: {e}", exc_info=True)
            return False

    async def get_session(self, session_id: str) -> Optional[ConversationState]:
        """
        Get conversation state by session ID

        Args:
            session_id: Session UUID

        Returns:
            ConversationState or None if not found
        """
        try:
            return await self.repo.find_by_session_id(session_id)
        except Exception as e:
            logger.error(f"Failed to get session {session_id}: {e}")
            return None

    async def get_session_by_email(self, email_id: str) -> Optional[ConversationState]:
        """
        Get conversation state by email ID

        Args:
            email_id: Gmail message ID

        Returns:
            ConversationState or None if not found
        """
        try:
            return await self.repo.find_by_email_id(email_id)
        except Exception as e:
            logger.error(f"Failed to get session by email_id {email_id}: {e}")
            return None

    async def get_session_by_call(self, call_id: str) -> Optional[ConversationState]:
        """
        Get conversation state by call ID

        Args:
            call_id: GoHighLevel call ID

        Returns:
            ConversationState or None if not found
        """
        try:
            return await self.repo.find_by_call_id(call_id)
        except Exception as e:
            logger.error(f"Failed to get session by call_id {call_id}: {e}")
            return None

    async def get_session_by_thread(self, thread_id: str) -> Optional[ConversationState]:
        """
        Get conversation state by email thread ID

        Args:
            thread_id: Gmail thread ID

        Returns:
            Most recent ConversationState for this thread, or None if not found
        """
        try:
            return await self.repo.find_by_thread_id(thread_id)
        except Exception as e:
            logger.error(f"Failed to get session by thread_id {thread_id}: {e}")
            return None

    async def get_contact_history(
        self,
        contact_identifier: str,
        limit: int = 50,
        channel: Optional[str] = None
    ) -> List[ConversationState]:
        """
        Get conversation history for a contact

        Args:
            contact_identifier: Email or phone number
            limit: Maximum number to return (default 50)
            channel: Optional filter by channel

        Returns:
            List of ConversationState objects
        """
        try:
            return await self.repo.find_by_contact(
                contact_identifier=contact_identifier,
                limit=limit,
                channel=channel
            )
        except Exception as e:
            logger.error(f"Failed to get contact history for {contact_identifier}: {e}")
            return []

    async def find_incomplete_sessions(self, max_age_hours: int = 24) -> List[ConversationState]:
        """
        Find incomplete conversation sessions for potential resume

        Args:
            max_age_hours: Maximum age in hours (default 24)

        Returns:
            List of incomplete ConversationState objects
        """
        try:
            return await self.repo.find_incomplete_sessions(max_age_hours=max_age_hours)
        except Exception as e:
            logger.error(f"Failed to find incomplete sessions: {e}")
            return []

    async def get_statistics(
        self,
        start_date: Optional[dt] = None,
        end_date: Optional[dt] = None,
        channel: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get conversation statistics for a time period

        Args:
            start_date: Start date (defaults to 30 days ago)
            end_date: End date (defaults to now)
            channel: Optional filter by channel

        Returns:
            Dictionary of statistics
        """
        try:
            return await self.repo.get_statistics(
                start_date=start_date,
                end_date=end_date,
                channel=channel
            )
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {}

    async def cleanup_old_sessions(self, days_old: int = 90) -> int:
        """
        Delete old completed/errored conversation sessions

        Args:
            days_old: Age threshold in days (default 90)

        Returns:
            Number of deleted sessions
        """
        try:
            deleted_count = await self.repo.delete_old_sessions(days_old=days_old)
            logger.info(f"Cleaned up {deleted_count} old conversation sessions")
            return deleted_count
        except Exception as e:
            logger.error(f"Failed to cleanup old sessions: {e}")
            return 0
