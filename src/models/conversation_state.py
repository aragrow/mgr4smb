"""
Conversation State Model - Track conversation lifecycle across email and phone

Provides comprehensive state tracking for conversations including:
- Multi-channel support (email, phone)
- Event logging for all agent decisions
- Checkpoints for resume capability
- Analytics and review support
"""

from datetime import datetime as dt
from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field
from uuid import uuid4


class ConversationEvent(BaseModel):
    """
    Individual event within a conversation

    Captures agent decisions, LLM calls, worker actions, and state changes
    """
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: dt = Field(default_factory=dt.utcnow)

    # Event type classification
    type: Literal[
        "email_received",
        "call_received",
        "agent_routed",
        "llm_call",
        "agent_classification",
        "worker_call",
        "response_sent",
        "call_transferred",
        "checkpoint_created",
        "error"
    ]

    # Agent that generated this event
    agent_name: Optional[str] = None

    # Event-specific data
    data: Dict[str, Any] = Field(default_factory=dict)

    # State snapshot for resume capability
    checkpoint: Optional[Dict[str, Any]] = None


class ConversationCheckpoint(BaseModel):
    """
    State snapshot for resuming conversations

    Contains everything needed to restore conversation state
    """
    timestamp: dt = Field(default_factory=dt.utcnow)
    current_agent: str
    state: Literal["in_progress", "completed", "timeout", "error"]
    next_action: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)
    pending_actions: List[str] = Field(default_factory=list)


class ConversationMetadata(BaseModel):
    """
    Aggregated metadata about the conversation

    Used for quick querying and analytics
    """
    total_events: int = 0
    agents_involved: List[str] = Field(default_factory=list)
    llm_calls: int = 0
    total_tokens: int = 0
    processing_duration_ms: Optional[int] = None

    # Channel-specific metadata
    call_duration_seconds: Optional[int] = None  # For phone conversations


class ConversationState(BaseModel):
    """
    Complete conversation state tracking

    Supports both email and phone conversations with full event history,
    checkpoints for resume capability, and metadata for analytics.

    Examples:
        Email conversation:
            state = ConversationState(
                channel="email",
                email_id="gmail-msg-123",
                thread_id="thread-456",
                contact_identifier="client@example.com",
                contact_name="John Doe",
                classification="client"
            )

        Phone conversation:
            state = ConversationState(
                channel="phone",
                call_id="ghl-call-789",
                phone_number="+13055551234",
                contact_identifier="+13055551234",
                contact_name="Jane Smith",
                classification="client"
            )
    """
    # MongoDB ID
    id: Optional[str] = Field(None, alias="_id")

    # Session identification
    session_id: str = Field(default_factory=lambda: str(uuid4()))

    # Channel identification
    channel: Literal["email", "phone"]

    # Email-specific fields (required if channel=email)
    email_id: Optional[str] = None
    thread_id: Optional[str] = None

    # Phone-specific fields (required if channel=phone)
    call_id: Optional[str] = None
    phone_number: Optional[str] = None
    call_duration: Optional[int] = None  # seconds
    call_direction: Optional[Literal["inbound", "outbound"]] = None

    # Common contact identification
    contact_identifier: str  # Email address OR phone number
    contact_name: Optional[str] = None
    classification: Optional[Literal["client", "vendor", "lead"]] = None

    # Conversation status
    status: Literal["in_progress", "completed", "timeout", "error"] = "in_progress"

    # Event history
    events: List[ConversationEvent] = Field(default_factory=list)

    # Resume capability
    last_checkpoint: Optional[ConversationCheckpoint] = None

    # Aggregated metadata
    metadata: ConversationMetadata = Field(default_factory=ConversationMetadata)

    # Timestamps
    created_at: dt = Field(default_factory=dt.utcnow)
    updated_at: dt = Field(default_factory=dt.utcnow)
    completed_at: Optional[dt] = None
    timeout_at: Optional[dt] = None

    class Config:
        populate_by_name = True
        json_encoders = {
            dt: lambda v: v.isoformat()
        }

    def add_event(
        self,
        event_type: str,
        agent_name: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        checkpoint: Optional[Dict[str, Any]] = None
    ) -> ConversationEvent:
        """
        Add an event to the conversation history

        Args:
            event_type: Type of event
            agent_name: Agent that generated the event
            data: Event-specific data
            checkpoint: Optional state snapshot

        Returns:
            The created event
        """
        event = ConversationEvent(
            type=event_type,
            agent_name=agent_name,
            data=data or {},
            checkpoint=checkpoint
        )

        self.events.append(event)
        self.updated_at = dt.utcnow()

        # Update metadata
        self.metadata.total_events = len(self.events)
        if agent_name and agent_name not in self.metadata.agents_involved:
            self.metadata.agents_involved.append(agent_name)
        if event_type == "llm_call":
            self.metadata.llm_calls += 1
            if "total_tokens" in (data or {}):
                self.metadata.total_tokens += data["total_tokens"]

        return event

    def create_checkpoint(
        self,
        current_agent: str,
        state: str,
        next_action: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        pending_actions: Optional[List[str]] = None
    ) -> ConversationCheckpoint:
        """
        Create a state checkpoint for resume capability

        Args:
            current_agent: Agent currently handling conversation
            state: Current conversation state
            next_action: Next action to take
            context: Contextual information
            pending_actions: List of pending actions

        Returns:
            The created checkpoint
        """
        checkpoint = ConversationCheckpoint(
            current_agent=current_agent,
            state=state,
            next_action=next_action,
            context=context or {},
            pending_actions=pending_actions or []
        )

        self.last_checkpoint = checkpoint
        self.updated_at = dt.utcnow()

        return checkpoint

    def mark_completed(self) -> None:
        """Mark conversation as completed"""
        self.status = "completed"
        self.completed_at = dt.utcnow()
        self.updated_at = dt.utcnow()

        # Calculate processing duration
        if self.created_at and self.completed_at:
            duration = (self.completed_at - self.created_at).total_seconds() * 1000
            self.metadata.processing_duration_ms = int(duration)

    def mark_timeout(self, timeout_at: Optional[dt] = None) -> None:
        """
        Mark conversation as timed out

        Args:
            timeout_at: When the timeout occurred (defaults to now)
        """
        self.status = "timeout"
        self.timeout_at = timeout_at or dt.utcnow()
        self.updated_at = dt.utcnow()

    def mark_error(self, error_data: Optional[Dict[str, Any]] = None) -> None:
        """
        Mark conversation as errored

        Args:
            error_data: Optional error details
        """
        self.status = "error"
        self.updated_at = dt.utcnow()

        # Log error event
        self.add_event(
            event_type="error",
            data=error_data or {}
        )

    def get_duration_ms(self) -> Optional[int]:
        """
        Get conversation duration in milliseconds

        Returns:
            Duration in ms, or None if not completed
        """
        if self.completed_at:
            return int((self.completed_at - self.created_at).total_seconds() * 1000)
        return None

    def get_events_by_type(self, event_type: str) -> List[ConversationEvent]:
        """
        Get all events of a specific type

        Args:
            event_type: Type of event to filter

        Returns:
            List of matching events
        """
        return [e for e in self.events if e.type == event_type]

    def get_events_by_agent(self, agent_name: str) -> List[ConversationEvent]:
        """
        Get all events from a specific agent

        Args:
            agent_name: Name of agent

        Returns:
            List of matching events
        """
        return [e for e in self.events if e.agent_name == agent_name]
