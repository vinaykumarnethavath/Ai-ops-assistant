"""
Configuration management for AI Operations Assistant.
Uses Pydantic Settings for type-safe environment variable handling.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # LLM Settings
    gemini_api_key: str = Field(..., description="Google Gemini API Key")
    gemini_model: str = Field(default="gemini-2.0-flash", description="Gemini model to use")
    
    # API Keys
    github_token: Optional[str] = Field(default=None, description="GitHub Personal Access Token")
    openweathermap_api_key: str = Field(..., description="OpenWeatherMap API Key")
    newsapi_key: str = Field(..., description="NewsAPI Key")
    
    # Application Settings
    log_level: str = Field(default="INFO", description="Logging level")
    cache_ttl_seconds: int = Field(default=300, description="Cache TTL in seconds")
    max_retries: int = Field(default=3, description="Maximum retry attempts for API calls")
    request_timeout: int = Field(default=30, description="Request timeout in seconds")
    
    # Server Settings
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
