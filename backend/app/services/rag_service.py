from typing import List, Dict, Any, Optional
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from app.core.config import settings
from app.core.logging_config import get_logger
from pathlib import Path
import json
from datetime import datetime

logger = get_logger(__name__)


class RAGService:
    """RAG service for retrieving relevant context"""
    
    def __init__(self):
        self.embeddings = None
        self.vectorstore = None
        self._initialize_embeddings()
        self._load_vectorstore()
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200
        )
    
    def _initialize_embeddings(self):
        """Initialize embeddings model using Google Generative AI (Gemini)"""
        if settings.GEMINI_API_KEY:
            import os
            # Set environment variables for compatibility with LangChain
            if not os.getenv("GEMINI_API_KEY"):
                os.environ["GEMINI_API_KEY"] = settings.GEMINI_API_KEY
            if not os.getenv("GOOGLE_API_KEY"):
                os.environ["GOOGLE_API_KEY"] = settings.GEMINI_API_KEY
            
            try:
                self.embeddings = GoogleGenerativeAIEmbeddings(
                    model=settings.EMBEDDING_MODEL,
                    task_type="RETRIEVAL_DOCUMENT"  # Optimized for document retrieval
                )
                logger.info(f"Initialized embeddings model: {settings.EMBEDDING_MODEL}")
            except Exception as e:
                logger.error(f"Error initializing embeddings: {e}", exc_info=True)
                self.embeddings = None
        else:
            logger.warning("GEMINI_API_KEY not set. RAG functionality will be disabled.")
            self.embeddings = None
    
    def _load_vectorstore(self):
        """Load or create vector store"""
        if not self.embeddings:
            return
        
        vectorstore_path = Path(settings.VECTOR_STORE_PATH)
        
        if vectorstore_path.exists() and any(vectorstore_path.iterdir()):
            try:
                self.vectorstore = FAISS.load_local(
                    str(vectorstore_path),
                    self.embeddings,
                    allow_dangerous_deserialization=True
                )
            except Exception as e:
                logger.error(f"Error loading vectorstore: {e}", exc_info=True)
                self.vectorstore = None
        
        if not self.vectorstore:
            # Create empty vectorstore with a dummy document that won't interfere with searches
            logger.info("Creating new vectorstore with initial document")
            dummy_doc = Document(
                page_content="Initial document",
                metadata={"type": "system", "session_id": "__system__"}
            )
            self.vectorstore = FAISS.from_documents([dummy_doc], self.embeddings)
            self._save_vectorstore()
            logger.info("Successfully created new vectorstore")
    
    def _save_vectorstore(self):
        """Save vector store to disk"""
        if self.vectorstore:
            vectorstore_path = Path(settings.VECTOR_STORE_PATH)
            vectorstore_path.mkdir(exist_ok=True, parents=True)
            self.vectorstore.save_local(str(vectorstore_path))
    
    async def add_documents(self, documents: List[Document]):
        """Add documents to vector store"""
        if not self.vectorstore or not self.embeddings:
            logger.warning("Cannot add documents - vectorstore or embeddings not initialized")
            return
        
        try:
            # Split documents
            texts = self.text_splitter.split_documents(documents)
            
            # Add to vectorstore
            self.vectorstore.add_documents(texts)
            self._save_vectorstore()
            logger.info(f"Added {len(texts)} document chunks to vectorstore")
        except Exception as e:
            logger.error(f"Error adding documents to vectorstore: {e}", exc_info=True)
    
    async def search(self, query: str, k: int = 5, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search for relevant documents, optionally filtered by session_id"""
        if not self.vectorstore:
            logger.warning("Vectorstore not initialized, cannot perform search")
            return []
        
        try:
            # If session_id is provided, search more results and filter by session_id
            # This is because FAISS filtering might not work reliably, so we search more and filter
            search_k = k * 3 if session_id else k  # Search more if filtering
            
            # Try to use filter if available, otherwise search all and filter manually
            results = []
            try:
                if session_id:
                    # Try using filter parameter (may not work in all FAISS versions)
                    filter_dict = {"session_id": str(session_id)}
                    results = self.vectorstore.similarity_search_with_score(
                        query, 
                        k=search_k,
                        filter=filter_dict
                    )
                else:
                    results = self.vectorstore.similarity_search_with_score(query, k=search_k)
            except (TypeError, AttributeError) as e:
                # Filter parameter not supported, search all and filter manually
                logger.debug(f"Filter parameter not supported, searching all and filtering manually: {e}")
                results = self.vectorstore.similarity_search_with_score(query, k=search_k)
            
            # Filter results by session_id if provided
            filtered_results = []
            for doc, score in results:
                if session_id:
                    # Only include documents that match the session_id
                    doc_session_id = doc.metadata.get("session_id")
                    if doc_session_id and str(doc_session_id) == str(session_id):
                        filtered_results.append({
                            "content": doc.page_content,
                            "metadata": doc.metadata,
                            "score": score
                        })
                else:
                    # Include all results if no session_id filter
                    filtered_results.append({
                        "content": doc.page_content,
                        "metadata": doc.metadata,
                        "score": score
                    })
            
            # Limit to k results
            filtered_results = filtered_results[:k]
            
            if session_id:
                logger.info(f"RAG search: Found {len(filtered_results)} documents for session {session_id}")
            else:
                logger.info(f"RAG search: Found {len(filtered_results)} documents")
            
            return filtered_results
        except Exception as e:
            logger.error(f"Error searching vectorstore: {e}", exc_info=True)
            return []
    
    async def add_financial_context(self, symbol: str, data: Dict[str, Any]):
        """Add financial data as context"""
        if not self.vectorstore or not self.embeddings:
            return
        
        try:
            content = f"Stock: {symbol}\n{json.dumps(data, indent=2)}"
            doc = Document(
                page_content=content,
                metadata={
                    "symbol": symbol,
                    "type": "financial_data",
                    "timestamp": str(datetime.now())
                }
            )
            await self.add_documents([doc])
            logger.info(f"Added financial context for symbol: {symbol}")
        except Exception as e:
            logger.error(f"Error adding financial context for symbol {symbol}: {e}", exc_info=True)


# Global instance
rag_service = RAGService()
