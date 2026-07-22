"""
Configuration management for the AI Research Assistant backend.
Loads environment variables and provides configuration objects.
Uses Pydantic Settings for validation and type safety.
"""

import os
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field, validator


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    Why Pydantic Settings?
    - Type validation: All config values are validated at startup
    - Automatic conversion: Strings to integers, bools, etc.
    - Hierarchical: Support for .env files and environment variables
    - IDE support: Full type hints for autocomplete
    """

    # ==== APP SETTINGS ====
    APP_NAME: str = "AI Research Assistant"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = Field(default=False, description="Debug mode")
    ENVIRONMENT: str = Field(default="development",
                             description="production|development|testing")

    # ==== SERVER SETTINGS ====
    HOST: str = Field(default="0.0.0.0", description="Server host")
    PORT: int = Field(default=8000, description="Server port")
    RELOAD: bool = Field(
        default=True, description="Auto-reload on code changes")

    # ==== DATABASE (PostgreSQL) ====
    # Production URL: postgresql://user:password@host:port/database
    # Local: postgresql://postgres:password@localhost:5432/ai_research
    DATABASE_URL: str = Field(
        default="postgresql://postgres:password@localhost:5432/ai_research",
        description="PostgreSQL connection URL"
    )
    DATABASE_ECHO: bool = Field(default=False, description="Log SQL queries")
    DATABASE_POOL_SIZE: int = Field(
        default=20, description="Connection pool size")
    DATABASE_MAX_OVERFLOW: int = Field(
        default=10, description="Max overflow connections")

    # ==== CACHE (Redis) ====
    # Production: redis://password@host:port/db
    # Local: redis://localhost:6379/0
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL"
    )
    REDIS_CACHE_TTL: int = Field(
        default=300, description="Default cache TTL in seconds")

    # ==== VECTOR DATABASE (ChromaDB) ====
    CHROMA_PERSIST_DIR: str = Field(
        default="./data/chroma",
        description="ChromaDB persistence directory"
    )
    EMBEDDING_MODEL: str = Field(
        default="BAAI/bge-base-en-v1.5",
        description="Sentence-transformer model for embeddings"
    )
    EMBEDDING_DIMENSION: int = Field(
        default=768, description="Embedding vector dimension")

    # ==== FILE UPLOAD ====
    UPLOAD_DIR: str = Field(default="./uploads",
                            description="PDF upload directory")
    MAX_FILE_SIZE_MB: int = Field(
        default=50, description="Max file size in MB")
    ALLOWED_EXTENSIONS: list = Field(
        default=["pdf"], description="Allowed file extensions")

    # ==== CHUNKING STRATEGY ====
    CHUNK_SIZE: int = Field(default=1024, description="Chunk size in tokens")
    CHUNK_OVERLAP: int = Field(
        default=128, description="Chunk overlap in tokens")

    # ==== LLM SETTINGS ====
    LLM_PROVIDER: str = Field(default="openai", description="openai|ollama")
    OPENAI_API_KEY: Optional[str] = Field(
        default=None, description="OpenAI API key")
    OPENAI_MODEL: str = Field(default="gpt-4", description="OpenAI model")
    OPENAI_TEMPERATURE: float = Field(
        default=0.7, description="Temperature for LLM")
    OPENAI_MAX_TOKENS: int = Field(
        default=2000, description="Max tokens per response")

    # Ollama (local LLM)
    OLLAMA_BASE_URL: str = Field(
        default="http://localhost:11434", description="Ollama server URL")
    OLLAMA_MODEL: str = Field(
        default="llama2", description="Ollama model name")

    # Google Gemini (free alternative to OpenAI)
    GEMINI_API_KEY: Optional[str] = Field(
        default=None, description="Google Gemini API key (free at aistudio.google.com)")

    # ==== RETRIEVAL SETTINGS ====
    RETRIEVAL_TOP_K: int = Field(
        default=5, description="Number of chunks to retrieve")
    ENABLE_RERANKING: bool = Field(
        default=True, description="Enable cross-encoder reranking")
    RERANKING_MODEL: str = Field(
        default="cross-encoder/ms-marco-MiniLM-L-12-v2",
        description="Cross-encoder model for reranking"
    )
    HYBRID_SEARCH: bool = Field(
        default=True, description="Enable BM25 + vector hybrid search")

    # ==== AUTHENTICATION ====
    # Use: openssl rand -hex 32
    SECRET_KEY: str = Field(
        default="your-secret-key-here-change-in-production",
        description="JWT secret key"
    )
    ALGORITHM: str = Field(default="HS256", description="JWT algorithm")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=15, description="Access token TTL")
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        default=7, description="Refresh token TTL")

    # ==== RATE LIMITING ====
    RATE_LIMIT_ENABLED: bool = Field(
        default=True, description="Enable rate limiting")
    RATE_LIMIT_REQUESTS: int = Field(
        default=100, description="Requests per minute")
    RATE_LIMIT_UPLOAD: int = Field(default=10, description="Uploads per hour")

    # ==== CORS SETTINGS ====
    CORS_ORIGINS: list = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
        description="Allowed CORS origins"
    )
    CORS_ALLOW_CREDENTIALS: bool = Field(
        default=True, description="Allow credentials")

    # ==== WEB SEARCH (Phase 8 - Optional) ====
    SERPER_API_KEY: Optional[str] = Field(
        default=None, description="Serper API key for web search")
    ENABLE_WEB_SEARCH: bool = Field(
        default=False, description="Enable web search agent")

    # ==== LOGGING ====
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    LOG_FILE: Optional[str] = Field(default=None, description="Log file path")

    class Config:
        env_file = ".env"
        case_sensitive = True

    @validator('DATABASE_URL')
    def validate_database_url(cls, v):
        """Validate database URL format."""
        if not v.startswith('postgresql://'):
            raise ValueError('DATABASE_URL must start with postgresql://')
        return v

    @validator('REDIS_URL')
    def validate_redis_url(cls, v):
        """Validate Redis URL format."""
        if not v.startswith('redis://') and not v.startswith('rediss://'):
            raise ValueError('REDIS_URL must start with redis:// or rediss://')
        return v

    @validator('MAX_FILE_SIZE_MB')
    def validate_file_size(cls, v):
        """Ensure file size is reasonable."""
        if v < 1 or v > 500:
            raise ValueError('MAX_FILE_SIZE_MB must be between 1 and 500')
        return v

    @validator('CHUNK_SIZE')
    def validate_chunk_size(cls, v):
        """Ensure chunk size is reasonable."""
        if v < 128 or v > 4096:
            raise ValueError('CHUNK_SIZE must be between 128 and 4096')
        return v

    @property
    def MAX_FILE_SIZE(self) -> int:
        """Convert MAX_FILE_SIZE_MB to bytes."""
        return self.MAX_FILE_SIZE_MB * 1024 * 1024


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Using LRU cache prevents re-parsing .env file on every import.
    This is efficient and ensures all modules use the same config instance.

    Returns:
        Settings: Configuration object
    """
    return Settings()


# Create settings instance for direct import
settings = get_settings()


# ==== PATH CONFIGURATIONS ====
def ensure_directories():
    """
    Create necessary directories if they don't exist.
    Called at application startup.
    """
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)
    os.makedirs("./logs", exist_ok=True)
