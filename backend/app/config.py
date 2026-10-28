from pathlib import Path
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    DATABASE_URL: str = "sqlite+aiosqlite:///./sih_prototype.db"
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 10
    MAX_PAGES: int = 20
    API_PREFIX: str = "/api"
    DEBUG: bool = True
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000"

    # Authentication settings
    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    COOKIE_SECURE: bool = False
    RATE_LIMIT_ENABLED: bool = True

    # Feature flags
    ENABLE_SHADOW_DECLARATIVE_ENGINE: bool = False

    # One-time admin setup token for reviewer account creation
    ADMIN_SETUP_TOKEN: str = "pramaan-admin-setup-secret-token-2026"

    # Seed credentials
    REVIEWER_EMAIL: str = "reviewer@aicte-india.org"
    REVIEWER_PASSWORD: str = "Reviewer@AICTE2026"
    DEMO_INSTITUTION_EMAIL: str = "institution@engg-college.edu.in"
    DEMO_INSTITUTION_PASSWORD: str = "College@Pramaan2026"

    @model_validator(mode="after")
    def validate_jwt_secret(self):
        if not self.DEBUG and not self.JWT_SECRET_KEY:
            raise ValueError("JWT_SECRET_KEY must be set when DEBUG is False")
        if not self.JWT_SECRET_KEY:
            self.JWT_SECRET_KEY = "dev-insecure-secret-key-do-not-use-in-production-sih2026"
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def max_file_size_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

    @property
    def upload_path(self) -> Path:
        p = Path(self.UPLOAD_DIR)
        p.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()

