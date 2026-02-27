"""
Agents module for conversation orchestration

Provides agent-based architecture for email conversation management:
- Conversation Orchestrator: Central message broker and routing
- Shared Infrastructure: MessageBus, AgentRegistry, AgentBase
"""

from src.agents.orchestrator.orchestrator import ConversationOrchestrator
from src.agents.message_bus import MessageBus, Message, MessageType
from src.agents.agent_registry import AgentRegistry, AgentInfo
from src.agents.agent_base import AgentBase

__all__ = [
    "ConversationOrchestrator",
    "MessageBus",
    "Message",
    "MessageType",
    "AgentRegistry",
    "AgentInfo",
    "AgentBase",
]
