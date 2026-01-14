from typing import Dict, List, Any, Optional, TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from app.services.llm_service import llm_service
from app.core.model_utils import should_call_groq, should_call_gemini
# from app.services.tool_service import get_financial_tools  # Disabled for now
from app.services.rag_service import rag_service
import asyncio


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
        context_text = "\n".join([r["content"] for r in context_results])
        return f"Relevant context:\n{context_text}\n\nUser query: {query}"
    
    async def _retrieve_context_node(self, state: WorkflowState) -> Dict[str, Any]:
        """Retrieve relevant context using RAG"""
        query = state["user_query"]
        
        # Search for relevant context
        context_results = await rag_service.search(query, k=3)
        
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
    
    async def execute(
        self,
        user_query: str,
        session_id: str,
        model_preferences: List[str],
        history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """Execute workflow"""
        # Prepare messages with a more general system prompt
        system_prompt = """You are a helpful AI assistant. Provide clear, accurate, and conversational responses to user questions. 
        Answer questions directly and naturally - do not generate code unless explicitly requested. 
        For factual questions, provide straightforward answers based on your knowledge."""
        
        messages = llm_service.prepare_messages(user_query, history, system_prompt)
        
        # Retrieve context using RAG and add to messages
        context_results = await rag_service.search(user_query, k=3)
        context_text = self._prepare_rag_context(user_query, context_results)
        if context_text:
            messages.insert(0, SystemMessage(content=context_text))
        
        # Determine which models to call
        call_groq = should_call_groq(model_preferences)
        call_gemini = should_call_gemini(model_preferences)
        
        # Call both models in parallel
        async def call_groq_model():
            if not call_groq:
                return None
            return await self._call_model(messages, llm_service.call_gpt, stream=True)
        
        async def call_gemini_model():
            if not call_gemini:
                return None
            return await self._call_model(messages, llm_service.call_gemini, stream=True)
        
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
