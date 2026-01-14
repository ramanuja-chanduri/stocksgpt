"""Utility functions for model preference checking and related operations"""
from typing import List
from app.core.config import settings


def should_call_groq(model_preferences: List[str]) -> bool:
    """Check if Groq/Llama model should be called based on preferences"""
    return (
        settings.GROQ_MODEL in model_preferences 
        or "groq-llama" in model_preferences 
        or len(model_preferences) == 0
    )


def should_call_gemini(model_preferences: List[str]) -> bool:
    """Check if Gemini model should be called based on preferences"""
    return (
        settings.GEMINI_MODEL in model_preferences 
        or "gemini-3-flash" in model_preferences
    )


def get_groq_model_name() -> str:
    """Get the Groq model name"""
    return settings.GROQ_MODEL


def get_gemini_model_name() -> str:
    """Get the Gemini model name"""
    return settings.GEMINI_MODEL
