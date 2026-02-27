"""
Conversation Repository - CRUD operations for email conversations

Handles database operations for the conversations collection in MongoDB
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import DuplicateKeyError

from src.workers.db_worker.mongo_client import MongoDBClient
from src.models.conversation import Conversation, ConversationCreate, ConversationUpdate


class ConversationRepository:
    """Repository for conversation database operations"""

    COLLECTION_NAME = "conversations"

    def __init__(self, db: Optional[AsyncIOMotorDatabase] = None):
        """
        Initialize conversation repository

        Args:
            db: Optional database instance. If not provided, uses MongoDBClient.get_database()
        """
        self.db = db if db is not None else MongoDBClient.get_database()
        self.collection = self.db[self.COLLECTION_NAME]

    async def ensure_indexes(self) -> None:
        """
        Create indexes for efficient querying

        Indexes:
        - email_id: unique index for Gmail message ID
        - to: index for client lookup
        - datetime: descending index for time-based queries
        - thread_id: index for thread-based queries
        - is_processed: index for processing status queries
        """
        await self.collection.create_index("email_id", unique=True)
        await self.collection.create_index("to")
        await self.collection.create_index([("datetime", DESCENDING)])
        await self.collection.create_index("thread_id")
        await self.collection.create_index("is_processed")

    async def create(self, conversation: ConversationCreate) -> Conversation:
        """
        Create a new conversation

        Args:
            conversation: Conversation data to create

        Returns:
            Created conversation with MongoDB ID

        Raises:
            DuplicateKeyError: If email_id already exists
        """
        doc = conversation.model_dump(by_alias=True)
        doc["created_at"] = datetime.utcnow()
        doc["updated_at"] = datetime.utcnow()
        doc["is_processed"] = False

        result = await self.collection.insert_one(doc)
        doc["_id"] = str(result.inserted_id)

        return Conversation(**doc)

    async def find_by_id(self, conversation_id: str) -> Optional[Conversation]:
        """
        Find conversation by MongoDB ID

        Args:
            conversation_id: MongoDB document ID

        Returns:
            Conversation if found, None otherwise
        """
        from bson import ObjectId

        try:
            doc = await self.collection.find_one({"_id": ObjectId(conversation_id)})
            if doc:
                doc["_id"] = str(doc["_id"])
                return Conversation(**doc)
        except Exception:
            return None

        return None

    async def find_by_email_id(self, email_id: str) -> Optional[Conversation]:
        """
        Find conversation by Gmail message ID

        Args:
            email_id: Gmail message ID

        Returns:
            Conversation if found, None otherwise
        """
        doc = await self.collection.find_one({"email_id": email_id})
        if doc:
            doc["_id"] = str(doc["_id"])
            return Conversation(**doc)
        return None

    async def find_by_client_email(
        self, client_email: str, limit: int = 100, skip: int = 0
    ) -> List[Conversation]:
        """
        Find conversations for a specific client email

        Args:
            client_email: Client email address (to field)
            limit: Maximum number of results
            skip: Number of results to skip

        Returns:
            List of conversations ordered by datetime descending
        """
        cursor = (
            self.collection.find({"to": client_email})
            .sort("datetime", DESCENDING)
            .skip(skip)
            .limit(limit)
        )

        conversations = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            conversations.append(Conversation(**doc))

        return conversations

    async def find_by_thread_id(self, thread_id: str) -> List[Conversation]:
        """
        Find all conversations in a Gmail thread

        Args:
            thread_id: Gmail thread ID

        Returns:
            List of conversations ordered by datetime ascending
        """
        cursor = self.collection.find({"thread_id": thread_id}).sort("datetime", ASCENDING)

        conversations = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            conversations.append(Conversation(**doc))

        return conversations

    async def find_unprocessed(self, limit: int = 100) -> List[Conversation]:
        """
        Find unprocessed conversations

        Args:
            limit: Maximum number of results

        Returns:
            List of unprocessed conversations ordered by datetime ascending
        """
        cursor = (
            self.collection.find({"is_processed": False})
            .sort("datetime", ASCENDING)
            .limit(limit)
        )

        conversations = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            conversations.append(Conversation(**doc))

        return conversations

    async def update(
        self, conversation_id: str, update_data: ConversationUpdate
    ) -> Optional[Conversation]:
        """
        Update a conversation

        Args:
            conversation_id: MongoDB document ID
            update_data: Fields to update

        Returns:
            Updated conversation if found, None otherwise
        """
        from bson import ObjectId

        update_dict = update_data.model_dump(exclude_unset=True, by_alias=True)
        update_dict["updated_at"] = datetime.utcnow()

        try:
            result = await self.collection.find_one_and_update(
                {"_id": ObjectId(conversation_id)},
                {"$set": update_dict},
                return_document=True,
            )

            if result:
                result["_id"] = str(result["_id"])
                return Conversation(**result)
        except Exception:
            return None

        return None

    async def mark_as_processed(self, conversation_id: str) -> bool:
        """
        Mark a conversation as processed

        Args:
            conversation_id: MongoDB document ID

        Returns:
            True if updated, False otherwise
        """
        from bson import ObjectId

        try:
            result = await self.collection.update_one(
                {"_id": ObjectId(conversation_id)},
                {"$set": {"is_processed": True, "updated_at": datetime.utcnow()}},
            )
            return result.modified_count > 0
        except Exception:
            return False

    async def delete(self, conversation_id: str) -> bool:
        """
        Delete a conversation

        Args:
            conversation_id: MongoDB document ID

        Returns:
            True if deleted, False otherwise
        """
        from bson import ObjectId

        try:
            result = await self.collection.delete_one({"_id": ObjectId(conversation_id)})
            return result.deleted_count > 0
        except Exception:
            return False

    async def count_by_client(self, client_email: str) -> int:
        """
        Count conversations for a client

        Args:
            client_email: Client email address

        Returns:
            Number of conversations
        """
        return await self.collection.count_documents({"to": client_email})

    async def get_recent_conversations(
        self, hours: int = 24, limit: int = 100
    ) -> List[Conversation]:
        """
        Get recent conversations within specified hours

        Args:
            hours: Number of hours to look back
            limit: Maximum number of results

        Returns:
            List of recent conversations ordered by datetime descending
        """
        since = datetime.utcnow() - timedelta(hours=hours)
        cursor = (
            self.collection.find({"datetime": {"$gte": since}})
            .sort("datetime", DESCENDING)
            .limit(limit)
        )

        conversations = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            conversations.append(Conversation(**doc))

        return conversations
