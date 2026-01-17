from typing import List, Dict, Any, Optional
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec
from app.core.config import settings
from app.core.logging_config import get_logger
from pathlib import Path
import json
from datetime import datetime
import os
import uuid

logger = get_logger(__name__)


class RAGService:
    """RAG service for retrieving relevant context"""
    
    def __init__(self):
        self.embeddings = None
        self.pinecone_index = None
        self.pinecone_index_name = None
        self.vectorstore = None
        self._initialize_embeddings()
        self._initialize_pinecone()
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
                    task_type = "RETRIEVAL_DOCUMENT",  # Optimized for document retrieval,
                    output_dimensionality = 768  # Ensure fixed dimensionality for Pinecone
                )
                logger.info(f"Initialized embeddings model: {settings.EMBEDDING_MODEL}")
            except Exception as e:
                logger.error(f"Error initializing embeddings: {e}", exc_info=True)
                self.embeddings = None
        else:
            logger.warning("GEMINI_API_KEY not set. RAG functionality will be disabled.")
            self.embeddings = None

    def _initialize_pinecone(self):
        """Initialize Pinecone client and index if Pinecone settings are available."""

        api_key = settings.PINECONE_API_KEY or os.getenv("PINECONE_API_KEY")
        index_name = settings.PINECONE_INDEX_NAME or os.getenv("PINECONE_INDEX_NAME")

        if not api_key or not index_name:
            logger.info("Pinecone settings not provided - vectorstore disabled.")
            return

        try:
            # Initialize Pinecone client
            pc = Pinecone(api_key=api_key)
            
            # Check if index exists
            existing_indexes = [idx.name for idx in pc.list_indexes()]

            if index_name not in existing_indexes:
                DIM = 768  # Must match embedding dimensionality
                pc.create_index(
                    name=index_name,
                    dimension=DIM,
                    metric="cosine",
                    spec=ServerlessSpec(
                        cloud='aws',
                        region='us-east-1'
                    )
                )
                logger.info(f"Created Pinecone index '{index_name}'")

            self.pinecone_index_name = index_name
            self.pinecone_index = pc.Index(index_name)
            logger.info(f"Initialized Pinecone index: {index_name}")

            # Create LangChain PineconeVectorStore wrapper
            if PineconeVectorStore and self.embeddings:
                try:
                    self.vectorstore = PineconeVectorStore(
                        index_name=self.pinecone_index_name,
                        embedding=self.embeddings
                    )
                    logger.info("Initialized LangChain PineconeVectorStore wrapper")
                except Exception as e:
                    logger.warning(f"Could not initialize LangChain PineconeVectorStore wrapper: {e}")
                    
        except Exception as e:
            logger.error(f"Error initializing Pinecone: {e}", exc_info=True)
            self.pinecone_index = None
    
    def is_available(self) -> bool:
        """Check if RAG service is properly initialized and available"""
        return self.vectorstore is not None and self.embeddings is not None
    
    async def add_documents(self, documents: List[Document]):
        """Add documents to vector store"""
        if not self.embeddings:
            logger.warning("Cannot add documents - embeddings not initialized")
            return
        
        if not self.vectorstore:
            logger.error("Vectorstore not initialized - cannot add documents")
            return

        try:
            chunks = self.text_splitter.split_documents(documents)
            
            # Ensure metadata values are strings
            for c in chunks:
                if c.metadata:
                    if "session_id" in c.metadata:
                        c.metadata["session_id"] = str(c.metadata["session_id"])
                    if "file_id" in c.metadata:
                        c.metadata["file_id"] = str(c.metadata["file_id"])
                    c.metadata.setdefault("created_at", datetime.utcnow().isoformat())

            self.vectorstore.add_documents(chunks)
            logger.info(f"Added {len(chunks)} document chunks to vectorstore")
            
        except Exception as e:
            logger.error(f"Error adding documents to vectorstore: {e}", exc_info=True)
            raise
    
    async def search(
        self, 
        query: str, 
        k: int = 5, 
        session_id: Optional[str] = None,
        file_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Search for relevant documents, filtered by session_id and/or file_ids
        
        Args:
            query: Search query
            k: Number of results to return
            session_id: Optional session filter
            file_ids: Optional list of file IDs to filter by
            
        Returns:
            List of matching documents with content, metadata, and scores
        """
        if not self.is_available():
            logger.debug("Vectorstore not available, skipping RAG search")
            return []

        try:
            # Build filter based on provided parameters
            filter_dict = {}
            
            # Priority: file_ids > session_id
            if file_ids:
                # Filter by specific file IDs
                if len(file_ids) == 1:
                    filter_dict["file_id"] = str(file_ids[0])
                else:
                    # Pinecone supports $in operator for multiple values
                    filter_dict["file_id"] = {"$in": [str(fid) for fid in file_ids]}
            elif session_id:
                # Filter by session if no file_ids specified
                filter_dict["session_id"] = str(session_id)
            
            # Only pass filter if we have conditions
            filter_to_use = filter_dict if filter_dict else None
            
            results = self.vectorstore.similarity_search_with_score(
                query, 
                k=k, 
                filter=filter_to_use
            )
            
            formatted = []
            for doc, score in results:
                # Double-check filters match (safety layer)
                if file_ids:
                    doc_file_id = str(doc.metadata.get("file_id", ""))
                    if doc_file_id not in [str(fid) for fid in file_ids]:
                        continue
                elif session_id and str(doc.metadata.get("session_id")) != str(session_id):
                    continue
                    
                formatted.append({
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "score": score
                })
            
            # Build filter description for logging
            filter_desc = []
            if file_ids:
                filter_desc.append(f"{len(file_ids)} file(s)")
            elif session_id:
                filter_desc.append(f"session {session_id}")
            filter_str = " and ".join(filter_desc) if filter_desc else "no filters"
            
            logger.info(f"RAG search found {len(formatted)} documents ({filter_str})")
            return formatted[:k]
            
        except Exception as e:
            logger.error(f"Error searching vectorstore: {e}", exc_info=True)
            return []

    def delete_by_session(self, session_id: str) -> bool:
        """Delete all vectors for a session"""
        if not self.vectorstore:
            logger.warning("Vectorstore not initialized - cannot delete")
            return False
        
        try:
            self.vectorstore.delete(filter={"session_id": str(session_id)})
            logger.info(f"Deleted vectors for session {session_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting by session: {e}", exc_info=True)
            return False

    def delete_by_file(self, file_id: str) -> bool:
        """Delete all vectors for a file"""
        if not self.vectorstore:
            logger.warning("Vectorstore not initialized - cannot delete")
            return False
        
        try:
            self.vectorstore.delete(filter={"file_id": str(file_id)})
            logger.info(f"Deleted vectors for file {file_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting by file: {e}", exc_info=True)
            return False

# Global instance
rag_service = RAGService()