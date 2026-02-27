"""
Agent Prompt data model

Stores prompts for agents to use for intent classification and processing
"""

from datetime import datetime as dt
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class AgentPrompt(BaseModel):
    """Agent prompt model"""

    model_config = ConfigDict(
        populate_by_name=True,
        json_encoders={dt: lambda v: v.isoformat()}
    )

    # MongoDB will generate this
    id: Optional[str] = Field(None, alias="_id", description="MongoDB document ID")

    agent_name: str = Field(..., description="Agent name (orchestrator, manager_agent, lead_agent, etc.)")
    prompt_type: str = Field(..., description="Prompt type (intent_classification, processing, etc.)")

    # Prompt content
    system_prompt: str = Field(..., description="System prompt for the agent")
    user_prompt_template: str = Field(..., description="User prompt template with variables")

    # Configuration
    model: str = Field(default="gemini-2.5-flash", description="LLM model to use")
    temperature: float = Field(default=0.3, description="Temperature for LLM (0.0-1.0)")
    max_tokens: int = Field(default=500, description="Maximum tokens in response")

    # Metadata
    description: str = Field(..., description="Description of what this prompt does")
    examples: Optional[Dict[str, Any]] = Field(None, description="Example inputs/outputs")

    # Timestamps
    created_at: Optional[dt] = Field(None, description="Prompt creation timestamp")
    updated_at: Optional[dt] = Field(None, description="Prompt last update timestamp")
    version: int = Field(default=1, description="Prompt version number")


class AgentPromptCreate(BaseModel):
    """Model for creating a new agent prompt"""

    model_config = ConfigDict(populate_by_name=True)

    agent_name: str
    prompt_type: str
    system_prompt: str
    user_prompt_template: str
    model: str = "gemini-2.5-flash"
    temperature: float = 0.3
    max_tokens: int = 500
    description: str
    examples: Optional[Dict[str, Any]] = None
    version: int = 1


class AgentPromptUpdate(BaseModel):
    """Model for updating an agent prompt"""

    model_config = ConfigDict(populate_by_name=True)

    system_prompt: Optional[str] = None
    user_prompt_template: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    description: Optional[str] = None
    examples: Optional[Dict[str, Any]] = None
    version: Optional[int] = None
