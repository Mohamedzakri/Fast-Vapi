from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings and configuration"""

    # Application
    APP_NAME: str = "FastAPI Web Scraper"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # MongoDB
    MONGODB_URL: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "web_scraper_db"

    # Scraping
    USE_SELENIUM: bool = True
    SCRAPING_TIMEOUT: int = 30
    MAX_CONTENT_LENGTH: int = 10_000_000  # 10MB

    # Rate Limiting (requests per minute)
    RATE_LIMIT_PER_MINUTE: int = 10

    # Logging
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
