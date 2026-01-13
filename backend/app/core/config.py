from pydantic_settings import BaseSettings
from typing import List
import os
from pathlib import Path


class Settings(BaseSettings):
    # API Keys
    GROQ_API_KEY: str = "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"  # Groq API key for llama model
    GEMINI_API_KEY: str = "AIzaSyDrRGDfMrLPmvOAWg52cd9vEPwpvnEYVRg"  # Google API key for Gemini model
    # OPENAI_API_KEY: str = ""  # Disabled - using Groq instead
    
    # Cloud Storage - Disabled, using local storage only
    # AWS_ACCESS_KEY_ID: str = ""  # Removed - using local storage
    # AWS_SECRET_ACCESS_KEY: str = ""  # Removed - using local storage
    # AWS_REGION: str = "us-east-1"  # Removed - using local storage
    # S3_BUCKET_NAME: str = ""  # Removed - using local storage
    
    # Alternative: GCP Storage - Commented out, using local storage
    # GCP_PROJECT_ID: str = ""
    # GCP_STORAGE_BUCKET: str = ""
    # USE_GCP: bool = False  # Set to True to use GCP instead of AWS
    
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
    EMBEDDING_MODEL: str = "models/gemini-embedding-001"  # Google Gemini embedding model
    
    # Session Management
    SESSION_TIMEOUT_HOURS: int = 24
    
    # LLM Models
    GROQ_MODEL: str = "meta-llama/llama-4-scout-17b-16e-instruct"  # Groq model
    GEMINI_MODEL: str = "gemini-3-flash-preview"  # Gemini model
    # GPT_MODEL: str = "gpt-4o"  # Disabled - using Groq instead
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

# Create necessary directories
Path(settings.UPLOAD_DIR).mkdir(exist_ok=True, parents=True)
Path(settings.VECTOR_STORE_PATH).mkdir(exist_ok=True, parents=True)
