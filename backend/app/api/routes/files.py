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

router = APIRouter()


@router.post("/upload", response_model=schemas.FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    session_id: str = Form(None),
    db: AsyncSession = Depends(get_db)
):
    """Upload a file. session_id can be passed as a form field."""
    try:
        # Validate file size
        contents = await file.read()
        if len(contents) > settings.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size is {settings.MAX_FILE_SIZE / 1024 / 1024}MB"
            )
        
        # Validate file type
        file_path = Path(file.filename)
        if not validate_file_type(file_path, settings.ALLOWED_EXTENSIONS, file_contents=contents):
            raise HTTPException(
                status_code=400,
                detail=f"File type not allowed. Allowed types: {', '.join(settings.ALLOWED_EXTENSIONS)}"
            )
        
        # Get or create session
        if session_id:
            result = await db.execute(
                select(models.Session).where(models.Session.session_id == session_id)
            )
            session = result.scalar_one_or_none()
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")
        else:
            # Create new session
            session = models.Session(session_id=str(uuid.uuid4()))
            db.add(session)
            await db.flush()
        
        # Sanitize filename
        sanitized_name = sanitize_filename(file.filename)
        
        # Upload to storage
        cloud_url = await storage_service.upload_file(
            file_content=contents,
            file_name=sanitized_name,
            session_id=session.session_id,
            content_type=file.content_type
        )
        
        # Save file record
        file_record = models.File(
            session_id=session.session_id,
            file_name=sanitized_name,
            file_type=file.content_type or file_path.suffix,
            file_size=len(contents),
            cloud_url=cloud_url
        )
        db.add(file_record)
        await db.commit()
        await db.refresh(file_record)
        
        return schemas.FileUploadResponse.model_validate(file_record)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading file: {str(e)}")


@router.get("/{session_id}", response_model=List[schemas.FileUploadResponse])
async def get_session_files(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get all files for a session"""
    result = await db.execute(
        select(models.Session).where(models.Session.session_id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    files_result = await db.execute(
        select(models.File)
        .where(models.File.session_id == session_id)
        .order_by(models.File.uploaded_at.desc())
    )
    files = files_result.scalars().all()
    return [schemas.FileUploadResponse.model_validate(f) for f in files]


@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Delete a file"""
    result = await db.execute(
        select(models.File).where(models.File.file_id == file_id)
    )
    file_record = result.scalar_one_or_none()
    if not file_record:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Delete from storage
    if file_record.cloud_url:
        await storage_service.delete_file(file_record.cloud_url)
    
    # Delete from database
    await db.delete(file_record)
    await db.commit()
    
    return {"message": "File deleted successfully"}
