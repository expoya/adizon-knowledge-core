"""
Application configuration using Pydantic Settings.
Loads environment variables from .env file.
"""

from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Zentrale Konstante für Vector Collection - MUSS überall gleich sein!
VECTOR_COLLECTION_NAME = "adizon_knowledge_base"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -------------------------------------------------------------------------
    # Application
    # -------------------------------------------------------------------------
    app_env: str = Field(default="development", alias="APP_ENV")
    app_debug: bool = Field(default=True, alias="APP_DEBUG")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")

    # -------------------------------------------------------------------------
    # CORS
    # -------------------------------------------------------------------------
    cors_origins: str = Field(
        default="http://localhost:5173,http://localhost:3000",
        alias="CORS_ORIGINS",
    )

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    # -------------------------------------------------------------------------
    # PostgreSQL + pgvector
    # -------------------------------------------------------------------------
    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5433, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="knowledge_core", alias="POSTGRES_DB")
    postgres_user: str = Field(default="postgres", alias="POSTGRES_USER")
    postgres_password: str = Field(default="postgres", alias="POSTGRES_PASSWORD")
    database_url: str | None = Field(default=None, alias="DATABASE_URL")

    @property
    def async_database_url(self) -> str:
        """Build async database URL for SQLAlchemy."""
        if self.database_url:
            # Ensure we use the async driver
            url = self.database_url
            if url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+psycopg://", 1)
            return url
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # -------------------------------------------------------------------------
    # Neo4j
    # -------------------------------------------------------------------------
    neo4j_uri: str = Field(default="bolt://localhost:7687", alias="NEO4J_URI")
    neo4j_user: str = Field(default="neo4j", alias="NEO4J_USER")
    neo4j_password: str = Field(default="password", alias="NEO4J_PASSWORD")

    # -------------------------------------------------------------------------
    # MinIO / S3
    # -------------------------------------------------------------------------
    minio_endpoint: str = Field(default="localhost:9000", alias="MINIO_ENDPOINT")
    minio_access_key: str = Field(default="minioadmin", alias="MINIO_ACCESS_KEY")
    minio_secret_key: str = Field(default="minioadmin", alias="MINIO_SECRET_KEY")
    minio_bucket_name: str = Field(default="knowledge-documents", alias="MINIO_BUCKET_NAME")
    minio_secure: bool = Field(default=False, alias="MINIO_SECURE")

    # -------------------------------------------------------------------------
    # AI API (OpenAI-compatible endpoint, e.g., Trooper)
    # Used for both embeddings and LLM calls
    # These MUST be set in .env - no OpenAI defaults!
    # -------------------------------------------------------------------------
    embedding_api_url: str = Field(
        ...,  # Required - no default
        alias="EMBEDDING_API_URL",
    )
    embedding_api_key: str = Field(
        ...,  # Required - no default
        alias="EMBEDDING_API_KEY",
    )
    embedding_model: str = Field(
        default="jina/jina-embeddings-v2-base-de",
        alias="EMBEDDING_MODEL",
    )

    # -------------------------------------------------------------------------
    # LLM Model (for graph extraction and other LLM tasks)
    # -------------------------------------------------------------------------
    llm_model_name: str = Field(
        default="adizon-ministral",
        alias="LLM_MODEL_NAME",
    )

    # -------------------------------------------------------------------------
    # OpenAI (optional, legacy)
    # -------------------------------------------------------------------------
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")


@lru_cache
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    Note: Settings are cached! If you change .env, restart the server.
    """
    return Settings()


def clear_settings_cache() -> None:
    """Clear the settings cache. Call this if you need to reload settings."""
    get_settings.cache_clear()
