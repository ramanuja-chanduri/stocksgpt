import secrets
from typing import Optional
from fastapi import HTTPException, status
from pathlib import Path
import filetype


def generate_id() -> str:
    """Generate a unique ID"""
    return secrets.token_urlsafe(16)


def validate_file_type(file_path: Path, allowed_extensions: list, file_contents: Optional[bytes] = None) -> bool:
    """Validate file type using file extension and MIME type"""
    # Check extension
    if file_path.suffix.lower() not in allowed_extensions:
        return False
    
    # Check MIME type using filetype (pure Python, works on all platforms)
    try:
        # Prefer file contents if provided (for uploaded files in memory)
        if file_contents:
            kind = filetype.guess(file_contents)
        else:
            # Fall back to reading from file path
            kind = filetype.guess(str(file_path))
        
        if kind:
            mime_type = kind.mime
            allowed_mimes = {
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".png": "image/png",
                ".webp": "image/webp",
                ".pdf": "application/pdf"
            }
            expected_mime = allowed_mimes.get(file_path.suffix.lower())
            if expected_mime and mime_type == expected_mime:
                return True
    except Exception:
        # If filetype detection fails, fall back to extension check
        pass
    
    return True


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent directory traversal"""
    # Remove path components
    filename = Path(filename).name
    # Remove dangerous characters
    filename = "".join(c for c in filename if c.isalnum() or c in "._-")
    return filename


class RateLimiter:
    """Simple in-memory rate limiter (consider Redis for production)"""
    def __init__(self):
        self.requests = {}
    
    def is_allowed(self, identifier: str, max_requests: int = 100, window_seconds: int = 60) -> bool:
        import time
        current_time = time.time()
        
        if identifier not in self.requests:
            self.requests[identifier] = []
        
        # Clean old requests
        self.requests[identifier] = [
            req_time for req_time in self.requests[identifier]
            if current_time - req_time < window_seconds
        ]
        
        if len(self.requests[identifier]) >= max_requests:
            return False
        
        self.requests[identifier].append(current_time)
        return True


rate_limiter = RateLimiter()
