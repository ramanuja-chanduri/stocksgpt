from typing import Dict, List, Any, Optional, TypedDict
from langgraph.graph import StateGraph, END
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from app.services.llm_service import llm_service
from app.services.tool_service import get_financial_tools
from app.services.rag_service import rag_service
import asyncio


class WorkflowState(TypedDict):
    messages: List[BaseMessage]
    user_query: str
    tool_results: List[Dict[str, Any]]
    gpt_response: Optional[str]
    gemini_response: Optional[str]
    session_id: str


class WorkflowService:
    """Service for managing LangGraph workflows"""
    
    def __init__(self):
        self.tools = get_financial_tools()
        self.graph = self._create_graph()
    
    def _create_graph(self) -> StateGraph:
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
    
    async def _retrieve_context_node(self, state: WorkflowState) -> WorkflowState:
        """Retrieve relevant context using RAG"""
        query = state["user_query"]
        
        # Search for relevant context
        context_results = await rag_service.search(query, k=3)
        
        # Add context to messages if available
        if context_results:
            context_text = "\n".join([r["content"] for r in context_results])
            context_message = f"Relevant context:\n{context_text}\n\nUser query: {query}"
            state["messages"].append(SystemMessage(content=context_message))
        
        return state
    
    async def _call_gpt_node(self, state: WorkflowState) -> WorkflowState:
        """Call GPT model"""
        try:
            messages = state["messages"]
            response_chunks = []
            
            async for chunk in llm_service.call_gpt(messages, tools=self.tools, stream=True):
                response_chunks.append(chunk)
            
            state["gpt_response"] = "".join(response_chunks)
        except Exception as e:
            state["gpt_response"] = f"Error: {str(e)}"
        
        return state
    
    async def _call_gemini_node(self, state: WorkflowState) -> WorkflowState:
        """Call Gemini model"""
        try:
            messages = state["messages"]
            response_chunks = []
            
            async for chunk in llm_service.call_gemini(messages, tools=self.tools, stream=True):
                response_chunks.append(chunk)
            
            state["gemini_response"] = "".join(response_chunks)
        except Exception as e:
            state["gemini_response"] = f"Error: {str(e)}"
        
        return state
    
    async def execute(
        self,
        user_query: str,
        session_id: str,
        model_preferences: List[str],
        history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """Execute workflow"""
        # Prepare messages
        system_prompt = """You are a financial analysis assistant. Help users with stock market queries, 
        financial analysis, and market research. Use available tools to fetch real-time data when needed."""
        
        messages = llm_service.prepare_messages(user_query, history, system_prompt)
        
        # Create initial state
        initial_state: WorkflowState = {
            "messages": messages,
            "user_query": user_query,
            "tool_results": [],
            "gpt_response": None,
            "gemini_response": None,
            "session_id": session_id
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
