from typing import Dict, List, Any, Optional, TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from app.services.llm_service import llm_service
from app.core.model_utils import should_call_groq, should_call_gemini
# from app.services.tool_service import get_financial_tools  # Disabled for now
from app.services.rag_service import rag_service
from app.core.config import settings
from app.core.logging_config import get_logger
from pathlib import Path
import asyncio
import base64
import aiofiles

logger = get_logger(__name__)


def add_messages(left: List[BaseMessage], right: List[BaseMessage]) -> List[BaseMessage]:
    """Reducer function for messages - combines message lists"""
    return left + right


class WorkflowState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    user_query: str
    tool_results: List[Dict[str, Any]]
    gpt_response: Optional[str]
    gemini_response: Optional[str]
    session_id: str
    model_preferences: List[str]


class WorkflowService:
    """Service for managing LangGraph workflows"""
    
    def __init__(self):
        # self.tools = get_financial_tools()  # Disabled for now
        self.tools = None  # Tools disabled for now
        self.graph = self._create_graph()
    
    def _create_graph(self):
        """Create LangGraph workflow"""
        workflow = StateGraph(WorkflowState)
        
        # Add nodes
        workflow.add_node("retrieve_context", self._retrieve_context_node)
        workflow.add_node("call_gpt", self._call_gpt_node)
        workflow.add_node("call_gemini", self._call_gemini_node)
        
        # Set entry point
        workflow.set_entry_point("retrieve_context")
        
        # Define edges
        workflow.add_edge("retrieve_context", "call_gpt")
        workflow.add_edge("retrieve_context", "call_gemini")
        workflow.add_edge("call_gpt", END)
        workflow.add_edge("call_gemini", END)
        
        return workflow.compile()
    
    def _prepare_rag_context(self, query: str, context_results: List[Dict[str, Any]]) -> Optional[str]:
        """Prepare RAG context text from search results"""
        if not context_results:
            return None
        
        # Format context with file information if available
        context_parts = []
        for i, r in enumerate(context_results, 1):
            content = r["content"]
            metadata = r.get("metadata", {})
            file_name = metadata.get("file_name", "Unknown file")
            context_parts.append(f"[From {file_name}]\n{content}")
        
        context_text = "\n\n---\n\n".join(context_parts)
        return f"""The following information is from documents uploaded by the user. Use this information to answer their question accurately and in detail.

{context_text}

Based on the above context, answer the user's question: {query}"""
    
    async def _retrieve_context_node(self, state: WorkflowState) -> Dict[str, Any]:
        """Retrieve relevant context using RAG"""
        query = state["user_query"]
        session_id = state.get("session_id")
        
        # Search for relevant context, filtered by session_id
        context_results = await rag_service.search(query, k=5, session_id=session_id)
        
        # Add context to messages if available
        new_messages = []
        context_text = self._prepare_rag_context(query, context_results)
        if context_text:
            new_messages.append(SystemMessage(content=context_text))
        
        # Return only the fields we're updating
        return {"messages": new_messages}
    
    async def _call_model(self, messages: List[BaseMessage], model_func, stream: bool = True) -> str:
        """Helper function to call a model and accumulate response chunks"""
        try:
            response_chunks = []
            async for chunk in model_func(messages, tools=None, stream=stream):
                response_chunks.append(chunk)
            return "".join(response_chunks)
        except Exception as e:
            return f"Error: {str(e)}"
    
    async def _call_gpt_node(self, state: WorkflowState) -> Dict[str, Any]:
        """Call GPT model (Groq/Llama)"""
        # Check if Groq/Llama should be called
        model_prefs = state.get("model_preferences", [])
        if not should_call_groq(model_prefs):
            return {"gpt_response": None}
        
        messages = state["messages"]
        gpt_response = await self._call_model(messages, llm_service.call_gpt, stream=True)
        return {"gpt_response": gpt_response}
    
    async def _call_gemini_node(self, state: WorkflowState) -> Dict[str, Any]:
        """Call Gemini model"""
        # Check if Gemini should be called
        model_prefs = state.get("model_preferences", [])
        if not should_call_gemini(model_prefs):
            return {"gemini_response": None}
        
        messages = state["messages"]
        gemini_response = await self._call_model(messages, llm_service.call_gemini, stream=True)
        return {"gemini_response": gemini_response}
    
    async def _load_file_content(self, cloud_url: str) -> Optional[bytes]:
        """Load file content from local storage using cloud_url
        
        Args:
            cloud_url: URL path like /uploads/session_id/file_id_filename
            
        Returns:
            File content as bytes, or None if file not found
        """
        try:
            # cloud_url is like /uploads/session_id/file_id_filename
            # UPLOAD_DIR is ./uploads
            # We need to extract the relative path after /uploads/
            
            if not cloud_url:
                logger.warning("Empty cloud_url provided")
                return None
            
            # Remove leading slash and extract path after uploads directory name
            uploads_dir_name = Path(settings.UPLOAD_DIR).name  # "uploads"
            if cloud_url.startswith(f"/{uploads_dir_name}/"):
                # Extract the part after /uploads/
                rel_path = cloud_url[len(f"/{uploads_dir_name}/"):]
                full_path = Path(settings.UPLOAD_DIR) / rel_path
            elif cloud_url.startswith("/"):
                # Fallback: assume it's already relative to UPLOAD_DIR
                rel_path = cloud_url.lstrip("/")
                full_path = Path(settings.UPLOAD_DIR) / rel_path
            else:
                # Assume it's already a relative path
                full_path = Path(settings.UPLOAD_DIR) / cloud_url
            
            if not full_path.exists():
                logger.warning(f"File not found: {full_path} (from cloud_url: {cloud_url})")
                return None
            
            async with aiofiles.open(full_path, 'rb') as f:
                content = await f.read()
            logger.debug(f"Loaded file: {full_path} ({len(content)} bytes)")
            return content
        except Exception as e:
            logger.error(f"Error loading file from {cloud_url}: {e}", exc_info=True)
            return None
    
    async def _prepare_files_for_llm(
        self, 
        file_records: Any,  # Accept any sequence of file records
        user_query: str
    ) -> Dict[str, List[BaseMessage]]:
        """Prepare messages with files for different models"""
        # Separate messages for different models (some may not support images)
        groq_messages = []
        gemini_messages = []
        
        # Prepare base text message
        text_content = user_query
        
        # Load image files and prepare multimodal content
        image_parts = []
        for file_record in file_records:
            file_ext = Path(file_record.file_name).suffix.lower()
            is_image = file_ext in ['.jpg', '.jpeg', '.png', '.webp']
            
            if is_image:
                # Load image content
                file_content = await self._load_file_content(file_record.cloud_url)
                if file_content:
                    # Encode image as base64
                    image_base64 = base64.b64encode(file_content).decode('utf-8')
                    
                    # Determine MIME type
                    mime_type_map = {
                        '.jpg': 'image/jpeg',
                        '.jpeg': 'image/jpeg',
                        '.png': 'image/png',
                        '.webp': 'image/webp'
                    }
                    mime_type = mime_type_map.get(file_ext, 'image/jpeg')
                    
                    # For Gemini: use multimodal format (LangChain format)
                    image_parts.append({
                        "type": "image",
                        "source_type": "base64",
                        "mime_type": mime_type,
                        "data": image_base64
                    })
                    logger.info(f"Loaded image file: {file_record.file_name} ({len(file_content)} bytes)")
            elif file_ext == '.pdf':
                # For PDFs, we'll include a note that it was uploaded
                # The RAG system should have already processed it
                text_content += f"\n\n[Note: A PDF file '{file_record.file_name}' has been uploaded and processed. You can reference its content in your response.]"
        
        # Prepare Gemini messages (supports multimodal)
        if image_parts:
            # Create multimodal message with text and images for Gemini
            gemini_content: List[Any] = [{"type": "text", "text": text_content}] + image_parts
            gemini_messages.append(HumanMessage(content=gemini_content))
        else:
            gemini_messages.append(HumanMessage(content=text_content))

        # Prepare Groq/Llama messages: many providers (Groq/Llama) expect
        # image parts as `image_url` entries. Convert base64 image parts to
        # data-URL `image_url` objects so the Groq API accepts them.
        if image_parts:
            groq_image_parts: List[Any] = []
            for p in image_parts:
                # If part is base64-encoded, convert to data URL
                if p.get("source_type") == "base64" and p.get("data"):
                    mime = p.get("mime_type", "image/jpeg")
                    data_b64 = p.get("data")
                    data_url = f"data:{mime};base64,{data_b64}"
                    groq_image_parts.append({
                        "type": "image_url",
                        "image_url": {"url": data_url}
                    })
                else:
                    # Fallback: pass through existing part
                    groq_image_parts.append(p)

            groq_content: List[Any] = [{"type": "text", "text": text_content}] + groq_image_parts
            groq_messages.append(HumanMessage(content=groq_content))
        else:
            groq_messages.append(HumanMessage(content=text_content))
        
        return {
            "groq": groq_messages,
            "gemini": gemini_messages
        }
    
    async def execute(
        self,
        user_query: str,
        session_id: str,
        model_preferences: List[str],
        history: Optional[List[Dict[str, str]]] = None,
        file_records: Optional[List[Any]] = None
    ) -> Dict[str, Any]:
        """Execute workflow"""
        # Prepare messages with a more general system prompt
        system_prompt = """You are a helpful AI assistant. Provide clear, accurate, and conversational responses to user questions. 
        Answer questions directly and naturally - do not generate code unless explicitly requested. 
        For factual questions, provide straightforward answers based on your knowledge."""
        
        # Prepare base messages
        base_messages = llm_service.prepare_messages(user_query, history, system_prompt)
        
        # Retrieve context using RAG and add to messages, filtered by session_id
        context_results = await rag_service.search(user_query, k=5, session_id=session_id)
        context_text = self._prepare_rag_context(user_query, context_results)
        
        # Prepare messages with files if provided
        if file_records:
            file_messages = await self._prepare_files_for_llm(file_records, user_query)
            
            # For Gemini: combine system prompt, context, and file messages
            gemini_messages = []
            if context_text:
                gemini_messages.append(SystemMessage(content=context_text))
            elif system_prompt:
                gemini_messages.append(SystemMessage(content=system_prompt))
            gemini_messages.extend(file_messages["gemini"])
            
            # For Groq: combine system prompt, context, and text messages
            groq_messages = []
            if context_text:
                groq_messages.append(SystemMessage(content=context_text))
            elif system_prompt:
                groq_messages.append(SystemMessage(content=system_prompt))
            groq_messages.extend(file_messages["groq"])
        else:
            # No files, use standard messages
            messages = base_messages.copy()
            if context_text:
                messages.insert(0, SystemMessage(content=context_text))
            gemini_messages = messages
            groq_messages = messages
        
        # Determine which models to call
        call_groq = should_call_groq(model_preferences)
        call_gemini = should_call_gemini(model_preferences)
        
        # Call both models in parallel
        async def call_groq_model():
            if not call_groq:
                return None
            return await self._call_model(groq_messages, llm_service.call_gpt, stream=True)
        
        async def call_gemini_model():
            if not call_gemini:
                return None
            return await self._call_model(gemini_messages, llm_service.call_gemini, stream=True)
        
        # Execute both models in parallel
        gpt_response, gemini_response = await asyncio.gather(
            call_groq_model(),
            call_gemini_model(),
            return_exceptions=False
        )
        
        return {
            "gpt_response": gpt_response,
            "gemini_response": gemini_response,
            "tool_results": []
        }


# Global instance
workflow_service = WorkflowService()
