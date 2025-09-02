"""
Configuration management using Pydantic BaseSettings
Loads configuration from environment variables with sensible defaults
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from typing import Optional
from pathlib import Path


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    Uses Pydantic v2 BaseSettings for automatic env var loading.
    """

    # Environment
    ENVIRONMENT: str = Field(
        default="development", description="Environment (development, staging, production)"
    )

    LOG_LEVEL: str = Field(default="INFO", description="Logging level")

    # Paths
    OUTPUT_DIR: Path = Field(default=Path("outputs"), description="Directory for JSON output files")

    # Output Management Configuration
    OUTPUT_INCLUDE_PERSON_NAME: bool = Field(
        default=True, description="Include person name in output filenames"
    )

    OUTPUT_RETENTION_DAYS: Optional[int] = Field(
        default=None, description="Number of days to retain output files (None = keep forever)"
    )

    OUTPUT_CLEANUP_ON_STARTUP: bool = Field(
        default=False, description="Clean up old output files on application startup"
    )

    OUTPUT_DETAILED_LOGGING: bool = Field(
        default=True, description="Include detailed processing logs in output metadata"
    )

    # Firecrawl Configuration
    FIRECRAWL_API_KEY: Optional[str] = Field(
        default=None, description="Firecrawl API key (optional - will work without it)"
    )

    FIRECRAWL_API_URL: str = Field(
        default="https://api.firecrawl.dev/v2", description="Firecrawl API base URL (v2)"
    )

    FIRECRAWL_MAX_URLS: int = Field(default=50, description="Maximum URLs to discover during crawl")

    FIRECRAWL_TIMEOUT: int = Field(
        default=30, description="Timeout for Firecrawl API calls in seconds"
    )

    # Firecrawl Resilience Configuration
    FIRECRAWL_MAX_RETRIES: int = Field(
        default=3, description="Maximum retries for failed Firecrawl requests"
    )

    FIRECRAWL_BASE_DELAY_SECONDS: float = Field(
        default=1.0, description="Base delay for exponential backoff in seconds"
    )

    FIRECRAWL_MAX_DELAY_SECONDS: int = Field(
        default=60, description="Maximum delay for exponential backoff in seconds"
    )

    FIRECRAWL_REQUESTS_PER_MINUTE: int = Field(
        default=30, description="Rate limit for Firecrawl API requests per minute"
    )

    # Firecrawl v2 Async Crawl Configuration
    FIRECRAWL_CRAWL_POLL_INTERVAL: int = Field(
        default=2, description="Seconds between crawl job status polls"
    )

    FIRECRAWL_CRAWL_MAX_WAIT: int = Field(
        default=300, description="Maximum seconds to wait for crawl completion (5 minutes)"
    )

    # Inngest Configuration
    INNGEST_APP_ID: Optional[str] = Field(
        default="astral-assessment", description="Inngest application ID"
    )

    INNGEST_EVENT_KEY: Optional[str] = Field(
        default=None, description="Inngest event key for authentication"
    )

    INNGEST_BASE_URL: str = Field(
        default="https://api.inngest.com", description="Inngest API base URL"
    )

    INNGEST_IS_PRODUCTION: bool = Field(
        default=False, description="Whether Inngest is in production mode"
    )

    # Inngest Event Names (consistent naming for events)
    INNGEST_REGISTER_EVENT: str = Field(
        default="user.registration.requested", description="Event name for registration workflow"
    )

    INNGEST_SIGNING_KEY: Optional[str] = Field(
        default=None, description="Inngest webhook signing key for signature validation"
    )

    # API Configuration
    API_HOST: str = Field(default="0.0.0.0", description="API host")

    API_PORT: int = Field(default=8000, description="API port")

    # HTTP Client Configuration
    HTTP_TIMEOUT: int = Field(default=30, description="Default HTTP client timeout in seconds")

    HTTP_MAX_RETRIES: int = Field(default=3, description="Maximum number of HTTP retries")

    # LinkedIn Configuration (for future implementation)
    LINKEDIN_API_KEY: Optional[str] = Field(
        default=None, description="LinkedIn API key (not implemented yet)"
    )

    # Business Intelligence URL Filtering
    BI_URL_LIMIT: int = Field(
        default=7, description="Maximum number of URLs to keep after filtering"
    )

    BI_VALUABLE_PATHS: str = Field(
        default="about,our-approach,team,leadership,services,solutions,case-studies,customers,blog,investors,culture,portfolio,clients,work,projects",
        description="Comma-separated list of valuable path segments for BI",
    )

    BI_EXCLUDED_PATHS: str = Field(
        default="privacy,terms,cookie,careers,contact,login,signup,register,press-kit,media-kit,legal,disclaimer,accessibility,sitemap",
        description="Comma-separated list of paths to exclude",
    )

    @field_validator("OUTPUT_DIR")
    @classmethod
    def validate_output_dir(cls, v: Path) -> Path:
        """Ensure OUTPUT_DIR is a Path object"""
        if isinstance(v, str):
            return Path(v)
        return v

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Ensure log level is valid"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v = v.upper()
        if v not in valid_levels:
            raise ValueError(f"LOG_LEVEL must be one of {valid_levels}")
        return v

    @property
    def valuable_paths_list(self) -> list[str]:
        """Convert comma-separated valuable paths to list"""
        return [p.strip() for p in self.BI_VALUABLE_PATHS.split(",") if p.strip()]

    @property
    def excluded_paths_list(self) -> list[str]:
        """Convert comma-separated excluded paths to list"""
        return [p.strip() for p in self.BI_EXCLUDED_PATHS.split(",") if p.strip()]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",  # Ignore extra environment variables
    )


# Create a singleton instance
settings = Settings()

# Export commonly used values for convenience
OUTPUT_DIR = settings.OUTPUT_DIR
FIRECRAWL_API_KEY = settings.FIRECRAWL_API_KEY
INNGEST_APP_ID = settings.INNGEST_APP_ID
