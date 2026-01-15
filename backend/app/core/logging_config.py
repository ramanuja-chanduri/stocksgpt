"""Logging configuration for the application"""
import logging
import sys
from pathlib import Path
from app.core.config import settings

# Create logs directory if it doesn't exist
LOG_DIR = Path("./logs")
LOG_DIR.mkdir(exist_ok=True, parents=True)

# Configure logging format
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Configure root logger
def setup_logging():
    """Setup logging configuration for the application"""
    # Console: Always INFO level for cleaner output
    # Files: DEBUG level for detailed logs when needed
    console_level = logging.INFO
    file_level = logging.DEBUG if settings.DEBUG else logging.INFO
    
    # Create formatters
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)
    
    # Configure root logger - set to lowest level needed
    root_logger = logging.getLogger()
    root_logger.setLevel(min(console_level, file_level))
    
    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()
    
    # Console handler - less verbose, only INFO and above
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler for general logs - more detailed
    file_handler = logging.FileHandler(LOG_DIR / "app.log", encoding="utf-8")
    file_handler.setLevel(file_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # File handler for errors
    error_handler = logging.FileHandler(LOG_DIR / "errors.log", encoding="utf-8")
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)
    
    # Suppress verbose third-party library logs
    # Database/ORM logs
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)  # Suppress SQL query logs
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.dialects").setLevel(logging.WARNING)
    
    # HTTP client logs
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    # LLM provider logs
    logging.getLogger("groq").setLevel(logging.WARNING)
    logging.getLogger("groq._base_client").setLevel(logging.WARNING)
    logging.getLogger("google_genai").setLevel(logging.WARNING)
    logging.getLogger("google.genai").setLevel(logging.WARNING)
    
    # LangChain logs
    logging.getLogger("langchain").setLevel(logging.WARNING)
    logging.getLogger("langchain_core").setLevel(logging.WARNING)
    logging.getLogger("langchain_community").setLevel(logging.WARNING)
    
    # Uvicorn/FastAPI logs
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)  # Suppress access logs
    logging.getLogger("fastapi").setLevel(logging.WARNING)
    
    # Keep our application logs at appropriate levels
    # Application loggers will use the root logger level (INFO or DEBUG based on settings)
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a module"""
    return logging.getLogger(name)
