from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List
from datetime import datetime, timedelta

from app.core.database import get_db
from app.models import models, schemas
from app.core.config import settings

router = APIRouter()


@router.get("", response_model=List[schemas.SessionResponse])
async def list_sessions(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """List all chat sessions"""
    result = await db.execute(
        select(models.Session)
        .order_by(models.Session.updated_at.desc())
        .limit(limit)
        .offset(offset)
    )
    sessions = result.scalars().all()
    return [schemas.SessionResponse.model_validate(s) for s in sessions]


@router.get("/{session_id}", response_model=schemas.SessionResponse)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific session"""
    result = await db.execute(
        select(models.Session).where(models.Session.session_id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return schemas.SessionResponse.from_orm(session)


@router.post("", response_model=schemas.SessionResponse)
async def create_session(
    session_data: schemas.SessionCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new session"""
    import uuid
    session = models.Session(
        session_id=str(uuid.uuid4()),
        title=session_data.title
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return schemas.SessionResponse.from_orm(session)


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Delete a session"""
    result = await db.execute(
        select(models.Session).where(models.Session.session_id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    await db.execute(
        delete(models.Session).where(models.Session.session_id == session_id)
    )
    await db.commit()
    return {"message": "Session deleted successfully"}


@router.get("/{session_id}/messages", response_model=List[schemas.MessageResponse])
async def get_session_messages(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get all messages for a session"""
    result = await db.execute(
        select(models.Session).where(models.Session.session_id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    messages_result = await db.execute(
        select(models.Message)
        .where(models.Message.session_id == session_id)
        .order_by(models.Message.created_at)
    )
    messages = messages_result.scalars().all()
    return [schemas.MessageResponse.model_validate(m) for m in messages]


@router.post("/cleanup")
async def cleanup_old_sessions(db: AsyncSession = Depends(get_db)):
    """Clean up sessions older than timeout period"""
    cutoff_time = datetime.utcnow() - timedelta(hours=settings.SESSION_TIMEOUT_HOURS)
    
    result = await db.execute(
        select(models.Session).where(models.Session.updated_at < cutoff_time)
    )
    old_sessions = result.scalars().all()
    
    for session in old_sessions:
        await db.execute(
            delete(models.Session).where(models.Session.session_id == session.session_id)
        )
    
    await db.commit()
    return {"message": f"Cleaned up {len(old_sessions)} old sessions"}
