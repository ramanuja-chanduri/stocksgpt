from pydantic_settings import BaseSettings
from typing import List
import os
from pathlib import Path


class Settings(BaseSettings):
    # API Keys
    OPENAI_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    
    # Cloud Storage
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str = ""
    
    # Alternative: GCP Storage
    GCP_PROJECT_ID: str = ""
    GCP_STORAGE_BUCKET: str = ""
    USE_GCP: bool = False  # Set to True to use GCP instead of AWS
    
    # API Keys for Tools
    TAVILY_API_KEY: str = ""
    ALPHA_VANTAGE_KEY: str = ""
    
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./stocksgpt.db"
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True
    
    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]
    
    # File Upload
    MAX_FILE_SIZE: int = 20 * 1024 * 1024  # 20MB
    ALLOWED_EXTENSIONS: List[str] = [".jpg", ".jpeg", ".png", ".webp", ".pdf"]
    UPLOAD_DIR: str = "./uploads"
    
    # Vector Store
    VECTOR_STORE_PATH: str = "./vectorstore"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    
    # Session Management
    SESSION_TIMEOUT_HOURS: int = 24
    
    # LLM Models
    GPT_MODEL: str = "gpt-4o"
    GEMINI_MODEL: str = "gemini-2.0-flash-exp"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

# Create necessary directories
Path(settings.UPLOAD_DIR).mkdir(exist_ok=True, parents=True)
Path(settings.VECTOR_STORE_PATH).mkdir(exist_ok=True, parents=True)
