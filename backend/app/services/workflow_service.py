from typing import Dict, List, Any, Optional, TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from app.services.llm_service import llm_service
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
    
    async def _retrieve_context_node(self, state: WorkflowState) -> Dict[str, Any]:
        """Retrieve relevant context using RAG"""
        query = state["user_query"]
        
        # Search for relevant context
        context_results = await rag_service.search(query, k=3)
        
        # Add context to messages if available
        new_messages = []
        if context_results:
            context_text = "\n".join([r["content"] for r in context_results])
            context_message = f"Relevant context:\n{context_text}\n\nUser query: {query}"
            new_messages.append(SystemMessage(content=context_message))
        
        # Return only the fields we're updating
        return {"messages": new_messages}
    
    async def _call_gpt_node(self, state: WorkflowState) -> Dict[str, Any]:
        """Call GPT model (Groq/Llama)"""
        # Check if Groq/Llama should be called
        model_prefs = state.get("model_preferences", [])
        call_groq = (
            "meta-llama/llama-4-scout-17b-16e-instruct" in model_prefs 
            or "groq-llama" in model_prefs 
            or len(model_prefs) == 0
        )
        
        if not call_groq:
            return {"gpt_response": None}
        
        try:
            messages = state["messages"]
            response_chunks = []
            
            async for chunk in llm_service.call_gpt(messages, tools=None, stream=True):  # tools=self.tools disabled
                response_chunks.append(chunk)
            
            gpt_response = "".join(response_chunks)
        except Exception as e:
            gpt_response = f"Error: {str(e)}"
        
        # Return only the fields we're updating (not messages)
        return {"gpt_response": gpt_response}
    
    async def _call_gemini_node(self, state: WorkflowState) -> Dict[str, Any]:
        """Call Gemini model"""
        # Check if Gemini should be called
        model_prefs = state.get("model_preferences", [])
        call_gemini = (
            "gemini-3-flash-preview" in model_prefs 
            or "gemini-3-flash" in model_prefs
        )
        
        if not call_gemini:
            return {"gemini_response": None}
        
        try:
            messages = state["messages"]
            response_chunks = []
            
            async for chunk in llm_service.call_gemini(messages, tools=None, stream=True):  # tools=self.tools disabled
                response_chunks.append(chunk)
            
            gemini_response = "".join(response_chunks)
        except Exception as e:
            gemini_response = f"Error: {str(e)}"
        
        # Return only the fields we're updating (not messages)
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
        
        # Create initial state
        initial_state: WorkflowState = {
            "messages": messages,
            "user_query": user_query,
            "tool_results": [],
            "gpt_response": None,
            "gemini_response": None,
            "session_id": session_id,
            "model_preferences": model_preferences
        }
        
        # Execute graph
        result = await self.graph.ainvoke(initial_state)
        
        return {
            "gpt_response": result.get("gpt_response"),
            "gemini_response": result.get("gemini_response"),
            "tool_results": result.get("tool_results", [])
        }


# Global instance
workflow_service = WorkflowService()
