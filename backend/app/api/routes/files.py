from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import uuid
from pathlib import Path

from app.core.database import get_db
from app.models import models, schemas
from app.services.storage_service import storage_service
from app.core.security import validate_file_type, sanitize_filename
from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.post("/upload", response_model=schemas.FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    session_id: str = Form(None),
    db: AsyncSession = Depends(get_db)
):
    """Upload a file. session_id can be passed as a form field."""
    try:
        logger.info(f"File upload: {file.filename} (session: {session_id or 'new'})")
        
        # Validate file size
        contents = await file.read()
        if len(contents) > settings.MAX_FILE_SIZE:
            logger.warning(f"File too large: {len(contents)} bytes (max: {settings.MAX_FILE_SIZE} bytes)")
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size is {settings.MAX_FILE_SIZE / 1024 / 1024}MB"
            )
        
        # Validate file type
        file_path = Path(file.filename)
        if not validate_file_type(file_path, settings.ALLOWED_EXTENSIONS, file_contents=contents):
            logger.warning(f"Invalid file type: {file.filename}")
            raise HTTPException(
                status_code=400,
                detail=f"File type not allowed. Allowed types: {', '.join(settings.ALLOWED_EXTENSIONS)}"
            )
        
        # Get or create session
        if session_id:
            logger.debug(f"Looking up existing session: {session_id}")
            result = await db.execute(
                select(models.Session).where(models.Session.session_id == session_id)
            )
            session = result.scalar_one_or_none()
            if not session:
                logger.warning(f"Session not found: {session_id}")
                raise HTTPException(status_code=404, detail="Session not found")
            logger.debug(f"Found existing session: {session_id}")
        else:
            # Create new session
            session = models.Session(session_id=str(uuid.uuid4()))
            db.add(session)
            await db.flush()
            logger.info(f"Created new session for file upload: {session.session_id}")
        
        # Sanitize filename
        sanitized_name = sanitize_filename(file.filename)
        logger.debug(f"Sanitized filename: {file.filename} -> {sanitized_name}")
        
        # Upload to storage first; storage will generate a file_id and return it
        logger.debug(f"Uploading file to storage: {sanitized_name}")
        storage_file_id, cloud_url = await storage_service.upload_file(
            file_content=contents,
            file_name=sanitized_name,
            session_id=str(session.session_id),
            content_type=file.content_type
        )

        # Create DB file record using the storage-generated file_id so both match
        file_record = models.File(
            file_id=str(storage_file_id),
            session_id=session.session_id,
            file_name=sanitized_name,
            file_type=file.content_type or file_path.suffix,
            file_size=len(contents),
            cloud_url=cloud_url
        )
        db.add(file_record)
        await db.commit()
        await db.refresh(file_record)
        
        # Extract text using LangChain document loaders and add to RAG vectorstore
        # Note: Images are handled directly by multimodal models (Gemini/Llama), no OCR needed
        try:
            from app.services.rag_service import rag_service
            from langchain_community.document_loaders import PyPDFLoader, TextLoader
            import tempfile
            import os

            # Determine file extension
            ext = sanitized_name.lower().split('.')[-1] if '.' in sanitized_name else ''

            # Skip image files - they'll be handled directly by multimodal models
            if ext in ['jpg', 'jpeg', 'png', 'webp']:
                logger.info(f"Image uploaded (no RAG processing): {sanitized_name}")
                return schemas.FileUploadResponse.model_validate(file_record)
            
            # Create a temporary file for the loader
            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}" if ext else None) as tmp_file:
                tmp_file.write(contents)
                tmp_file_path = tmp_file.name
            
            try:
                documents = []
                
                # Use appropriate LangChain loader based on file type
                if ext == 'pdf':
                    loader = PyPDFLoader(tmp_file_path)
                    documents = loader.load()
                    logger.info(f"Extracted {len(documents)} pages from PDF: {sanitized_name}")
                
                elif ext in ['txt', 'md', 'text']:
                    loader = TextLoader(tmp_file_path, encoding='utf-8')
                    documents = loader.load()
                    logger.info(f"Extracted text from {ext} file: {sanitized_name}")
                
                # Add metadata to all documents and add to vectorstore
                if documents:
                    for doc in documents:
                        doc.metadata.update({
                            'session_id': str(session.session_id),
                            'file_name': sanitized_name,
                            'source': file_record.cloud_url or sanitized_name,
                            'file_id': str(file_record.file_id),
                            'file_type': ext
                        })
                    
                    await rag_service.add_documents(documents)
                    logger.info(f"File processed and added to RAG: {sanitized_name}")
                else:
                    logger.warning(f"No content extracted from file {sanitized_name} (extension: {ext})")
                    
            finally:
                # Clean up temporary file
                try:
                    os.unlink(tmp_file_path)
                    logger.debug(f"Cleaned up temporary file: {tmp_file_path}")
                except Exception as e:
                    logger.warning(f"Could not delete temporary file {tmp_file_path}: {e}")
                    
        except Exception as e:
            logger.error(f"Error ingesting file for RAG: {e}", exc_info=True)

        return schemas.FileUploadResponse.model_validate(file_record)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error uploading file: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error uploading file: {str(e)}")


@router.get("/{session_id}", response_model=List[schemas.FileUploadResponse])
async def get_session_files(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get all files for a session"""
    logger.debug(f"Getting files for session: {session_id}")
    result = await db.execute(
        select(models.Session).where(models.Session.session_id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        logger.warning(f"Session not found when getting files: {session_id}")
        raise HTTPException(status_code=404, detail="Session not found")
    
    files_result = await db.execute(
        select(models.File)
        .where(models.File.session_id == session_id)
        .order_by(models.File.uploaded_at.desc())
    )
    files = files_result.scalars().all()
    logger.info(f"Retrieved {len(files)} file(s) for session {session_id}")
    return [schemas.FileUploadResponse.model_validate(f) for f in files]


@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Delete a file"""
    logger.info(f"Deleting file: {file_id}")
    result = await db.execute(
        select(models.File).where(models.File.file_id == file_id)
    )
    file_record = result.scalar_one_or_none()
    if not file_record:
        logger.warning(f"File not found for deletion: {file_id}")
        raise HTTPException(status_code=404, detail="File not found")
    
    # Delete from storage
    # Note: cloud_url is always set for uploaded files (contains local path like /uploads/...)
    # The storage service handles local storage deletion
    file_path = str(file_record.cloud_url) if file_record.cloud_url is not None else None
    if file_path:
        logger.debug(f"Deleting file from storage: {file_path}")
        deleted = await storage_service.delete_file(file_path)
        if not deleted:
            logger.warning(f"Failed to delete file from storage: {file_path}")
    else:
        logger.warning(f"File record {file_id} has no cloud_url/path, skipping storage deletion")
    
    # Delete from database
    await db.delete(file_record)
    await db.commit()
    logger.info(f"Deleted file: {file_id}")
    
    return {"message": "File deleted successfully"}
