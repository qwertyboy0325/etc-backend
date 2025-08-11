"""Application configuration settings."""

from typing import List, Optional, Union

from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings from environment variables."""

    # Application Configuration
    APP_NAME: str = "ETC Point Cloud Annotation System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    ENVIRONMENT: str = "development"

    # API Configuration
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "your-super-secret-key-here-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Database Configuration
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_NAME: str = "etc_pointcloud_dev"
    DB_USER: str = "root"
    DB_PASSWORD: str = "root"
    DATABASE_URL: Optional[str] = None

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_connection(cls, v: Optional[str], info) -> str:
        """Assemble database URL from components."""
        if isinstance(v, str):
            return v
        values = info.data
        return (
            f"postgresql+asyncpg://{values.get('DB_USER')}:"
            f"{values.get('DB_PASSWORD')}@{values.get('DB_HOST')}:"
            f"{values.get('DB_PORT')}/{values.get('DB_NAME')}"
        )

    # Redis Configuration
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: Optional[str] = None
    REDIS_URL: Optional[str] = None

    @field_validator("REDIS_URL", mode="before")
    @classmethod
    def assemble_redis_connection(cls, v: Optional[str], info) -> str:
        """Assemble Redis URL from components."""
        if isinstance(v, str):
            return v
        values = info.data
        password_part = (
            f":{values.get('REDIS_PASSWORD')}@" if values.get("REDIS_PASSWORD") else ""
        )
        return (
            f"redis://{password_part}{values.get('REDIS_HOST')}:"
            f"{values.get('REDIS_PORT')}/{values.get('REDIS_DB')}"
        )

    # MinIO Configuration
    MINIO_HOST: str = "localhost"
    MINIO_PORT: int = 9000
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "pointcloud-files"
    MINIO_SECURE: bool = False
    MINIO_URL: Optional[str] = None

    @field_validator("MINIO_URL", mode="before")
    @classmethod
    def assemble_minio_connection(cls, v: Optional[str], info) -> str:
        """Assemble MinIO URL from components."""
        if isinstance(v, str):
            return v
        values = info.data
        protocol = "https" if values.get("MINIO_SECURE") else "http"
        return f"{protocol}://{values.get('MINIO_HOST')}:{values.get('MINIO_PORT')}"

    # File Upload Configuration
    MAX_FILE_SIZE: int = 50  # MB
    ALLOWED_FILE_EXTENSIONS: List[str] = [".npy", ".npz"]
    UPLOAD_CHUNK_SIZE: int = 8192  # bytes

    # Celery Configuration
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None

    @field_validator("CELERY_BROKER_URL", mode="before")
    @classmethod
    def assemble_celery_broker(cls, v: Optional[str], info) -> str:
        """Assemble Celery broker URL."""
        if isinstance(v, str):
            return v
        values = info.data
        return values.get("REDIS_URL", "").replace("/0", "/1")

    @field_validator("CELERY_RESULT_BACKEND", mode="before")
    @classmethod
    def assemble_celery_backend(cls, v: Optional[str], info) -> str:
        """Assemble Celery result backend URL."""
        if isinstance(v, str):
            return v
        values = info.data
        return values.get("REDIS_URL", "").replace("/0", "/2")

    # CORS Configuration
    BACKEND_CORS_ORIGINS: List[AnyHttpUrl] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:3002",  # 添加新的端口
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:3002",  # 添加新的端口
        "http://192.168.0.104:3000",
        "http://192.168.0.104:3001",
        "http://192.168.0.104:3002",  # 添加新的端口
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """Parse CORS origins."""
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    # Security Configuration
    BCRYPT_ROUNDS: int = 12
    JWT_ALGORITHM: str = "HS256"

    # Email Configuration (Optional)
    SMTP_TLS: bool = True
    SMTP_PORT: Optional[int] = None
    SMTP_HOST: Optional[str] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    EMAILS_FROM_EMAIL: Optional[str] = "noreply@etc.com"
    EMAILS_FROM_NAME: Optional[str] = "ETC System"

    # Monitoring Configuration
    SENTRY_DSN: Optional[str] = None
    ENABLE_METRICS: bool = False

    # Performance Configuration
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_BURST: int = 10

    # Background Tasks
    TASK_TIMEOUT: int = 300  # seconds
    MAX_RETRIES: int = 3

    # Development Tools
    ENABLE_DOCS: bool = True
    ENABLE_REDOC: bool = True
    ENABLE_OPENAPI_URL: str = "/api/v1/openapi.json"

    # Logging Configuration
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    class Config:
        """Pydantic configuration."""

        env_file = ".env"
        case_sensitive = True


# Create global settings instance
settings = Settings()
