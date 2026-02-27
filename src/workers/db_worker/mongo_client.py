"""
MongoDB Atlas client with connection pooling and health checks

This module provides a singleton MongoDB client for the application.
"""

import logging
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import MongoClient
from pymongo.server_api import ServerApi

from src.config import get_settings

logger = logging.getLogger(__name__)


class MongoDBClient:
    """
    MongoDB Atlas client with connection pooling (singleton pattern)

    This class manages the MongoDB connection and provides access to the database.
    Uses the singleton pattern to ensure only one client instance exists.
    """

    _instance: Optional[AsyncIOMotorClient] = None
    _sync_client: Optional[MongoClient] = None
    _db: Optional[AsyncIOMotorDatabase] = None

    @classmethod
    def get_client(cls) -> AsyncIOMotorClient:
        """
        Get or create async MongoDB client (singleton pattern)

        Returns:
            AsyncIOMotorClient: MongoDB async client instance

        Raises:
            ValueError: If MONGODB_URI is not configured
        """
        if cls._instance is None:
            settings = get_settings()

            if not settings.mongodb_uri:
                raise ValueError("MONGODB_URI environment variable not set")

            cls._instance = AsyncIOMotorClient(
                settings.mongodb_uri,
                maxPoolSize=settings.mongodb_max_pool_size,
                minPoolSize=settings.mongodb_min_pool_size,
                maxIdleTimeMS=45000,  # Close idle connections after 45 seconds
                waitQueueTimeoutMS=10000,  # Wait 10 seconds for available connection
                serverSelectionTimeoutMS=5000,  # 5 second server selection timeout
                retryWrites=True,
                w="majority",  # Write concern
                server_api=ServerApi("1"),
            )
            logger.info(
                f"MongoDB async client initialized (pool: {settings.mongodb_min_pool_size}-{settings.mongodb_max_pool_size})"
            )

        return cls._instance

    @classmethod
    def get_sync_client(cls) -> MongoClient:
        """
        Get or create sync MongoDB client for health checks

        Returns:
            MongoClient: MongoDB sync client instance

        Raises:
            ValueError: If MONGODB_URI is not configured
        """
        if cls._sync_client is None:
            settings = get_settings()

            if not settings.mongodb_uri:
                raise ValueError("MONGODB_URI environment variable not set")

            cls._sync_client = MongoClient(
                settings.mongodb_uri,
                server_api=ServerApi("1"),
            )
            logger.info("MongoDB sync client initialized for health checks")

        return cls._sync_client

    @classmethod
    def get_database(cls) -> AsyncIOMotorDatabase:
        """
        Get database instance

        Returns:
            AsyncIOMotorDatabase: MongoDB database instance
        """
        if cls._db is None:
            client = cls.get_client()
            settings = get_settings()
            cls._db = client[settings.mongodb_database]
            logger.info(f"Connected to database: {settings.mongodb_database}")

        return cls._db

    @classmethod
    async def health_check(cls) -> bool:
        """
        Perform async health check using ping command

        Returns:
            bool: True if connection is healthy, False otherwise
        """
        try:
            client = cls.get_client()
            await client.admin.command("ping")
            logger.info("MongoDB async health check: OK")
            return True
        except Exception as e:
            logger.error(f"MongoDB async health check failed: {e}")
            return False

    @classmethod
    def health_check_sync(cls) -> bool:
        """
        Perform synchronous health check using ping command

        This method uses the sync client and matches the user's requested pattern:
        - Create a client and connect to the server
        - Send a ping to confirm a successful connection

        Returns:
            bool: True if connection is healthy, False otherwise
        """
        try:
            # Create a new client and connect to the server
            client = cls.get_sync_client()

            # Send a ping to confirm a successful connection
            client.admin.command("ping")
            print("Pinged your deployment. You successfully connected to MongoDB!")
            logger.info("MongoDB sync health check: OK")
            return True
        except Exception as e:
            print(e)
            logger.error(f"MongoDB sync health check failed: {e}")
            return False

    @classmethod
    async def close(cls) -> None:
        """Close MongoDB connections"""
        if cls._instance:
            cls._instance.close()
            cls._instance = None
            cls._db = None
            logger.info("MongoDB async connection closed")

        if cls._sync_client:
            cls._sync_client.close()
            cls._sync_client = None
            logger.info("MongoDB sync connection closed")


async def check_mongo_health() -> bool:
    """
    Convenience function to check MongoDB health

    Returns:
        bool: True if healthy, False otherwise
    """
    return await MongoDBClient.health_check()
