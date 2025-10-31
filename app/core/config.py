from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env.local",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Database
    database_url: str = Field(default="postgresql://postgres:postgres@localhost:5432/arbeit")
    
    # Redis
    redis_url: str = Field(default="redis://localhost:6379")
    
    # Security
    jwt_secret: str = Field(default="your-super-secret-jwt-key-here-change-in-production")
    jwt_algorithm: str = Field(default="HS256")
    jwt_access_token_expire_minutes: int = Field(default=30)
    jwt_refresh_token_expire_days: int = Field(default=30)
    
    # Email
    email_api_key: str = Field(default="")
    resend_api_key: str = Field(default="")
    frontend_url: str = Field(default="http://localhost:3000")
    
    # Alerts (Optional)
    slack_webhook_url: str = Field(default="")
    
    # Application
    log_level: str = Field(default="INFO")
    debug: bool = Field(default=False)
    
    # CORS
    cors_origins: list[str] = Field(default=["http://localhost:3000", "http://localhost:8000"])


# Global settings instance
settings = Settings()