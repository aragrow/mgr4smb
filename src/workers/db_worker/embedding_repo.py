"""
Embedding Repository - CRUD operations and Google Gemini integration

Handles:
- Embedding generation using Google Gemini text-embedding-004
- Vector storage in MongoDB Atlas
- Vector similarity search using MongoDB Atlas Vector Search
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from google import genai
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.workers.db_worker.mongo_client import MongoDBClient
from src.models.embedding import Embedding, EmbeddingCreate, VectorSearchResult
from src.config.settings import get_settings


class EmbeddingRepository:
    """Repository for embedding operations with Google Gemini integration"""

    COLLECTION_NAME = "embeddings"

    def __init__(self, db: Optional[AsyncIOMotorDatabase] = None):
        """
        Initialize embedding repository

        Args:
            db: Optional database instance. If not provided, uses MongoDBClient.get_database()
        """
        self.db = db if db is not None else MongoDBClient.get_database()
        self.collection = self.db[self.COLLECTION_NAME]
        self.settings = get_settings()

        # Initialize Google Gemini client
        self.genai_client = genai.Client(api_key=self.settings.google_api_key)

        # Get vector index name from settings
        self.VECTOR_INDEX_NAME = self.settings.vector_index_name

    async def ensure_indexes(self) -> None:
        """
        Create indexes for efficient querying

        Note: Vector search index must be created manually in MongoDB Atlas UI
        See: https://www.mongodb.com/docs/atlas/atlas-vector-search/create-index/

        Standard indexes:
        - conversation_id: index for conversation lookup
        - email_id: index for email lookup
        - created_at: descending index for time-based queries
        """
        await self.collection.create_index("conversation_id")
        await self.collection.create_index("email_id")
        await self.collection.create_index([("created_at", -1)])

    def generate_embedding(self, text: str, task_type: Optional[str] = None) -> List[float]:
        """
        Generate embedding using Google Gemini

        Args:
            text: Text content to embed
            task_type: Optional task type override. If not provided, uses settings.
                      Use 'retrieval_document' for storing, 'retrieval_query' for searching

        Returns:
            Embedding vector (3072 dimensions for gemini-embedding-001)

        Raises:
            Exception: If embedding generation fails
        """
        result = self.genai_client.models.embed_content(
            model=self.settings.embedding_model,
            content=text,
        )

        return result.embeddings[0].values

    async def create_embedding_from_text(
        self,
        conversation_id: str,
        email_id: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Embedding:
        """
        Generate embedding and store in database

        Uses 'retrieval_document' task type for optimal storage performance.

        Args:
            conversation_id: Reference to conversation document
            email_id: Gmail message ID
            text: Text content to embed (should include from, to, cc, subject, body, datetime)
            metadata: Optional metadata (from, to, cc, subject, datetime, etc.)

        Returns:
            Created embedding document
        """
        # Generate embedding using Google Gemini with retrieval_document task type
        # This optimizes the embedding for storage and later retrieval
        embedding_vector = self.generate_embedding(text, task_type="retrieval_document")

        # Create embedding document with metadata
        embedding_data = EmbeddingCreate(
            conversation_id=conversation_id,
            email_id=email_id,
            embedding=embedding_vector,
            text_content=text[:1000],  # Store first 1000 chars for reference
            embedding_model=self.settings.embedding_model,
            embedding_dimensions=self.settings.embedding_dimensions,
            metadata=metadata,
        )

        return await self.create(embedding_data)

    async def create(self, embedding: EmbeddingCreate) -> Embedding:
        """
        Create a new embedding document

        Args:
            embedding: Embedding data to create

        Returns:
            Created embedding with MongoDB ID
        """
        doc = embedding.model_dump(by_alias=True)
        doc["created_at"] = datetime.utcnow()

        result = await self.collection.insert_one(doc)
        doc["_id"] = str(result.inserted_id)

        return Embedding(**doc)

    async def find_by_id(self, embedding_id: str) -> Optional[Embedding]:
        """
        Find embedding by MongoDB ID

        Args:
            embedding_id: MongoDB document ID

        Returns:
            Embedding if found, None otherwise
        """
        from bson import ObjectId

        try:
            doc = await self.collection.find_one({"_id": ObjectId(embedding_id)})
            if doc:
                doc["_id"] = str(doc["_id"])
                return Embedding(**doc)
        except Exception:
            return None

        return None

    async def find_by_conversation_id(self, conversation_id: str) -> Optional[Embedding]:
        """
        Find embedding by conversation ID

        Args:
            conversation_id: Conversation document ID

        Returns:
            Embedding if found, None otherwise
        """
        doc = await self.collection.find_one({"conversation_id": conversation_id})
        if doc:
            doc["_id"] = str(doc["_id"])
            return Embedding(**doc)
        return None

    async def find_by_email_id(self, email_id: str) -> Optional[Embedding]:
        """
        Find embedding by email ID

        Args:
            email_id: Gmail message ID

        Returns:
            Embedding if found, None otherwise
        """
        doc = await self.collection.find_one({"email_id": email_id})
        if doc:
            doc["_id"] = str(doc["_id"])
            return Embedding(**doc)
        return None

    async def vector_search(
        self,
        query_text: Optional[str] = None,
        query_vector: Optional[List[float]] = None,
        limit: int = 10,
        min_score: float = 0.7,
    ) -> List[VectorSearchResult]:
        """
        Perform vector similarity search using MongoDB Atlas Vector Search

        Uses 'retrieval_query' task type for optimal search performance when query_text is provided.

        Args:
            query_text: Text to search for similar content (generates embedding automatically)
            query_vector: Pre-generated embedding vector (use this if you already have an embedding)
            limit: Maximum number of results
            min_score: Minimum similarity score (0-1)

        Returns:
            List of search results with similarity scores

        Raises:
            ValueError: If neither query_text nor query_vector is provided

        Note:
            Requires MongoDB Atlas Vector Search index to be created.
            Index configuration:
            {
              "mappings": {
                "dynamic": false,
                "fields": {
                  "embedding": {
                    "type": "knnVector",
                    "dimensions": 3072,
                    "similarity": "cosine"
                  }
                }
              }
            }
        """
        # Validate inputs
        if query_text is None and query_vector is None:
            raise ValueError("Either query_text or query_vector must be provided")

        # Generate embedding if query_text provided
        if query_text is not None:
            query_embedding = self.generate_embedding(query_text, task_type="retrieval_query")
        else:
            query_embedding = query_vector

        # MongoDB Atlas Vector Search aggregation pipeline
        pipeline = [
            {
                "$vectorSearch": {
                    "index": self.VECTOR_INDEX_NAME,
                    "path": "embedding",
                    "queryVector": query_embedding,
                    "numCandidates": limit * 10,  # Oversample for better results
                    "limit": limit,
                }
            },
            {
                "$project": {
                    "conversation_id": 1,
                    "email_id": 1,
                    "text_content": 1,
                    "score": {"$meta": "vectorSearchScore"},
                }
            },
            {"$match": {"score": {"$gte": min_score}}},
        ]

        results = []
        async for doc in self.collection.aggregate(pipeline):
            results.append(
                VectorSearchResult(
                    conversation_id=doc["conversation_id"],
                    email_id=doc["email_id"],
                    text_content=doc["text_content"],
                    score=doc["score"],
                )
            )

        return results

    async def delete(self, embedding_id: str) -> bool:
        """
        Delete an embedding

        Args:
            embedding_id: MongoDB document ID

        Returns:
            True if deleted, False otherwise
        """
        from bson import ObjectId

        try:
            result = await self.collection.delete_one({"_id": ObjectId(embedding_id)})
            return result.deleted_count > 0
        except Exception:
            return False

    async def delete_by_conversation_id(self, conversation_id: str) -> bool:
        """
        Delete embedding by conversation ID

        Args:
            conversation_id: Conversation document ID

        Returns:
            True if deleted, False otherwise
        """
        try:
            result = await self.collection.delete_one({"conversation_id": conversation_id})
            return result.deleted_count > 0
        except Exception:
            return False

    async def count_total(self) -> int:
        """
        Count total embeddings

        Returns:
            Total number of embedding documents
        """
        return await self.collection.count_documents({})

    async def count_embeddings(self) -> int:
        """
        Count total embeddings (alias for count_total)

        Returns:
            Total number of embedding documents
        """
        return await self.count_total()

    def get_vector_search_index_definition(self) -> Dict[str, Any]:
        """
        Get the MongoDB Atlas Vector Search index definition

        Returns:
            Index definition for creating in MongoDB Atlas UI

        Note:
            This is a helper method. The index must be created manually in Atlas UI:
            1. Go to Atlas UI > Database > Search
            2. Create Search Index
            3. Choose "JSON Editor"
            4. Use the returned definition
        """
        return {
            "mappings": {
                "dynamic": False,
                "fields": {
                    "embedding": {
                        "type": "knnVector",
                        "dimensions": self.settings.embedding_dimensions,
                        "similarity": "cosine",
                    }
                },
            }
        }
