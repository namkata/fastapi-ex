import os
from pydantic import BaseSettings
from typing import List
from dotenv import load_dotenv

# Load biến môi trường từ file .env
load_dotenv()


class Settings(BaseSettings):
    # Thông tin cơ bản của dự án
    PROJECT_NAME: str = "FastAPI Example Project"
    PROJECT_DESCRIPTION: str = (
        "FastAPI project with CRUD, file upload, "
        "SeaweedFS and LocalStack S3 integration"
    )
    PROJECT_VERSION: str = "0.1.0"

    # API settings
    API_V1_STR: str = "/api/v1"

    # CORS settings
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]

    # Database settings
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./app.db")

    # JWT settings
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # File upload settings
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS: List[str] = ["jpg", "jpeg", "png", "gif"]

    # SeaweedFS settings
    SEAWEEDFS_MASTER_URL: str = os.getenv(
        "SEAWEEDFS_MASTER_URL", "http://localhost:9333"
    )

    # S3 settings (LocalStack)
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "test")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "test")
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    S3_ENDPOINT_URL: str = os.getenv("S3_ENDPOINT_URL", "http://localhost:4566")
    S3_BUCKET_NAME: str = os.getenv("S3_BUCKET_NAME", "images-bucket")

    # Logging settings
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT: str = "{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
    LOG_FILE: str = "logs/app.log"
    LOG_ROTATION: str = "1 day"
    LOG_RETENTION: str = "7 days"

    class Config:
        env_file = ".env"
        case_sensitive = True


# Khởi tạo đối tượng settings
settings = Settings()
