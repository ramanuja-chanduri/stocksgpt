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
from langchain_core.messages import SystemMessage
from app.core.logging_config import get_logger

logger = get_logger(__name__)

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
        
        # Retrieve file records based on file_ids in the request
        # Design: Files are saved locally with file_ids. If a file_id is referenced 
        # in a chat message with the same session_id, that file is sent to the LLM.
        file_records = []
        if request.file_ids:
            # Explicit file_ids provided: retrieve only those files that belong to this session
            files_result = await db.execute(
                select(models.File)
                .where(models.File.file_id.in_(request.file_ids))
                .where(models.File.session_id == session.session_id)  # Security: ensure file belongs to session
            )
            file_records = files_result.scalars().all()
            logger.info(f"Retrieved {len(file_records)} file(s) for specified file_ids: {request.file_ids}")
        else:
            # No file_ids specified: include all files for this session (convenience feature)
            # This allows users to reference uploaded files without explicitly passing file_ids
            files_result = await db.execute(
                select(models.File)
                .where(models.File.session_id == session.session_id)
                .order_by(models.File.uploaded_at.desc())
            )
            file_records = files_result.scalars().all()
            if file_records:
                logger.info(f"No file_ids provided, retrieved all {len(file_records)} file(s) for session")
        
        if file_records:
            logger.info(f"Retrieved {len(file_records)} file(s) for chat request")
        
        # Determine which models to call (Groq and Gemini)
        call_groq = should_call_groq(request.model_preferences)
        call_gemini = should_call_gemini(request.model_preferences)
        
        # Execute workflow
        workflow_result = await workflow_service.execute(
            user_query=request.message,
            session_id=str(session.session_id),
            model_preferences=request.model_preferences,
            history=history,
            file_records=list(file_records) if file_records else None
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
                    
                    # Retrieve file records - if file_ids provided, use those; otherwise get all session files
                    file_records = []
                    file_ids = request_data.get("file_ids", [])
                    if file_ids:
                        files_result = await db.execute(
                            select(models.File)
                            .where(models.File.file_id.in_(file_ids))
                            .where(models.File.session_id == session.session_id)
                        )
                        file_records = files_result.scalars().all()
                    else:
                        # If no file_ids specified, get all files for this session
                        files_result = await db.execute(
                            select(models.File)
                            .where(models.File.session_id == session.session_id)
                            .order_by(models.File.uploaded_at.desc())
                        )
                        file_records = files_result.scalars().all()
                    
                    if file_records:
                        logger.info(f"Retrieved {len(file_records)} file(s) for streaming chat request")
                    
                    # Determine which models to call
                    call_groq = should_call_groq(model_preferences)
                    call_gemini = should_call_gemini(model_preferences)
                    
                    # Prepare messages with files and history using workflow service
                    system_prompt = """You are a helpful AI assistant. Provide clear, accurate, and conversational responses to user questions. 
                    Answer questions directly and naturally - do not generate code unless explicitly requested. 
                    For factual questions, provide straightforward answers based on your knowledge."""
                    
                    # Get RAG context
                    from app.services.rag_service import rag_service
                    context_results = await rag_service.search(message, k=5, session_id=str(session.session_id))
                    context_text = None
                    if context_results:
                        context_parts = []
                        for r in context_results:
                            content = r["content"]
                            metadata = r.get("metadata", {})
                            file_name = metadata.get("file_name", "Unknown file")
                            context_parts.append(f"[From {file_name}]\n{content}")
                        context_text = f"""The following information is from documents uploaded by the user. Use this information to answer their question accurately and in detail.

{chr(10).join(context_parts)}

Based on the above context, answer the user's question: {message}"""
                    
                    # Prepare messages with files
                    if file_records:
                        file_messages = await workflow_service._prepare_files_for_llm(list(file_records), message)
                        
                        # For Gemini
                        gemini_messages = []
                        if context_text:
                            gemini_messages.append(SystemMessage(content=context_text))
                        elif system_prompt:
                            gemini_messages.append(SystemMessage(content=system_prompt))
                        gemini_messages.extend(file_messages["gemini"])
                        
                        # For Groq
                        groq_messages = []
                        if context_text:
                            groq_messages.append(SystemMessage(content=context_text))
                        elif system_prompt:
                            groq_messages.append(SystemMessage(content=system_prompt))
                        groq_messages.extend(file_messages["groq"])
                    else:
                        # No files, use standard messages
                        messages = llm_service.prepare_messages(message, history, system_prompt)
                        if context_text:
                            messages.insert(0, SystemMessage(content=context_text))
                        gemini_messages = messages
                        groq_messages = messages
                    
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
                                llm_service.call_gpt(groq_messages, stream=True),
                                groq_response_content
                            )
                        ))
                    
                    if call_gemini:
                        tasks.append(asyncio.create_task(
                            _stream_model(
                                get_gemini_model_name(),
                                gemini_message_id,
                                llm_service.call_gemini(gemini_messages, stream=True),
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
