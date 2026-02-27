"""
Conversation data model for email conversations

Represents an email conversation stored in MongoDB
"""

from datetime import datetime as dt
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class EmailAttachment(BaseModel):
    """Email attachment metadata"""

    filename: str = Field(..., description="Original filename")
    content_type: str = Field(..., description="MIME type")
    size_bytes: int = Field(..., description="File size in bytes")
    storage_path: Optional[str] = Field(None, description="Path to stored file")


class Conversation(BaseModel):
    """Email conversation model"""

    model_config = ConfigDict(
        populate_by_name=True,
        json_encoders={dt: lambda v: v.isoformat()}
    )

    # MongoDB will generate this, but we can accept it for updates
    id: Optional[str] = Field(None, alias="_id", description="MongoDB document ID")

    email_id: str = Field(..., description="Gmail message ID (unique)")
    to: str = Field(..., description="Recipient email (client identifier)")
    from_email: str = Field(..., alias="from", description="Sender email address")
    cc: Optional[str] = Field(None, description="CC email addresses")
    subject: str = Field(..., description="Email subject line")
    body: str = Field(..., description="Email body content (plain text)")
    attachments: List[EmailAttachment] = Field(
        default_factory=list, description="Email attachments"
    )
    datetime: dt = Field(..., description="Email received timestamp (UTC)")

    # Metadata
    thread_id: Optional[str] = Field(None, description="Gmail thread ID")
    labels: List[str] = Field(default_factory=list, description="Gmail labels")
    is_processed: bool = Field(default=False, description="Processing status")
    created_at: Optional[dt] = Field(
        None, description="Record creation timestamp"
    )
    updated_at: Optional[dt] = Field(
        None, description="Record update timestamp"
    )


class ConversationCreate(BaseModel):
    """Model for creating a new conversation"""

    model_config = ConfigDict(populate_by_name=True)

    email_id: str
    to: str
    from_email: str = Field(..., alias="from")
    cc: Optional[str] = None
    subject: str
    body: str
    attachments: List[EmailAttachment] = Field(default_factory=list)
    datetime: dt
    thread_id: Optional[str] = None
    labels: List[str] = Field(default_factory=list)


class ConversationUpdate(BaseModel):
    """Model for updating a conversation"""

    model_config = ConfigDict(populate_by_name=True)

    subject: Optional[str] = None
    body: Optional[str] = None
    attachments: Optional[List[EmailAttachment]] = None
    labels: Optional[List[str]] = None
    is_processed: Optional[bool] = None
    updated_at: Optional[dt] = None
