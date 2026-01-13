from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime
from enum import Enum


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT_GPT = "assistant_gpt"
    ASSISTANT_GEMINI = "assistant_gemini"


class ModelType(str, Enum):
    GROQ_LLAMA = "meta-llama/llama-4-scout-17b-16e-instruct"  # Groq model
    GEMINI_3_FLASH = "gemini-3-flash-preview"  # Gemini model
    # GPT_4O = "gpt-4o"  # Disabled - using Groq instead


class SessionCreate(BaseModel):
    title: Optional[str] = None


class SessionResponse(BaseModel):
    session_id: str
    title: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class MessageCreate(BaseModel):
    content: str
    session_id: str
    model_preferences: Optional[List[ModelType]] = Field(
        default=[ModelType.GROQ_LLAMA, ModelType.GEMINI_3_FLASH],  # Both models
        description="Which models to query"
    )
    file_ids: Optional[List[str]] = Field(default=[], description="Attached file IDs")


class MessageResponse(BaseModel):
    message_id: str
    session_id: str
    role: str
    content: str
    model: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class FileUploadResponse(BaseModel):
    file_id: str
    session_id: str
    file_name: str
    file_type: str
    file_size: int
    cloud_url: Optional[str]
    uploaded_at: datetime
    
    class Config:
        from_attributes = True


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    model_preferences: List[str] = Field(
        default=["meta-llama/llama-4-scout-17b-16e-instruct", "gemini-3-flash-preview"],  # Both models
        description="Which models to query: 'meta-llama/llama-4-scout-17b-16e-instruct' (Groq) or 'gemini-3-flash-preview' (Gemini)"
    )
    file_ids: Optional[List[str]] = Field(default=[])


class ChatResponse(BaseModel):
    session_id: str
    user_message_id: str
    responses: List[MessageResponse]
    tool_calls: Optional[List[dict]] = None


class StreamingChunk(BaseModel):
    session_id: str
    message_id: str
    model: str
    content: str
    done: bool = False


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
