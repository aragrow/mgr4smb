"""
Agent Registry - Manages available agents

Provides registration and discovery of agents
"""

from typing import Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel


class AgentInfo(BaseModel):
    """Information about a registered agent"""

    name: str
    agent_type: str
    status: str = "active"  # active, inactive, error
    registered_at: datetime = datetime.now()
    last_seen: datetime = datetime.now()
    capabilities: List[str] = []
    metadata: Dict[str, str] = {}


class AgentRegistry:
    """
    Registry for managing available agents

    Tracks agent status, capabilities, and metadata
    """

    def __init__(self):
        """Initialize agent registry"""
        self.agents: Dict[str, AgentInfo] = {}

    def register(self, agent_info: AgentInfo) -> None:
        """
        Register an agent

        Args:
            agent_info: Information about the agent
        """
        self.agents[agent_info.name] = agent_info

    def unregister(self, agent_name: str) -> None:
        """
        Unregister an agent

        Args:
            agent_name: Name of the agent to unregister
        """
        if agent_name in self.agents:
            del self.agents[agent_name]

    def get_agent(self, agent_name: str) -> Optional[AgentInfo]:
        """
        Get information about an agent

        Args:
            agent_name: Name of the agent

        Returns:
            AgentInfo if found, None otherwise
        """
        return self.agents.get(agent_name)

    def list_agents(self, status: Optional[str] = None) -> List[AgentInfo]:
        """
        List all registered agents

        Args:
            status: Optional filter by status

        Returns:
            List of agent information
        """
        if status:
            return [info for info in self.agents.values() if info.status == status]
        return list(self.agents.values())

    def update_status(self, agent_name: str, status: str) -> None:
        """
        Update agent status

        Args:
            agent_name: Name of the agent
            status: New status
        """
        if agent_name in self.agents:
            self.agents[agent_name].status = status
            self.agents[agent_name].last_seen = datetime.now()

    def heartbeat(self, agent_name: str) -> None:
        """
        Update agent last_seen timestamp

        Args:
            agent_name: Name of the agent
        """
        if agent_name in self.agents:
            self.agents[agent_name].last_seen = datetime.now()
