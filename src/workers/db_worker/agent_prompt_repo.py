"""
Agent Prompt Repository - CRUD operations for agent prompts

Handles database operations for the agent_prompts collection in MongoDB
"""

from datetime import datetime
from typing import Optional, List
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ASCENDING

from src.workers.db_worker.mongo_client import MongoDBClient
from src.models.agent_prompt import AgentPrompt, AgentPromptCreate, AgentPromptUpdate


class AgentPromptRepository:
    """Repository for agent prompt database operations"""

    COLLECTION_NAME = "agent_prompts"

    def __init__(self, db: Optional[AsyncIOMotorDatabase] = None):
        """
        Initialize agent prompt repository

        Args:
            db: Optional database instance. If not provided, uses MongoDBClient.get_database()
        """
        self.db = db if db is not None else MongoDBClient.get_database()
        self.collection = self.db[self.COLLECTION_NAME]

    async def ensure_indexes(self) -> None:
        """
        Create indexes for efficient querying

        Indexes:
        - (agent_name, prompt_type): unique compound index for lookup
        - agent_name: index for listing all prompts for an agent
        - version: index for version queries
        """
        # Unique compound index on agent_name + prompt_type
        await self.collection.create_index(
            [("agent_name", ASCENDING), ("prompt_type", ASCENDING)],
            unique=True
        )
        await self.collection.create_index("agent_name")
        await self.collection.create_index([("version", ASCENDING)])

    async def create(self, prompt: AgentPromptCreate) -> AgentPrompt:
        """
        Create a new agent prompt

        Args:
            prompt: Prompt data to create

        Returns:
            Created prompt with MongoDB ID

        Raises:
            DuplicateKeyError: If (agent_name, prompt_type) already exists
        """
        doc = prompt.model_dump(by_alias=True)
        doc["created_at"] = datetime.utcnow()
        doc["updated_at"] = datetime.utcnow()

        result = await self.collection.insert_one(doc)
        doc["_id"] = str(result.inserted_id)

        return AgentPrompt(**doc)

    async def find_by_agent_and_type(
        self, agent_name: str, prompt_type: str
    ) -> Optional[AgentPrompt]:
        """
        Find prompt by agent name and prompt type

        Args:
            agent_name: Agent name (orchestrator, manager_agent, etc.)
            prompt_type: Prompt type (intent_classification, processing, etc.)

        Returns:
            AgentPrompt if found, None otherwise
        """
        doc = await self.collection.find_one({
            "agent_name": agent_name,
            "prompt_type": prompt_type
        })

        if doc:
            doc["_id"] = str(doc["_id"])
            return AgentPrompt(**doc)

        return None

    async def find_by_agent(self, agent_name: str) -> List[AgentPrompt]:
        """
        Find all prompts for a specific agent

        Args:
            agent_name: Agent name

        Returns:
            List of agent prompts
        """
        cursor = self.collection.find({"agent_name": agent_name})

        prompts = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            prompts.append(AgentPrompt(**doc))

        return prompts

    async def update(
        self, agent_name: str, prompt_type: str, update_data: AgentPromptUpdate
    ) -> Optional[AgentPrompt]:
        """
        Update an agent prompt

        Args:
            agent_name: Agent name
            prompt_type: Prompt type
            update_data: Fields to update

        Returns:
            Updated prompt if found, None otherwise
        """
        update_dict = update_data.model_dump(exclude_unset=True, by_alias=True)
        update_dict["updated_at"] = datetime.utcnow()

        result = await self.collection.find_one_and_update(
            {"agent_name": agent_name, "prompt_type": prompt_type},
            {"$set": update_dict},
            return_document=True,
        )

        if result:
            result["_id"] = str(result["_id"])
            return AgentPrompt(**result)

        return None

    async def delete(self, agent_name: str, prompt_type: str) -> bool:
        """
        Delete an agent prompt

        Args:
            agent_name: Agent name
            prompt_type: Prompt type

        Returns:
            True if deleted, False otherwise
        """
        result = await self.collection.delete_one({
            "agent_name": agent_name,
            "prompt_type": prompt_type
        })

        return result.deleted_count > 0

    async def list_all(self) -> List[AgentPrompt]:
        """
        List all agent prompts

        Returns:
            List of all agent prompts
        """
        cursor = self.collection.find()

        prompts = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            prompts.append(AgentPrompt(**doc))

        return prompts
