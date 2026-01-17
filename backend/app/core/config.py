from pydantic_settings import BaseSettings
from typing import List
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    # API Keys - loaded from .env file first, then environment variables
    # Set these in backend/.env file (do NOT hard-code real keys)
    GROQ_API_KEY: str = os.environ["GROQ_API_KEY"]  # Groq API key for llama model
    GEMINI_API_KEY: str = os.environ["GEMINI_API_KEY"]  # Google API key for Gemini model
    # OPENAI_API_KEY: str = ""  # Disabled - using Groq instead
    
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
    EMBEDDING_MODEL: str = "models/gemini-embedding-001"  # Google Gemini embedding model
    PINECONE_API_KEY: str = os.getenv("PINECONE_API_KEY", "")
    PINECONE_INDEX_NAME: str = "stocks-gpt-index"
    
    # Session Management
    SESSION_TIMEOUT_HOURS: int = 24
    
    # LLM Models
    GROQ_MODEL: str = "meta-llama/llama-4-scout-17b-16e-instruct"  # Groq model
    GEMINI_MODEL: str = "gemini-3-flash-preview"  # Gemini model
    # GPT_MODEL: str = "gpt-4o"  # Disabled - using Groq instead
    
    class Config:
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"


settings = Settings()

# Create necessary directories
Path(settings.UPLOAD_DIR).mkdir(exist_ok=True, parents=True)
