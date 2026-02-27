"""
Application settings using pydantic-settings

Loads environment variables from .env.local file
"""

import os
from functools import lru_cache
from typing import Optional

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # MongoDB Atlas Configuration
    mongodb_uri: str = Field(
        ...,
        alias="MONGODB_URI",
        description="MongoDB Atlas connection URI",
    )
    mongodb_database: str = Field(
        default="conversation_agent",
        alias="MONGODB_DATABASE",
        description="MongoDB database name",
    )
    mongodb_max_pool_size: int = Field(
        default=50,
        alias="MONGODB_MAX_POOL_SIZE",
        description="Maximum connection pool size",
    )
    mongodb_min_pool_size: int = Field(
        default=10,
        alias="MONGODB_MIN_POOL_SIZE",
        description="Minimum connection pool size",
    )

    # Environment
    env: str = Field(
        default="development",
        alias="ENV",
        description="Environment (development, staging, production)",
    )

    # Google Gemini API Configuration
    google_api_key: str = Field(
        ...,
        alias="GOOGLE_API_KEY",
        description="Google API key for Gemini embeddings",
    )
    google_model: str = Field(
        default="gemini-2.5-flash",
        alias="GOOGLE_MODEL",
        description="Google Gemini model name for LLM generation",
    )
    llm_max_response_tokens: int = Field(
        default=8192,
        alias="LLM_MAX_RESPONSE_TOKENS",
        description="Maximum tokens for LLM response generation (API limit)",
    )
    llm_target_response_tokens: int = Field(
        default=200,
        alias="LLM_TARGET_RESPONSE_TOKENS",
        description="Target response length in tokens (used in prompt instruction)",
    )

    # Embedding Configuration
    embedding_model: str = Field(
        default="gemini-embedding-001",
        alias="EMBEDDING_MODEL",
        description="Google Gemini embedding model name",
    )
    embedding_dimensions: int = Field(
        default=3072,
        alias="EMBEDDING_DIMENSIONS",
        description="Embedding vector dimensions (3072 for gemini-embedding-001)",
    )
    embedding_task_type: str = Field(
        default="retrieval_document",
        alias="EMBEDDING_TASK_TYPE",
        description="Task type for embedding generation",
    )
    vector_index_name: str = Field(
        default="vector_search_index_",
        alias="VECTOR_INDEX_NAME",
        description="MongoDB Atlas Vector Search index name for conversations",
    )
    knowledge_vector_index_name: str = Field(
        default="vector_index_knowledge",
        alias="KNOWLEDGE_VECTOR_INDEX_NAME",
        description="MongoDB Atlas Vector Search index name for knowledge base",
    )

    # Gmail API Configuration
    gmail_client_id: str = Field(
        ...,
        alias="GMAIL_CLIENT_ID",
        description="Gmail OAuth 2.0 client ID",
    )
    gmail_client_secret: str = Field(
        ...,
        alias="GMAIL_CLIENT_SECRET",
        description="Gmail OAuth 2.0 client secret",
    )
    gmail_refresh_token: str = Field(
        ...,
        alias="GMAIL_REFRESH_TOKEN",
        description="Gmail OAuth 2.0 refresh token",
    )
    gmail_user_email: str = Field(
        ...,
        alias="GMAIL_USER_EMAIL",
        description="Gmail account email address to monitor",
    )

    # Email Processing Configuration
    email_polling_interval: int = Field(
        default=300,
        alias="EMAIL_POLLING_INTERVAL",
        description="Email polling interval in seconds",
    )
    email_max_results: int = Field(
        default=100,
        alias="EMAIL_MAX_RESULTS",
        description="Maximum emails to fetch per poll",
    )
    email_label_filter: str = Field(
        default="INBOX",
        alias="EMAIL_LABEL_FILTER",
        description="Gmail label to filter",
    )

    # GoHighLevel API Configuration
    ghl_client_id: Optional[str] = Field(
        default=None,
        alias="GHL_CLIENT_ID",
        description="GoHighLevel OAuth 2.0 client ID",
    )
    ghl_client_secret: Optional[str] = Field(
        default=None,
        alias="GHL_CLIENT_SECRET",
        description="GoHighLevel OAuth 2.0 client secret",
    )
    ghl_location_id: Optional[str] = Field(
        default=None,
        alias="GHL_LOCATION_ID",
        description="GoHighLevel location ID (sub-account)",
    )
    ghl_access_token: Optional[str] = Field(
        default=None,
        alias="GHL_ACCESS_TOKEN",
        description="GoHighLevel OAuth 2.0 access token",
    )
    ghl_refresh_token: Optional[str] = Field(
        default=None,
        alias="GHL_REFRESH_TOKEN",
        description="GoHighLevel OAuth 2.0 refresh token",
    )

    # Jobber API Configuration
    jobber_client_id: Optional[str] = Field(
        default=None,
        alias="JOBBER_CLIENT_ID",
        description="Jobber OAuth 2.0 client ID",
    )
    jobber_client_secret: Optional[str] = Field(
        default=None,
        alias="JOBBER_CLIENT_SECRET",
        description="Jobber OAuth 2.0 client secret",
    )
    jobber_access_token: Optional[str] = Field(
        default=None,
        alias="JOBBER_ACCESS_TOKEN",
        description="Jobber OAuth 2.0 access token",
    )
    jobber_refresh_token: Optional[str] = Field(
        default=None,
        alias="JOBBER_REFRESH_TOKEN",
        description="Jobber OAuth 2.0 refresh token",
    )
    jobber_api_version: str = Field(
        default="2025-04-16",
        alias="JOBBER_API_VERSION",
        description="Jobber GraphQL API version",
    )

    # Logging
    log_level: str = Field(
        default="INFO",
        alias="LOG_LEVEL",
        description="Logging level",
    )

    # On-Call Configuration
    on_call_number: str = Field(
        ...,
        alias="ON_CALL_NUMBER",
        description="On-call phone number for URGENT notifications (E.164 format, e.g., +13055551234)",
    )

    # API Security - JWT Configuration
    jwt_secret_key: str = Field(
        default="your-secret-key-change-in-production-min-32-chars",
        alias="JWT_SECRET_KEY",
        description="Secret key for JWT token signing (min 32 characters)",
    )
    jwt_algorithm: str = Field(
        default="HS256",
        alias="JWT_ALGORITHM",
        description="JWT signing algorithm",
    )

    # API Clients - Format: client_id1=secret1,client_id2=secret2
    api_clients_raw: str = Field(
        default="",
        alias="API_CLIENTS",
        description="Comma-separated client_id=secret pairs for API authentication",
    )

    # CORS Origins
    cors_origins_raw: str = Field(
        default="http://localhost:3000,http://localhost:8000",
        alias="CORS_ORIGINS",
        description="Comma-separated allowed CORS origins",
    )

    # API Server Configuration
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")

    model_config = SettingsConfigDict(
        env_file=".env.local",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached application settings

    Returns:
        Settings: Application settings instance
    """
    return Settings()
