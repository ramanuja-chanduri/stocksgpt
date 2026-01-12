from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from typing import List
import json
import uuid

from app.core.database import get_db
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
        history = [
            {"role": msg.role, "content": msg.content}
            for msg in history_messages
            if msg.message_id != user_message.message_id  # Exclude current message
        ]
        
        # Determine which models to call
        call_gpt = "gpt-4o" in request.model_preferences
        call_gemini = "gemini-2.0-flash" in request.model_preferences
        
        responses = []
        
        # Execute workflow
        workflow_result = await workflow_service.execute(
            user_query=request.message,
            session_id=session.session_id,
            model_preferences=request.model_preferences,
            history=history
        )
        
        # Save GPT response
        if call_gpt and workflow_result.get("gpt_response"):
            gpt_message = models.Message(
                session_id=session.session_id,
                role="assistant_gpt",
                content=workflow_result["gpt_response"],
                model="gpt-4o"
            )
            db.add(gpt_message)
            await db.flush()
            responses.append(MessageResponse.model_validate(gpt_message))
        
        # Save Gemini response
        if call_gemini and workflow_result.get("gemini_response"):
            gemini_message = models.Message(
                session_id=session.session_id,
                role="assistant_gemini",
                content=workflow_result["gemini_response"],
                model="gemini-2.0-flash"
            )
            db.add(gemini_message)
            await db.flush()
            responses.append(MessageResponse.model_validate(gemini_message))
        
        # Update session timestamp
        await db.execute(
            update(models.Session)
            .where(models.Session.session_id == session.session_id)
            .values(updated_at=func.now())
        )
        await db.commit()
        
        return ChatResponse(
            session_id=session.session_id,
            user_message_id=user_message.message_id,
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
            model_preferences = request_data.get("model_preferences", ["gpt-4o", "gemini-2.0-flash"])
            
            if not message:
                await websocket.send_json({"error": "Message is required"})
                continue
            
            # Get or create session (simplified for WebSocket)
            # In production, you'd want to properly handle this
            
            call_gpt = "gpt-4o" in model_preferences
            call_gemini = "gemini-2.0-flash" in model_preferences
            
            # Prepare messages
            messages = llm_service.prepare_messages(message)
            
            # Stream responses
            if call_gpt:
                message_id = str(uuid.uuid4())
                async for chunk in llm_service.call_gpt(messages, stream=True):
                    await websocket.send_json({
                        "session_id": session_id or "new",
                        "message_id": message_id,
                        "model": "gpt-4o",
                        "content": chunk,
                        "done": False
                    })
                await websocket.send_json({
                    "session_id": session_id or "new",
                    "message_id": message_id,
                    "model": "gpt-4o",
                    "content": "",
                    "done": True
                })
            
            if call_gemini:
                message_id = str(uuid.uuid4())
                async for chunk in llm_service.call_gemini(messages, stream=True):
                    await websocket.send_json({
                        "session_id": session_id or "new",
                        "message_id": message_id,
                        "model": "gemini-2.0-flash",
                        "content": chunk,
                        "done": False
                    })
                await websocket.send_json({
                    "session_id": session_id or "new",
                    "message_id": message_id,
                    "model": "gemini-2.0-flash",
                    "content": "",
                    "done": True
                })
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({"error": str(e)})
