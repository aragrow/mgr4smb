"""
Conversation State Repository - MongoDB operations for conversation tracking

Provides CRUD operations and specialized queries for conversation states,
supporting both email and phone conversations with resume capability.
"""

import logging
from datetime import datetime as dt, timedelta
from typing import List, Optional, Dict, Any
from bson import ObjectId
from src.workers.db_worker.mongo_client import MongoDBClient
from src.models.conversation_state import ConversationState, ConversationEvent, ConversationCheckpoint

logger = logging.getLogger(__name__)


class ConversationStateRepository:
    """
    Repository for conversation state operations

    Handles all MongoDB operations for the conversation_states collection
    including creation, updates, queries, and analytics support.
    """

    def __init__(self):
        """Initialize repository with MongoDB client"""
        self.client = MongoDBClient.get_client()
        self.db = MongoDBClient.get_database()
        self.collection = self.db["conversation_states"]

    async def create(self, conversation_state: ConversationState) -> str:
        """
        Create a new conversation state

        Args:
            conversation_state: ConversationState to create

        Returns:
            Inserted document ID as string

        Raises:
            Exception: If creation fails
        """
        try:
            # Convert to dict for MongoDB
            doc = conversation_state.model_dump(by_alias=True, exclude={"id"})

            # Insert
            result = await self.collection.insert_one(doc)
            logger.info(f"Created conversation state: {result.inserted_id}")

            return str(result.inserted_id)

        except Exception as e:
            logger.error(f"Failed to create conversation state: {e}", exc_info=True)
            raise

    async def find_by_session_id(self, session_id: str) -> Optional[ConversationState]:
        """
        Find conversation state by session ID

        Args:
            session_id: Session UUID

        Returns:
            ConversationState or None if not found
        """
        try:
            doc = await self.collection.find_one({"session_id": session_id})

            if doc:
                doc["_id"] = str(doc["_id"])
                return ConversationState(**doc)

            return None

        except Exception as e:
            logger.error(f"Failed to find conversation state by session_id {session_id}: {e}")
            return None

    async def find_by_email_id(self, email_id: str) -> Optional[ConversationState]:
        """
        Find conversation state by email ID

        Args:
            email_id: Gmail message ID

        Returns:
            ConversationState or None if not found
        """
        try:
            doc = await self.collection.find_one({"email_id": email_id})

            if doc:
                doc["_id"] = str(doc["_id"])
                return ConversationState(**doc)

            return None

        except Exception as e:
            logger.error(f"Failed to find conversation state by email_id {email_id}: {e}")
            return None

    async def find_by_call_id(self, call_id: str) -> Optional[ConversationState]:
        """
        Find conversation state by call ID

        Args:
            call_id: GoHighLevel call ID

        Returns:
            ConversationState or None if not found
        """
        try:
            doc = await self.collection.find_one({"call_id": call_id})

            if doc:
                doc["_id"] = str(doc["_id"])
                return ConversationState(**doc)

            return None

        except Exception as e:
            logger.error(f"Failed to find conversation state by call_id {call_id}: {e}")
            return None

    async def find_by_thread_id(self, thread_id: str) -> Optional[ConversationState]:
        """
        Find conversation state by email thread ID

        Args:
            thread_id: Gmail thread ID

        Returns:
            Most recent ConversationState for this thread, or None if not found
        """
        try:
            # Find most recent conversation in this thread
            doc = await self.collection.find_one(
                {"thread_id": thread_id},
                sort=[("created_at", -1)]  # Most recent first
            )

            if doc:
                doc["_id"] = str(doc["_id"])
                return ConversationState(**doc)

            return None

        except Exception as e:
            logger.error(f"Failed to find conversation state by thread_id {thread_id}: {e}")
            return None

    async def find_by_contact(
        self,
        contact_identifier: str,
        limit: int = 50,
        channel: Optional[str] = None
    ) -> List[ConversationState]:
        """
        Find all conversation states for a contact

        Args:
            contact_identifier: Email or phone number
            limit: Maximum number to return
            channel: Optional filter by channel (email/phone)

        Returns:
            List of ConversationState objects
        """
        try:
            query = {"contact_identifier": contact_identifier}
            if channel:
                query["channel"] = channel

            cursor = self.collection.find(query).sort("created_at", -1).limit(limit)
            docs = await cursor.to_list(length=limit)

            states = []
            for doc in docs:
                doc["_id"] = str(doc["_id"])
                states.append(ConversationState(**doc))

            logger.info(f"Found {len(states)} conversation states for {contact_identifier}")
            return states

        except Exception as e:
            logger.error(f"Failed to find conversation states for {contact_identifier}: {e}")
            return []

    async def find_by_status(
        self,
        status: str,
        limit: int = 100,
        channel: Optional[str] = None
    ) -> List[ConversationState]:
        """
        Find conversation states by status

        Args:
            status: Status to filter (in_progress, completed, timeout, error)
            limit: Maximum number to return
            channel: Optional filter by channel

        Returns:
            List of ConversationState objects
        """
        try:
            query = {"status": status}
            if channel:
                query["channel"] = channel

            cursor = self.collection.find(query).sort("created_at", -1).limit(limit)
            docs = await cursor.to_list(length=limit)

            states = []
            for doc in docs:
                doc["_id"] = str(doc["_id"])
                states.append(ConversationState(**doc))

            logger.info(f"Found {len(states)} conversation states with status={status}")
            return states

        except Exception as e:
            logger.error(f"Failed to find conversation states by status {status}: {e}")
            return []

    async def find_incomplete_sessions(
        self,
        max_age_hours: int = 24
    ) -> List[ConversationState]:
        """
        Find incomplete (in_progress or timeout) sessions

        Args:
            max_age_hours: Maximum age in hours (default 24)

        Returns:
            List of incomplete ConversationState objects
        """
        try:
            cutoff_time = dt.utcnow() - timedelta(hours=max_age_hours)

            query = {
                "status": {"$in": ["in_progress", "timeout"]},
                "created_at": {"$gte": cutoff_time}
            }

            cursor = self.collection.find(query).sort("created_at", -1)
            docs = await cursor.to_list(length=None)

            states = []
            for doc in docs:
                doc["_id"] = str(doc["_id"])
                states.append(ConversationState(**doc))

            logger.info(f"Found {len(states)} incomplete sessions")
            return states

        except Exception as e:
            logger.error(f"Failed to find incomplete sessions: {e}")
            return []

    async def update(self, conversation_state: ConversationState) -> bool:
        """
        Update an existing conversation state

        Args:
            conversation_state: ConversationState to update

        Returns:
            True if successful, False otherwise
        """
        try:
            if not conversation_state.id:
                logger.error("Cannot update conversation state without ID")
                return False

            # Update timestamp
            conversation_state.updated_at = dt.utcnow()

            # Convert to dict
            doc = conversation_state.model_dump(by_alias=True, exclude={"id"})

            # Update
            result = await self.collection.update_one(
                {"_id": ObjectId(conversation_state.id)},
                {"$set": doc}
            )

            if result.modified_count > 0:
                logger.info(f"Updated conversation state: {conversation_state.id}")
                return True
            else:
                logger.warning(f"No changes made to conversation state: {conversation_state.id}")
                return False

        except Exception as e:
            logger.error(f"Failed to update conversation state: {e}", exc_info=True)
            return False

    async def add_event(
        self,
        session_id: str,
        event: ConversationEvent
    ) -> bool:
        """
        Add an event to a conversation state

        Args:
            session_id: Session UUID
            event: Event to add

        Returns:
            True if successful, False otherwise
        """
        try:
            result = await self.collection.update_one(
                {"session_id": session_id},
                {
                    "$push": {"events": event.model_dump()},
                    "$set": {"updated_at": dt.utcnow()}
                }
            )

            if result.modified_count > 0:
                logger.debug(f"Added event {event.type} to session {session_id}")
                return True
            else:
                logger.warning(f"Failed to add event to session {session_id}")
                return False

        except Exception as e:
            logger.error(f"Failed to add event to session {session_id}: {e}")
            return False

    async def update_checkpoint(
        self,
        session_id: str,
        checkpoint: ConversationCheckpoint
    ) -> bool:
        """
        Update the last checkpoint for a conversation

        Args:
            session_id: Session UUID
            checkpoint: Checkpoint to set

        Returns:
            True if successful, False otherwise
        """
        try:
            result = await self.collection.update_one(
                {"session_id": session_id},
                {
                    "$set": {
                        "last_checkpoint": checkpoint.model_dump(),
                        "updated_at": dt.utcnow()
                    }
                }
            )

            if result.modified_count > 0:
                logger.debug(f"Updated checkpoint for session {session_id}")
                return True
            else:
                logger.warning(f"Failed to update checkpoint for session {session_id}")
                return False

        except Exception as e:
            logger.error(f"Failed to update checkpoint for session {session_id}: {e}")
            return False

    async def mark_completed(self, session_id: str) -> bool:
        """
        Mark a conversation as completed

        Args:
            session_id: Session UUID

        Returns:
            True if successful, False otherwise
        """
        try:
            now = dt.utcnow()

            result = await self.collection.update_one(
                {"session_id": session_id},
                {
                    "$set": {
                        "status": "completed",
                        "completed_at": now,
                        "updated_at": now
                    }
                }
            )

            if result.modified_count > 0:
                logger.info(f"Marked session {session_id} as completed")
                return True
            else:
                logger.warning(f"Failed to mark session {session_id} as completed")
                return False

        except Exception as e:
            logger.error(f"Failed to mark session {session_id} as completed: {e}")
            return False

    async def mark_timeout(self, session_id: str, timeout_at: Optional[dt] = None) -> bool:
        """
        Mark a conversation as timed out

        Args:
            session_id: Session UUID
            timeout_at: Timeout timestamp (defaults to now)

        Returns:
            True if successful, False otherwise
        """
        try:
            now = dt.utcnow()

            result = await self.collection.update_one(
                {"session_id": session_id},
                {
                    "$set": {
                        "status": "timeout",
                        "timeout_at": timeout_at or now,
                        "updated_at": now
                    }
                }
            )

            if result.modified_count > 0:
                logger.info(f"Marked session {session_id} as timeout")
                return True
            else:
                logger.warning(f"Failed to mark session {session_id} as timeout")
                return False

        except Exception as e:
            logger.error(f"Failed to mark session {session_id} as timeout: {e}")
            return False

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
            if not start_date:
                start_date = dt.utcnow() - timedelta(days=30)
            if not end_date:
                end_date = dt.utcnow()

            # Build query
            query = {
                "created_at": {
                    "$gte": start_date,
                    "$lte": end_date
                }
            }
            if channel:
                query["channel"] = channel

            # Get counts by status
            pipeline = [
                {"$match": query},
                {"$group": {
                    "_id": "$status",
                    "count": {"$sum": 1},
                    "avg_duration": {"$avg": "$metadata.processing_duration_ms"},
                    "avg_events": {"$avg": "$metadata.total_events"},
                    "avg_llm_calls": {"$avg": "$metadata.llm_calls"},
                    "total_tokens": {"$sum": "$metadata.total_tokens"}
                }}
            ]

            cursor = self.collection.aggregate(pipeline)
            results = await cursor.to_list(length=None)

            # Format results
            stats = {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "channel": channel or "all",
                "by_status": {r["_id"]: r for r in results},
                "total_conversations": sum(r["count"] for r in results),
                "total_tokens": sum(r.get("total_tokens", 0) for r in results)
            }

            logger.info(f"Retrieved statistics: {stats['total_conversations']} conversations")
            return stats

        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {}

    async def delete_old_sessions(self, days_old: int = 90) -> int:
        """
        Delete conversation states older than specified days

        Args:
            days_old: Age threshold in days (default 90)

        Returns:
            Number of deleted documents
        """
        try:
            cutoff_date = dt.utcnow() - timedelta(days=days_old)

            result = await self.collection.delete_many({
                "created_at": {"$lt": cutoff_date},
                "status": {"$in": ["completed", "error"]}  # Don't delete in_progress or timeout
            })

            logger.info(f"Deleted {result.deleted_count} old conversation states")
            return result.deleted_count

        except Exception as e:
            logger.error(f"Failed to delete old sessions: {e}")
            return 0
