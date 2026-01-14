from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from typing import List
import asyncio
import json
import uuid

from app.core.database import get_db, AsyncSessionLocal
from app.core.model_utils import (
    should_call_groq, 
    should_call_gemini,
    get_groq_model_name,
    get_gemini_model_name
)
from app.models import models, schemas
from app.services.llm_service import llm_service
from app.services.workflow_service import workflow_service
from app.models.schemas import ChatRequest, ChatResponse, MessageResponse, StreamingChunk

router = APIRouter()


@router.post("", response_model=ChatResponse)
async def chat_endpoint(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    """Handle chat requests"""
    try:
        # Get or create session
        if request.session_id:
            result = await db.execute(
                select(models.Session).where(models.Session.session_id == request.session_id)
            )
            session = result.scalar_one_or_none()
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")
        else:
            # Create new session
            session = models.Session(
                session_id=str(uuid.uuid4()),
                title=request.message[:50] if request.message else None
            )
            db.add(session)
            await db.flush()
        
        # Save user message
        user_message = models.Message(
            session_id=session.session_id,
            role="user",
            content=request.message
        )
        db.add(user_message)
        await db.flush()
        
        # Get conversation history
        history_result = await db.execute(
            select(models.Message)
            .where(models.Message.session_id == session.session_id)
            .order_by(models.Message.created_at)
        )
        history_messages = history_result.scalars().all()
        
        # Convert to dict format
        # Exclude the current message (it's the last one we just inserted)
        history = [{"role": str(msg.role), "content": str(msg.content)} for msg in history_messages[:-1]]
        
        # Determine which models to call (Groq and Gemini)
        call_groq = should_call_groq(request.model_preferences)
        call_gemini = should_call_gemini(request.model_preferences)
        
        # Execute workflow
        workflow_result = await workflow_service.execute(
            user_query=request.message,
            session_id=str(session.session_id),
            model_preferences=request.model_preferences,
            history=history
        )
        
        # Helper function to save assistant messages
        async def save_assistant_message(role: str, model: str, content: str):
            """Save an assistant message and return the response"""
            if content:
                message = models.Message(
                    session_id=session.session_id,
                    role=role,
                    content=content,
                    model=model
                )
                db.add(message)
                await db.flush()
                return MessageResponse.model_validate(message)
            return None
        
        # Save responses
        responses = []
        if call_groq and workflow_result.get("gpt_response"):
            groq_response = await save_assistant_message(
                "assistant_gpt",
                get_groq_model_name(),
                workflow_result["gpt_response"]
            )
            if groq_response:
                responses.append(groq_response)
        
        if call_gemini and workflow_result.get("gemini_response"):
            gemini_response = await save_assistant_message(
                "assistant_gemini",
                get_gemini_model_name(),
                workflow_result["gemini_response"]
            )
            if gemini_response:
                responses.append(gemini_response)
        
        # Update session timestamp
        await db.execute(
            update(models.Session)
            .where(models.Session.session_id == session.session_id)
            .values(updated_at=func.now())
        )
        await db.commit()
        
        return ChatResponse(
            session_id=str(session.session_id),
            user_message_id=str(user_message.message_id),
            responses=responses,
            tool_calls=workflow_result.get("tool_results")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing chat: {str(e)}")


@router.websocket("/stream")
async def chat_stream(websocket: WebSocket):
    """WebSocket endpoint for streaming responses"""
    await websocket.accept()
    
    try:
        while True:
            data = await websocket.receive_text()
            request_data = json.loads(data)
            
            message = request_data.get("message")
            session_id = request_data.get("session_id")
            model_preferences = request_data.get(
                "model_preferences", 
                [get_groq_model_name(), get_gemini_model_name()]
            )
            
            if not message:
                await websocket.send_json({"error": "Message is required"})
                continue
            
            # Create database session for this request
            async with AsyncSessionLocal() as db:
                try:
                    # Get or create session
                    if session_id:
                        result = await db.execute(
                            select(models.Session).where(models.Session.session_id == session_id)
                        )
                        session = result.scalar_one_or_none()
                        if not session:
                            await websocket.send_json({
                                "error": "Session not found",
                                "session_id": session_id
                            })
                            continue
                    else:
                        # Create new session
                        session = models.Session(
                            session_id=str(uuid.uuid4()),
                            title=message[:50] if message else None
                        )
                        db.add(session)
                        await db.flush()
                    
                    # Save user message
                    user_message = models.Message(
                        session_id=session.session_id,
                        role="user",
                        content=message
                    )
                    db.add(user_message)
                    await db.flush()
                    
                    # Get conversation history
                    history_result = await db.execute(
                        select(models.Message)
                        .where(models.Message.session_id == session.session_id)
                        .order_by(models.Message.created_at)
                    )
                    history_messages = history_result.scalars().all()
                    
                    # Convert to dict format (exclude the current user message we just inserted)
                    history = [
                        {"role": str(msg.role), "content": str(msg.content)} 
                        for msg in history_messages[:-1]
                    ]
                    
                    # Determine which models to call
                    call_groq = should_call_groq(model_preferences)
                    call_gemini = should_call_gemini(model_preferences)
                    
                    # Prepare messages with history
                    messages = llm_service.prepare_messages(message, history)
                    
                    # Store session_id in a variable for closure
                    current_session_id = str(session.session_id)
                    
                    # Accumulators for streaming responses
                    groq_response_content = []
                    gemini_response_content = []
                    
                    async def _stream_model(model: str, message_id: str, iterator, accumulator: List[str]):
                        """Stream model response and accumulate chunks"""
                        try:
                            async for chunk in iterator:
                                accumulator.append(chunk)
                                await websocket.send_json({
                                    "session_id": current_session_id,
                                    "message_id": message_id,
                                    "model": model,
                                    "content": chunk,
                                    "done": False
                                })
                        except Exception as e:
                            await websocket.send_json({
                                "session_id": current_session_id,
                                "message_id": message_id,
                                "model": model,
                                "error": str(e),
                                "content": "",
                                "done": True
                            })
                            return
                        
                        await websocket.send_json({
                            "session_id": current_session_id,
                            "message_id": message_id,
                            "model": model,
                            "content": "",
                            "done": True
                        })
                    
                    # Stream both responses concurrently
                    tasks = []
                    groq_message_id = str(uuid.uuid4())
                    gemini_message_id = str(uuid.uuid4())
                    
                    if call_groq:
                        tasks.append(asyncio.create_task(
                            _stream_model(
                                get_groq_model_name(),
                                groq_message_id,
                                llm_service.call_gpt(messages, stream=True),
                                groq_response_content
                            )
                        ))
                    
                    if call_gemini:
                        tasks.append(asyncio.create_task(
                            _stream_model(
                                get_gemini_model_name(),
                                gemini_message_id,
                                llm_service.call_gemini(messages, stream=True),
                                gemini_response_content
                            )
                        ))
                    
                    if tasks:
                        await asyncio.gather(*tasks)
                    
                    # Save assistant responses to database
                    if call_groq and groq_response_content:
                        groq_message = models.Message(
                            session_id=session.session_id,
                            role="assistant_gpt",
                            content="".join(groq_response_content),
                            model=get_groq_model_name()
                        )
                        db.add(groq_message)
                    
                    if call_gemini and gemini_response_content:
                        gemini_message = models.Message(
                            session_id=session.session_id,
                            role="assistant_gemini",
                            content="".join(gemini_response_content),
                            model=get_gemini_model_name()
                        )
                        db.add(gemini_message)
                    
                    # Update session timestamp
                    await db.execute(
                        update(models.Session)
                        .where(models.Session.session_id == session.session_id)
                        .values(updated_at=func.now())
                    )
                    
                    await db.commit()
                    
                    # Send final confirmation with session_id
                    await websocket.send_json({
                        "session_id": current_session_id,
                        "user_message_id": str(user_message.message_id),
                        "status": "completed"
                    })
                    
                except Exception as e:
                    await db.rollback()
                    await websocket.send_json({
                        "error": f"Database error: {str(e)}",
                        "session_id": session_id or "unknown"
                    })
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"error": str(e)})
        except:
            pass  # WebSocket might already be closed
