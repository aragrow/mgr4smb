"""
Message Bus - Inter-agent communication infrastructure

Provides message passing between agents using async queues
"""

import asyncio
from enum import Enum
from typing import Any, Dict, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class MessageType(str, Enum):
    """Message types for agent communication"""
    GREETING = "greeting"           # Agent hello/registration
    REQUEST = "request"             # Request for action
    RESPONSE = "response"           # Response to request
    NOTIFICATION = "notification"   # Event notification
    ERROR = "error"                 # Error notification


class Message(BaseModel):
    """Message model for agent communication"""

    id: str = Field(default_factory=lambda: f"msg_{datetime.now().timestamp()}")
    type: MessageType
    from_agent: str
    to_agent: Optional[str] = None  # None means broadcast
    payload: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)
    correlation_id: Optional[str] = None  # For tracking request/response pairs


class MessageBus:
    """
    Message bus for agent communication

    Provides async message passing between agents using queues
    """

    def __init__(self):
        """Initialize message bus"""
        self.queues: Dict[str, asyncio.Queue] = {}
        self.broadcast_queue: asyncio.Queue = asyncio.Queue()

    def register_agent(self, agent_name: str) -> None:
        """
        Register an agent to receive messages

        Args:
            agent_name: Unique name of the agent
        """
        if agent_name not in self.queues:
            self.queues[agent_name] = asyncio.Queue()

    def unregister_agent(self, agent_name: str) -> None:
        """
        Unregister an agent

        Args:
            agent_name: Name of the agent to unregister
        """
        if agent_name in self.queues:
            del self.queues[agent_name]

    async def send_message(self, message: Message) -> None:
        """
        Send a message to an agent or broadcast

        Args:
            message: Message to send
        """
        if message.to_agent is None:
            # Broadcast to all agents except sender
            for agent_name, queue in self.queues.items():
                if agent_name != message.from_agent:
                    await queue.put(message)
        else:
            # Send to specific agent
            if message.to_agent in self.queues:
                await self.queues[message.to_agent].put(message)
            else:
                raise ValueError(f"Agent '{message.to_agent}' not registered")

    async def receive_message(self, agent_name: str, timeout: Optional[float] = None) -> Optional[Message]:
        """
        Receive a message for an agent

        Args:
            agent_name: Name of the agent receiving the message
            timeout: Optional timeout in seconds

        Returns:
            Message if available, None if timeout
        """
        if agent_name not in self.queues:
            raise ValueError(f"Agent '{agent_name}' not registered")

        try:
            if timeout:
                message = await asyncio.wait_for(
                    self.queues[agent_name].get(),
                    timeout=timeout
                )
            else:
                message = await self.queues[agent_name].get()
            return message
        except asyncio.TimeoutError:
            return None

    def has_messages(self, agent_name: str) -> bool:
        """
        Check if agent has pending messages

        Args:
            agent_name: Name of the agent

        Returns:
            True if messages are pending
        """
        if agent_name not in self.queues:
            return False
        return not self.queues[agent_name].empty()
