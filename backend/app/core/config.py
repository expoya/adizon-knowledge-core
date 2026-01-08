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
    
    # Public URL for callbacks (used by external services like ingestion worker)
    public_url: str = Field(default="http://localhost:8000", alias="PUBLIC_URL")

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
    # PostgreSQL + pgvector (Internal - for backend's own DB access)
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
    # Neo4j (Internal - for backend's own access)
    # -------------------------------------------------------------------------
    neo4j_uri: str = Field(default="bolt://localhost:7687", alias="NEO4J_URI")
    neo4j_user: str = Field(default="neo4j", alias="NEO4J_USER")
    neo4j_password: str = Field(default="password", alias="NEO4J_PASSWORD")

    # -------------------------------------------------------------------------
    # MinIO / S3 (Internal - for backend's own access)
    # -------------------------------------------------------------------------
    minio_endpoint: str = Field(default="localhost:9000", alias="MINIO_ENDPOINT")
    minio_access_key: str = Field(default="minioadmin", alias="MINIO_ACCESS_KEY")
    minio_secret_key: str = Field(default="minioadmin", alias="MINIO_SECRET_KEY")
    minio_bucket_name: str = Field(default="knowledge-documents", alias="MINIO_BUCKET_NAME")
    minio_secure: bool = Field(default=False, alias="MINIO_SECURE")

    # -------------------------------------------------------------------------
    # Worker Connection Settings (Public URLs for external Worker access)
    # These are the URLs the Trooper Worker uses to connect to services.
    # If not set, falls back to internal URLs (works for local dev).
    # -------------------------------------------------------------------------
    # PostgreSQL - Public URL for Worker
    worker_postgres_host: str | None = Field(default=None, alias="WORKER_POSTGRES_HOST")
    worker_postgres_port: int | None = Field(default=None, alias="WORKER_POSTGRES_PORT")
    worker_postgres_db: str | None = Field(default=None, alias="WORKER_POSTGRES_DB")
    worker_postgres_user: str | None = Field(default=None, alias="WORKER_POSTGRES_USER")
    worker_postgres_password: str | None = Field(default=None, alias="WORKER_POSTGRES_PASSWORD")

    # Neo4j - Public URL for Worker
    worker_neo4j_uri: str | None = Field(default=None, alias="WORKER_NEO4J_URI")
    worker_neo4j_user: str | None = Field(default=None, alias="WORKER_NEO4J_USER")
    worker_neo4j_password: str | None = Field(default=None, alias="WORKER_NEO4J_PASSWORD")

    # MinIO - Public URL for Worker
    worker_minio_endpoint: str | None = Field(default=None, alias="WORKER_MINIO_ENDPOINT")
    worker_minio_access_key: str | None = Field(default=None, alias="WORKER_MINIO_ACCESS_KEY")
    worker_minio_secret_key: str | None = Field(default=None, alias="WORKER_MINIO_SECRET_KEY")
    worker_minio_bucket_name: str | None = Field(default=None, alias="WORKER_MINIO_BUCKET_NAME")
    worker_minio_secure: bool | None = Field(default=None, alias="WORKER_MINIO_SECURE")

    # Helper methods to get Worker configs (with fallback to internal)
    def get_worker_postgres_config(self) -> dict:
        """Get PostgreSQL config for Worker (public URLs with fallback to internal)."""
        return {
            "host": self.worker_postgres_host or self.postgres_host,
            "port": self.worker_postgres_port or self.postgres_port,
            "database": self.worker_postgres_db or self.postgres_db,
            "user": self.worker_postgres_user or self.postgres_user,
            "password": self.worker_postgres_password or self.postgres_password,
        }

    def get_worker_neo4j_config(self) -> dict:
        """Get Neo4j config for Worker (public URLs with fallback to internal)."""
        return {
            "uri": self.worker_neo4j_uri or self.neo4j_uri,
            "user": self.worker_neo4j_user or self.neo4j_user,
            "password": self.worker_neo4j_password or self.neo4j_password,
        }

    def get_worker_minio_config(self) -> dict:
        """Get MinIO config for Worker (public URLs with fallback to internal)."""
        return {
            "endpoint": self.worker_minio_endpoint or self.minio_endpoint,
            "access_key": self.worker_minio_access_key or self.minio_access_key,
            "secret_key": self.worker_minio_secret_key or self.minio_secret_key,
            "bucket_name": self.worker_minio_bucket_name or self.minio_bucket_name,
            "secure": self.worker_minio_secure if self.worker_minio_secure is not None else self.minio_secure,
        }

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
    # Ontology Configuration (Multi-Tenant Support)
    # The ontology YAML is stored in MinIO and loaded dynamically.
    # -------------------------------------------------------------------------
    ontology_minio_path: str = Field(
        default="ontology/ontology.yaml",
        alias="ONTOLOGY_MINIO_PATH",
        description="Path to ontology YAML in MinIO bucket (e.g., 'ontology/ontology.yaml')",
    )

    # -------------------------------------------------------------------------
    # Trooper Worker (Compute-Intensive Microservice)
    # -------------------------------------------------------------------------
    trooper_url: str = Field(
        default="http://localhost:8001",
        alias="TROOPER_URL",
    )
    trooper_auth_token: str | None = Field(
        default=None,
        alias="TROOPER_AUTH_TOKEN",
    )

    # -------------------------------------------------------------------------
    # OpenAI (optional, legacy)
    # -------------------------------------------------------------------------
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")

    # -------------------------------------------------------------------------
    # CRM Integration (Plugin System)
    # -------------------------------------------------------------------------
    active_crm_provider: str | None = Field(
        default="zoho",
        alias="ACTIVE_CRM_PROVIDER",
        description="Active CRM provider: 'zoho', 'salesforce', 'hubspot', or 'none'",
    )

    # Zoho CRM Configuration
    zoho_client_id: str | None = Field(
        default=None,
        alias="ZOHO_CLIENT_ID",
        description="Zoho OAuth2 Client ID",
    )
    zoho_client_secret: str | None = Field(
        default=None,
        alias="ZOHO_CLIENT_SECRET",
        description="Zoho OAuth2 Client Secret",
    )
    zoho_refresh_token: str | None = Field(
        default=None,
        alias="ZOHO_REFRESH_TOKEN",
        description="Zoho OAuth2 Refresh Token (long-lived)",
    )
    zoho_api_base_url: str = Field(
        default="https://www.zohoapis.eu",
        alias="ZOHO_API_BASE_URL",
        description="Zoho API base URL (region-specific: .com, .eu, .in, etc.)",
    )


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
