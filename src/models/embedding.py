"""
Embedding data model for conversation embeddings

Represents vector embeddings generated from email conversations
"""

from datetime import datetime as dt
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class Embedding(BaseModel):
    """Conversation embedding model"""

    model_config = ConfigDict(
        populate_by_name=True,
        json_encoders={dt: lambda v: v.isoformat()}
    )

    # MongoDB will generate this, but we can accept it for updates
    id: Optional[str] = Field(None, alias="_id", description="MongoDB document ID")

    conversation_id: str = Field(..., description="Reference to conversation document")
    email_id: str = Field(..., description="Gmail message ID for reference")

    # Embedding vector
    embedding: List[float] = Field(..., description="Embedding vector (3072 dimensions)")

    # Metadata for vector search
    text_content: str = Field(
        ..., description="Original text used to generate embedding"
    )
    embedding_model: str = Field(
        default="gemini-embedding-001", description="Model used for embedding"
    )
    embedding_dimensions: int = Field(
        default=3072, description="Embedding vector dimensions"
    )

    # Additional metadata (from, to, cc, subject, datetime)
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Email metadata (from, to, cc, subject, datetime)"
    )

    # Timestamps
    created_at: Optional[dt] = Field(
        None, description="Embedding creation timestamp"
    )


class EmbeddingCreate(BaseModel):
    """Model for creating a new embedding"""

    model_config = ConfigDict(populate_by_name=True)

    conversation_id: str
    email_id: str
    embedding: List[float]
    text_content: str
    embedding_model: str = "gemini-embedding-001"
    embedding_dimensions: int = 3072
    metadata: Optional[Dict[str, Any]] = None


class VectorSearchResult(BaseModel):
    """Model for vector search results"""

    model_config = ConfigDict(populate_by_name=True)

    conversation_id: str
    email_id: str
    text_content: str
    score: float = Field(..., description="Similarity score (0-1)")
    metadata: dict = Field(default_factory=dict, description="Additional metadata")
