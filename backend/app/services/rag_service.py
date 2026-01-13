from typing import List, Dict, Any, Optional
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from app.core.config import settings
from pathlib import Path
import json
from datetime import datetime


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
            
            self.embeddings = GoogleGenerativeAIEmbeddings(
                model=settings.EMBEDDING_MODEL,
                task_type="RETRIEVAL_DOCUMENT"  # Optimized for document retrieval
            )
    
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
                print(f"Error loading vectorstore: {e}")
                self.vectorstore = None
        
        if not self.vectorstore:
            # Create empty vectorstore
            dummy_doc = Document(page_content="Initial document")
            self.vectorstore = FAISS.from_documents([dummy_doc], self.embeddings)
            self._save_vectorstore()
    
    def _save_vectorstore(self):
        """Save vector store to disk"""
        if self.vectorstore:
            vectorstore_path = Path(settings.VECTOR_STORE_PATH)
            vectorstore_path.mkdir(exist_ok=True, parents=True)
            self.vectorstore.save_local(str(vectorstore_path))
    
    async def add_documents(self, documents: List[Document]):
        """Add documents to vector store"""
        if not self.vectorstore or not self.embeddings:
            return
        
        try:
            # Split documents
            texts = self.text_splitter.split_documents(documents)
            
            # Add to vectorstore
            self.vectorstore.add_documents(texts)
            self._save_vectorstore()
        except Exception as e:
            print(f"Error adding documents to vectorstore: {e}")
    
    async def search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """Search for relevant documents"""
        if not self.vectorstore:
            return []
        
        try:
            results = self.vectorstore.similarity_search_with_score(query, k=k)
            return [
                {
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "score": score
                }
                for doc, score in results
            ]
        except Exception as e:
            print(f"Error searching vectorstore: {e}")
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
        except Exception as e:
            print(f"Error adding financial context: {e}")


# Global instance
rag_service = RAGService()
