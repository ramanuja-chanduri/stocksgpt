from typing import List, Optional, AsyncIterator, Dict, Any
# from langchain_openai import ChatOpenAI  # Disabled - using Groq instead
from langchain_groq import ChatGroq
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage
from langchain_core.callbacks import AsyncCallbackHandler
from app.core.config import settings
import json


class StreamingCallbackHandler(AsyncCallbackHandler):
    """Callback handler for streaming responses"""
    def __init__(self):
        self.tokens = []
        self.finished = False
    
    async def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        self.tokens.append(token)
    
    async def on_llm_end(self, response, **kwargs: Any) -> None:
        self.finished = True
    
    def get_content(self) -> str:
        return "".join(self.tokens)


class LLMService:
    """Service for managing LLM interactions"""
    
    def __init__(self):
        self.groq_llm = None
        self.gemini_llm = None
        # self.gpt_llm = None  # Disabled - using Groq instead
        self._initialize_models()
    
    def _initialize_models(self):
        """Initialize LLM models"""
        if settings.GROQ_API_KEY:
            self.groq_llm = ChatGroq(
                model=settings.GROQ_MODEL,
                temperature=0.7,
                api_key=settings.GROQ_API_KEY,  # type: ignore
                streaming=True
            )
        
        if settings.GEMINI_API_KEY:
            self.gemini_llm = ChatGoogleGenerativeAI(
                model=settings.GEMINI_MODEL,
                temperature=0.7,
                api_key=settings.GEMINI_API_KEY,  # type: ignore
                streaming=True
            )
        
        # Disabled - using Groq instead
        # if settings.OPENAI_API_KEY:
        #     self.gpt_llm = ChatOpenAI(
        #         model=settings.GPT_MODEL,
        #         temperature=0.7,
        #         api_key=settings.OPENAI_API_KEY,
        #         streaming=True
        #     )

    def _content_to_text(self, content: Any) -> str:
        """
        Best-effort conversion of LangChain message/chunk content to plain text.

        Different providers can return:
        - str
        - list[str]
        - list[dict] like [{"type": "text", "text": "..."}]
        - dict like {"text": "..."} or {"content": "..."} (provider-specific)
        """
        if content is None:
            return ""

        if isinstance(content, str):
            return content

        if isinstance(content, dict):
            # Common patterns across providers
            if isinstance(content.get("text"), str):
                return content["text"]
            if isinstance(content.get("content"), str):
                return content["content"]
            # Fallback: stringify
            return str(content)

        if isinstance(content, list):
            parts: List[str] = []
            for item in content:
                if item is None:
                    continue
                if isinstance(item, str):
                    parts.append(item)
                    continue
                if isinstance(item, dict):
                    if isinstance(item.get("text"), str):
                        parts.append(item["text"])
                        continue
                    if isinstance(item.get("content"), str):
                        parts.append(item["content"])
                        continue
                    # Some providers nest: {"type":"text","text":"..."} etc.
                    if isinstance(item.get("type"), str) and isinstance(item.get("text"), str):
                        parts.append(item["text"])
                        continue
                # Last resort
                parts.append(str(item))
            return "".join(parts)

        return str(content)
    
    async def call_gpt(
        self,
        messages: List[BaseMessage],
        tools: Optional[List] = None,
        stream: bool = False
    ) -> AsyncIterator[str]:
        """Call Groq model (previously GPT-4o)"""
        if not self.groq_llm:
            raise ValueError("Groq API key not configured")
        
        llm = self.groq_llm
        # Tools disabled for now
        # if tools:
        #     llm = llm.bind_tools(tools)
        
        if stream:
            async for chunk in llm.astream(messages):
                if hasattr(chunk, "content") and chunk.content is not None:
                    text = self._content_to_text(chunk.content)
                    if text:
                        yield text
        else:
            response = await llm.ainvoke(messages)
            text = self._content_to_text(getattr(response, "content", None))
            yield text
    
    async def call_gemini(
        self,
        messages: List[BaseMessage],
        tools: Optional[List] = None,
        stream: bool = False
    ) -> AsyncIterator[str]:
        """Call Gemini 3 Flash Preview model"""
        if not self.gemini_llm:
            raise ValueError("Google API key not configured")
        
        llm = self.gemini_llm
        # Tools disabled for now
        # if tools:
        #     llm = llm.bind_tools(tools)
        
        if stream:
            async for chunk in llm.astream(messages):
                if hasattr(chunk, "content") and chunk.content is not None:
                    text = self._content_to_text(chunk.content)
                    if text:
                        yield text
        else:
            response = await llm.ainvoke(messages)
            text = self._content_to_text(getattr(response, "content", None))
            yield text
    
    async def call_both(
        self,
        messages: List[BaseMessage],
        tools: Optional[List] = None,
        stream: bool = False
    ) -> Dict[str, AsyncIterator[str]]:
        """Call both models in parallel (Groq and Gemini)"""
        import asyncio
        
        tasks = {}
        if self.groq_llm:
            tasks["groq-llama"] = self.call_gpt(messages, tools, stream)
        if self.gemini_llm:
            tasks["gemini-3-flash"] = self.call_gemini(messages, tools, stream)
        
        return tasks
    
    def prepare_messages(
        self,
        user_message: str,
        history: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None
    ) -> List[BaseMessage]:
        """Prepare messages for LLM"""
        messages = []
        
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        
        # Add history
        if history:
            for msg in history:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "user":
                    messages.append(HumanMessage(content=content))
                else:
                    # For assistant messages, we'll use HumanMessage for simplicity
                    # In production, you might want to use AIMessage
                    messages.append(HumanMessage(content=f"Previous response: {content}"))
        
        # Add current user message
        messages.append(HumanMessage(content=user_message))
        
        return messages


# Global instance
llm_service = LLMService()
