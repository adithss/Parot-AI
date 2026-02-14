from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session
import tempfile
import os
import base64
from pathlib import Path
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Set
import jwt
import soundfile as sf
import asyncio
import aiohttp
import json
import time
from typing import Optional
# Import services
from translation_service import translate_meeting_content, get_available_languages
from transcription_service import transcribe_audio
from diarization_service import diarize_audio
from analysis_service import analyze_transcript
from chat_service import query_meeting_context
from spectrogram_service import create_spectrogram_image, cleanup_old_spectrograms

# Import database
from database import get_db, init_db, test_connection, models, schemas, crud

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

# WebSocket connections for collaborative meetings
active_ws_connections: Dict[str, Set[WebSocket]] = {}

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Parot Transcription API")

# Security
security = HTTPBearer()

# Mount static files directory for spectrograms
os.makedirs("static/spectrograms", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Clean up old spectrograms on startup
cleanup_old_spectrograms()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== JWT TOKEN FUNCTIONS ====================

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify JWT token and return user_id"""
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

# ==================== REQUEST MODELS ====================

class TranscribeRequest(BaseModel):
    audio_base64: str
    mime_type: str

class AnalyzeRequest(BaseModel):
    transcript: str

class QueryContextRequest(BaseModel):
    transcript: str
    summary: str
    sentiment: dict
    emotionAnalysis: list
    actionItems: list
    keyDecisions: list
    question: str

class ProcessRealtimeCompleteRequest(BaseModel):
    audio_base64: str
    mime_type: str

class TranslateRequest(BaseModel):
    content: dict
    target_language: str
    source_language: str = "en"
class ColabStreamManager:
    """
    Manages WebSocket connection to Colab backend for real-time transcription
    """
    
    def __init__(self, colab_url: str):
        self.colab_url = colab_url.rstrip('/')
        self.session: Optional[aiohttp.ClientSession] = None
        self.ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self.connected = False
        
    async def connect(self):
        """Connect to Colab WebSocket for streaming"""
        try:
            if not self.session:
                timeout = aiohttp.ClientTimeout(total=30)
                self.session = aiohttp.ClientSession(timeout=timeout)
            
            # Convert HTTP URL to WebSocket URL
            ws_url = self.colab_url.replace('http://', 'ws://').replace('https://', 'wss://')
            ws_url = f"{ws_url}/api/stream"
            
            logger.info(f"Connecting to Colab WebSocket: {ws_url}")
            
            self.ws = await self.session.ws_connect(ws_url)
            self.connected = True
            
            logger.info("✅ Connected to Colab backend")
            
        except Exception as e:
            logger.error(f"Failed to connect to Colab: {e}")
            raise
        
    async def send_audio(self, audio_chunk: bytes):
        """Send audio chunk to Colab for transcription"""
        if self.ws and self.connected:
            try:
                await self.ws.send_bytes(audio_chunk)
            except Exception as e:
                logger.error(f"Error sending audio to Colab: {e}")
                self.connected = False
                raise
    
    async def receive_transcription(self) -> Optional[dict]:
        """Receive transcription from Colab"""
        if self.ws and self.connected:
            try:
                msg = await asyncio.wait_for(self.ws.receive(), timeout=0.1)
                
                if msg.type == aiohttp.WSMsgType.TEXT:
                    return json.loads(msg.data)
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    logger.info("Colab WebSocket closed")
                    self.connected = False
                    return None
                    
            except asyncio.TimeoutError:
                return None
            except Exception as e:
                logger.error(f"Error receiving from Colab: {e}")
                return None
        
        return None
    
    async def stop(self):
        """Stop streaming and close connection"""
        try:
            if self.ws and self.connected:
                # Send stop signal to Colab
                await self.ws.send_json({"type": "stop"})
                await asyncio.sleep(0.5)  # Give Colab time to process
                await self.ws.close()
                
            if self.session:
                await self.session.close()
                
            self.connected = False
            logger.info("✅ Colab connection closed")
            
        except Exception as e:
            logger.error(f"Error closing Colab connection: {e}")
# ==================== STARTUP AND HEALTH ====================

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    logger.info("Testing database connection...")
    if test_connection():
        logger.info("Initializing database tables...")
        init_db()
        logger.info("Database initialization complete!")
    else:
        logger.error("Failed to connect to database. Please check your configuration.")

@app.get("/")
async def root():
    return {"message": "Parot Transcription API is running"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "API is running"}

# ==================== WEBSOCKET FOR COLLABORATIVE MEETINGS ====================

@app.websocket("/ws/meetings/{meeting_id}")
async def websocket_meeting_updates(
    websocket: WebSocket,
    meeting_id: str
):
    """WebSocket endpoint for real-time meeting updates"""
    await websocket.accept()
    
    # Add to active connections
    if meeting_id not in active_ws_connections:
        active_ws_connections[meeting_id] = set()
    active_ws_connections[meeting_id].add(websocket)
    
    logger.info(f"WebSocket connected for meeting {meeting_id}. Total connections: {len(active_ws_connections[meeting_id])}")
    
    try:
        while True:
            # Receive messages from clients
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                
                # Handle ping/pong for keepalive
                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                
                # 🚨 NEW: Handle host transcription broadcasts
                elif message.get("type") == "host_transcription":
                    transcription_data = message.get("data", {})
                    
                    # Broadcast to ALL participants (not back to host)
                    broadcast_message = {
                        "type": "host_transcription",
                        "data": transcription_data
                    }
                    
                    disconnected = set()
                    broadcast_count = 0
                    
                    for participant_ws in active_ws_connections[meeting_id]:
                        if participant_ws != websocket:  # Don't echo back to sender
                            try:
                                await participant_ws.send_json(broadcast_message)
                                broadcast_count += 1
                            except Exception as e:
                                logger.error(f"Failed to broadcast: {e}")
                                disconnected.add(participant_ws)
                    
                    # Remove disconnected
                    for ws in disconnected:
                        active_ws_connections[meeting_id].discard(ws)
                    
                    # Log
                    text_preview = transcription_data.get("text", "")[:50]
                    source = transcription_data.get("source", "unknown")
                    is_final = transcription_data.get("is_final", False)
                    logger.info(f"📡 Broadcast [{source}] to {broadcast_count} participants: '{text_preview}...' (final: {is_final})")
                    
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON received")
                
    except WebSocketDisconnect:
        # Remove from active connections
        active_ws_connections[meeting_id].discard(websocket)
        if not active_ws_connections[meeting_id]:
            del active_ws_connections[meeting_id]
        logger.info(f"WebSocket disconnected for meeting {meeting_id}")


@app.websocket("/ws/meetings/{meeting_id}/stream")
async def websocket_stream_transcription(
    websocket: WebSocket,
    meeting_id: str
):
    """
    WebSocket endpoint for HOST to stream audio and receive/broadcast live transcriptions
    
    Flow:
    1. Host connects and streams audio chunks
    2. Server forwards audio to Colab backend
    3. Server receives transcriptions from Colab
    4. Server broadcasts to all meeting participants
    
    Args:
        websocket: WebSocket connection from host
        meeting_id: ID of the collaborative meeting
    """
    await websocket.accept()
    logger.info(f"🎙️ Streaming connection established for meeting {meeting_id}")
    
    # Get Colab URL from environment
    colab_url = os.getenv("COLAB_URL")
    if not colab_url:
        logger.error("COLAB_URL not set in environment variables")
        await websocket.close(code=1008, reason="COLAB_URL not configured")
        return
    
    # Initialize stream manager
    stream_manager = ColabStreamManager(colab_url)
    listen_task = None
    
    try:
        # Connect to Colab backend
        await stream_manager.connect()
        
        # Send ready confirmation to host
        await websocket.send_json({
            "type": "stream_ready",
            "message": "Connected to transcription service",
            "meeting_id": meeting_id
        })
        
        # Background task to listen for transcriptions from Colab
        async def listen_and_broadcast():
            """
            Listen to Colab transcriptions and broadcast to all participants
            """
            sequence_number = 0
            
            while stream_manager.connected:
                try:
                    # Get transcription from Colab
                    transcription_data = await stream_manager.receive_transcription()
                    
                    if not transcription_data:
                        await asyncio.sleep(0.01)  # Small delay to prevent busy loop
                        continue
                    
                    # Parse transcription based on type
                    text = ""
                    is_final = False
                    source = ""
                    transcription_type = transcription_data.get("type", "")
                    
                    if transcription_type == "deepgram_transcript":
                        text = transcription_data.get("text", "")
                        is_final = transcription_data.get("is_final", False)
                        source = "deepgram"
                        
                    elif transcription_type == "medium_delta":
                        text = transcription_data.get("text", "")
                        is_final = True  # Medium updates are considered final
                        source = "medium"
                        
                    elif transcription_type == "large_result":
                        text = transcription_data.get("text", "")
                        is_final = True
                        source = "large"
                        
                    else:
                        # Unknown type, skip
                        continue
                    
                    if not text.strip():
                        continue
                    
                    # Increment sequence number
                    sequence_number += 1
                    timestamp_ms = int(time.time() * 1000)
                    
                    # Prepare broadcast message
                    broadcast_message = {
                        "type": "live_transcription",
                        "data": {
                            "text": text,
                            "is_final": is_final,
                            "sequence_number": sequence_number,
                            "timestamp_ms": timestamp_ms,
                            "source": source,
                            "meeting_id": meeting_id
                        }
                    }
                    
                    # Broadcast to ALL participants in the meeting
                    if meeting_id in active_ws_connections:
                        disconnected = set()
                        broadcast_count = 0
                        
                        for participant_ws in active_ws_connections[meeting_id]:
                            try:
                                await participant_ws.send_json(broadcast_message)
                                broadcast_count += 1
                            except Exception as e:
                                logger.error(f"Failed to broadcast to participant: {e}")
                                disconnected.add(participant_ws)
                        
                        # Remove disconnected participants
                        for ws in disconnected:
                            active_ws_connections[meeting_id].discard(ws)
                        
                        # Log broadcast
                        log_text = text[:50] + "..." if len(text) > 50 else text
                        logger.info(
                            f"📡 [{source}] Broadcast to {broadcast_count} participants: "
                            f"'{log_text}' (final: {is_final})"
                        )
                    
                    # Echo back to host for confirmation
                    try:
                        await websocket.send_json({
                            "type": "transcription_echo",
                            "data": {
                                "text": text,
                                "is_final": is_final,
                                "source": source,
                                "sequence_number": sequence_number
                            }
                        })
                    except Exception as e:
                        logger.error(f"Failed to echo to host: {e}")
                        break
                    
                except asyncio.CancelledError:
                    logger.info("Listen task cancelled")
                    break
                except Exception as e:
                    logger.error(f"Error in transcription listener: {e}")
                    await asyncio.sleep(0.1)  # Brief pause before retry
        
        # Start background listening task
        listen_task = asyncio.create_task(listen_and_broadcast())
        
        # Main loop: receive audio from host and forward to Colab
        while True:
            try:
                # Receive data from host
                data = await websocket.receive()
                
                # Handle binary audio data
                if "bytes" in data:
                    audio_chunk = data["bytes"]
                    
                    # Forward audio to Colab for transcription
                    try:
                        await stream_manager.send_audio(audio_chunk)
                    except Exception as e:
                        logger.error(f"Failed to send audio to Colab: {e}")
                        # Try to reconnect
                        try:
                            await stream_manager.connect()
                        except:
                            # If reconnection fails, close the stream
                            await websocket.send_json({
                                "type": "error",
                                "message": "Lost connection to transcription service"
                            })
                            break
                
                # Handle control messages (JSON)
                elif "text" in data:
                    try:
                        message = json.loads(data["text"])
                        msg_type = message.get("type")
                        
                        if msg_type == "ping":
                            # Respond to keepalive ping
                            await websocket.send_json({"type": "pong"})
                        
                        elif msg_type == "stop":
                            logger.info(f"🛑 Received stop signal for meeting {meeting_id}")
                            
                            # Stop Colab stream
                            await stream_manager.stop()
                            
                            # Cancel listener
                            if listen_task:
                                listen_task.cancel()
                                try:
                                    await listen_task
                                except asyncio.CancelledError:
                                    pass
                            
                            # Send confirmation
                            await websocket.send_json({
                                "type": "stream_stopped",
                                "message": "Transcription stream ended successfully"
                            })
                            
                            break
                            
                    except json.JSONDecodeError as e:
                        logger.error(f"Invalid JSON from host: {e}")
                
            except WebSocketDisconnect:
                logger.info(f"Host disconnected from streaming: {meeting_id}")
                break
                
            except Exception as e:
                logger.error(f"Error in main stream loop: {e}")
                break
        
    except Exception as e:
        logger.error(f"Fatal error in streaming endpoint: {e}")
        
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except:
            pass
        
    finally:
        # Cleanup
        logger.info(f"🧹 Cleaning up stream for meeting {meeting_id}")
        
        # Cancel listener task
        if listen_task and not listen_task.done():
            listen_task.cancel()
            try:
                await listen_task
            except asyncio.CancelledError:
                pass
        
        # Stop Colab stream
        try:
            await stream_manager.stop()
        except Exception as e:
            logger.error(f"Error stopping Colab stream: {e}")
        
        logger.info(f"🔌 Streaming connection closed for meeting {meeting_id}")

# ==================== AUTHENTICATION ENDPOINTS ====================

@app.post("/api/auth/signup", response_model=schemas.UserResponse)
async def signup(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """Register a new user"""
    try:
        # Check if user already exists
        existing_user = crud.get_user_by_email(db, user.email)
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered")
        
        # Create user
        db_user = crud.create_user(db, user)
        logger.info(f"New user created: {db_user.email}")
        return db_user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Signup error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Signup failed: {str(e)}")

@app.post("/api/auth/login")
async def login(user_login: schemas.UserLogin, db: Session = Depends(get_db)):
    """Login user and return access token"""
    try:
        # Authenticate user
        user = crud.authenticate_user(db, user_login.email, user_login.password)
        if not user:
            raise HTTPException(status_code=401, detail="Incorrect email or password")
        
        # Create access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.id}, expires_delta=access_token_expires
        )
        
        logger.info(f"User logged in: {user.email}")
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "full_name": user.full_name
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")

# ==================== MEETING ENDPOINTS ====================

@app.get("/api/meetings", response_model=List[schemas.MeetingResponse])
async def get_meetings(
    skip: int = 0,
    limit: int = 100,
    user_id: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Get all meetings for the authenticated user"""
    try:
        meetings = crud.get_user_meetings(db, user_id, skip, limit)
        return meetings
    except Exception as e:
        logger.error(f"Error fetching meetings: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch meetings: {str(e)}")

@app.get("/api/meetings/{meeting_id}", response_model=schemas.CompleteMeetingResponse)
async def get_meeting(
    meeting_id: str,
    user_id: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Get complete meeting data by ID"""
    try:
        meeting = crud.get_complete_meeting(db, meeting_id)
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        # Check if user has access (owner or participant)
        if meeting.user_id != user_id and not crud.is_participant(db, meeting_id, user_id):
            raise HTTPException(status_code=403, detail="Not authorized to access this meeting")
        
        return meeting
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching meeting: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch meeting: {str(e)}")

@app.delete("/api/meetings/{meeting_id}")
async def delete_meeting(
    meeting_id: str,
    user_id: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Delete a meeting"""
    try:
        meeting = crud.get_meeting_by_id(db, meeting_id)
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        # Verify user owns this meeting
        if meeting.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to delete this meeting")
        
        success = crud.delete_meeting(db, meeting_id)
        if success:
            return {"success": True, "message": "Meeting deleted successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to delete meeting")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting meeting: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete meeting: {str(e)}")

# ==================== COLLABORATION ENDPOINTS ====================

@app.post("/api/meetings", response_model=schemas.MeetingResponse)
async def create_meeting(
    meeting: schemas.MeetingCreate,
    user_id: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Create a new meeting"""
    try:
        db_meeting = crud.create_meeting(db, user_id, meeting)
        logger.info(f"Meeting created: {db_meeting.id}")
        return db_meeting
    except Exception as e:
        logger.error(f"Create meeting error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create meeting: {str(e)}")

@app.post("/api/meetings/{meeting_id}/invite", response_model=schemas.MeetingInvitationResponse)
async def invite_user_to_meeting(
    meeting_id: str,
    invitation: schemas.MeetingInvitationCreate,
    user_id: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Invite a user to a meeting by username"""
    try:
        meeting = crud.get_meeting_by_id(db, meeting_id)
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        if not crud.is_host(db, meeting_id, user_id):
            raise HTTPException(status_code=403, detail="Only the host can invite participants")
        
        db_invitation = crud.create_invitation(
            db,
            meeting_id=meeting_id,
            inviter_user_id=user_id,
            invitee_username=invitation.invitee_username
        )
        
        if not db_invitation:
            raise HTTPException(status_code=404, detail="User not found")
        
        logger.info(f"Invitation created: {db_invitation.id}")
        return db_invitation
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating invitation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create invitation: {str(e)}")

@app.get("/api/invitations", response_model=List[schemas.MeetingInvitationResponse])
async def get_my_invitations(
    status: Optional[str] = None,
    user_id: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Get invitations for the authenticated user"""
    try:
        invitations = crud.get_user_invitations(db, user_id, status)
        return invitations
    except Exception as e:
        logger.error(f"Error fetching invitations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/invitations/{invitation_id}/respond")
async def respond_to_invitation(
    invitation_id: str,
    response: schemas.InvitationResponseRequest,
    user_id: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Accept or decline a meeting invitation"""
    try:
        invitation = db.query(models.MeetingInvitation).filter(
            models.MeetingInvitation.id == invitation_id
        ).first()
        
        if not invitation:
            raise HTTPException(status_code=404, detail="Invitation not found")
        
        if invitation.invitee_user_id != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")
        
        if response.status not in ["accepted", "declined"]:
            raise HTTPException(status_code=400, detail="Invalid status")
        
        updated_invitation = crud.respond_to_invitation(db, invitation_id, response.status)
        
        return {
            "success": True,
            "status": updated_invitation.status,
            "meeting_id": updated_invitation.meeting_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error responding to invitation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/meetings/{meeting_id}/participants", response_model=List[schemas.MeetingParticipantResponse])
async def get_meeting_participants(
    meeting_id: str,
    user_id: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Get all participants of a meeting"""
    try:
        meeting = crud.get_meeting_by_id(db, meeting_id)
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        if meeting.user_id != user_id and not crud.is_participant(db, meeting_id, user_id):
            raise HTTPException(status_code=403, detail="Not authorized to view participants")
        
        participants = crud.get_meeting_participants(db, meeting_id)
        return participants
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching participants: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/meetings/{meeting_id}/participants/{participant_user_id}")
async def remove_participant(
    meeting_id: str,
    participant_user_id: str,
    user_id: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Remove a participant from a meeting"""
    try:
        if not crud.is_host(db, meeting_id, user_id):
            raise HTTPException(status_code=403, detail="Only the host can remove participants")
        
        meeting = crud.get_meeting_by_id(db, meeting_id)
        if meeting.host_user_id == participant_user_id:
            raise HTTPException(status_code=400, detail="Cannot remove the host")
        
        success = crud.remove_participant(db, meeting_id, participant_user_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Participant not found")
        
        return {"success": True, "message": "Participant removed"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing participant: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/users/search")
async def search_users(
    q: str,
    limit: int = 10,
    user_id: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Search for users by username or email"""
    try:
        if len(q) < 2:
            return []
        
        users = crud.search_users(db, q, limit)
        
        return [
            {
                "id": user.id,
                "username": user.username,
                "full_name": user.full_name,
                "email": user.email
            }
            for user in users
        ]
        
    except Exception as e:
        logger.error(f"Error searching users: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/meetings/{meeting_id}/start")
async def start_meeting(
    meeting_id: str,
    user_id: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Start a collaborative meeting (mark as live)"""
    try:
        if not crud.is_host(db, meeting_id, user_id):
            raise HTTPException(status_code=403, detail="Only the host can start the meeting")
        
        meeting = crud.start_meeting(db, meeting_id)
        
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        return {
            "success": True,
            "meeting_id": meeting.id,
            "is_live": meeting.is_live,
            "started_at": meeting.started_at
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting meeting: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/meetings/{meeting_id}/end")
async def end_meeting(
    meeting_id: str,
    user_id: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """End a collaborative meeting"""
    try:
        if not crud.is_host(db, meeting_id, user_id):
            raise HTTPException(status_code=403, detail="Only the host can end the meeting")
        
        meeting = crud.end_meeting(db, meeting_id)
        
        if not meeting:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        return {
            "success": True,
            "meeting_id": meeting.id,
            "is_live": meeting.is_live,
            "ended_at": meeting.ended_at
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error ending meeting: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/meetings/{meeting_id}/realtime-updates")
async def add_realtime_update(
    meeting_id: str,
    update: schemas.RealtimeUpdateCreate,
    user_id: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Add a real-time transcript update and broadcast to WebSocket clients"""
    try:
        if not crud.is_participant(db, meeting_id, user_id):
            raise HTTPException(
                status_code=403,
                detail="Not authorized to add updates to this meeting"
            )
        
        db_update = crud.add_realtime_update(db, meeting_id, update)
        
        # Broadcast to WebSocket clients
        if meeting_id in active_ws_connections:
            message = {
                "type": "transcript_update",
                "data": {
                    "id": db_update.id,
                    "text": db_update.text,
                    "speaker_label": db_update.speaker_label,
                    "sequence_number": db_update.sequence_number,
                    "is_final": db_update.is_final,
                    "timestamp_ms": db_update.timestamp_ms
                }
            }
            
            disconnected = set()
            for ws in active_ws_connections[meeting_id]:
                try:
                    await ws.send_json(message)
                except Exception as e:
                    logger.error(f"Failed to send WebSocket message: {e}")
                    disconnected.add(ws)
            
            for ws in disconnected:
                active_ws_connections[meeting_id].discard(ws)
            
            logger.info(f"Broadcasted update to {len(active_ws_connections[meeting_id])} clients")
        
        return db_update
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Add realtime update error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to add realtime update: {str(e)}"
        )

@app.get("/api/meetings/{meeting_id}/realtime-updates")
async def get_realtime_updates(
    meeting_id: str,
    after_sequence: Optional[int] = None,
    limit: int = 100,
    user_id: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Get real-time transcript updates for a meeting"""
    try:
        if not crud.is_participant(db, meeting_id, user_id) and not crud.is_host(db, meeting_id, user_id):
            raise HTTPException(status_code=403, detail="Not authorized")
        
        updates = crud.get_realtime_updates(db, meeting_id, after_sequence, limit)
        crud.update_participant_last_seen(db, meeting_id, user_id)
        
        return updates
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching realtime updates: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== TRANSCRIPTION & ANALYSIS ENDPOINTS ====================

@app.post("/api/transcribe")
async def transcribe_endpoint(
    request: TranscribeRequest,
    user_id: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Endpoint to transcribe and diarize audio file from Base64"""
    temp_file_path = None
    
    try:
        logger.info(f"Received audio data, mime_type: {request.mime_type}")
        
        # Decode Base64 audio
        try:
            audio_data = base64.b64decode(request.audio_base64)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid Base64 data: {str(e)}")
        
        # Determine file extension from MIME type
        mime_to_ext = {
            "audio/mpeg": ".mp3",
            "audio/mp3": ".mp3",
            "audio/wav": ".wav",
            "audio/x-wav": ".wav",
            "audio/webm": ".webm",
            "audio/ogg": ".ogg",
        }
        suffix = mime_to_ext.get(request.mime_type, ".wav")
        
        # Create a temporary file to store the audio
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(audio_data)
            temp_file_path = temp_file.name
        
        logger.info(f"Saved temporary file: {temp_file_path}")
        
        # Step 1: Transcribe audio using Faster Whisper
        logger.info("Starting transcription...")
        transcription_result = transcribe_audio(temp_file_path)
        
        if not transcription_result or len(transcription_result) == 0:
            raise Exception("No transcription generated. The audio file may be empty or contain no speech.")
        
        # Step 2: Diarize audio using Pyannote
        logger.info("Starting diarization...")
        diarization_result = diarize_audio(temp_file_path)
        
        # Step 3: Combine transcription with diarization
        logger.info("Combining transcription with diarization...")
        combined_transcript = combine_transcription_and_diarization(
            transcription_result,
            diarization_result
        )
        
        # Step 4: Generate spectrogram image
        logger.info("Generating spectrogram image...")
        spectrogram_path = None
        try:
            spectrogram_path = create_spectrogram_image(temp_file_path)
            logger.info(f"Spectrogram generated: {spectrogram_path}")
        except Exception as spec_error:
            logger.error(f"Failed to generate spectrogram: {spec_error}")
        
        logger.info("Transcription and diarization complete")
        
        # Build response
        response_data = {
            "success": True,
            "transcript": combined_transcript,
            "speakers": list(set([segment["speaker"] for segment in diarization_result]))
        }
        
        # Add spectrogram URL if generated
        if spectrogram_path:
            response_data["spectrogramUrl"] = f"/{spectrogram_path}"
        
        return JSONResponse(response_data)
            
    except Exception as e:
        logger.error(f"Error during transcription: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
        
    finally:
        # Clean up temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
                logger.info(f"Cleaned up temporary file: {temp_file_path}")
            except Exception as e:
                logger.error(f"Failed to delete temporary file: {str(e)}")

@app.post("/api/analyze")
async def analyze_endpoint(
    request: AnalyzeRequest,
    user_id: str = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Endpoint to analyze transcript using Gemini and save to database"""
    try:
        transcript = request.transcript
        
        if not transcript or not transcript.strip():
            raise HTTPException(status_code=400, detail="Transcript is required and cannot be empty")
        
        logger.info(f"Starting analysis for transcript of length {len(transcript)}...")
        analysis_result = analyze_transcript(transcript)
        
        logger.info("Analysis complete")
        
        # Parse the transcript into diarized segments
        diarized_segments = []
        if isinstance(transcript, str) and ":" in transcript:
            segments = transcript.split("\n\n")
            for segment in segments:
                segment = segment.strip()
                if ":" in segment:
                    parts = segment.split(":", 1)
                    if len(parts) == 2:
                        diarized_segments.append({
                            "speaker": parts[0].strip(),
                            "text": parts[1].strip()
                        })
        
        if not diarized_segments:
            diarized_segments = [{"speaker": "Speaker", "text": transcript}]
        
        # Save to database
        try:
            logger.info("Saving meeting data to database...")
            meeting_data = {
                "title": f"Meeting - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                "description": "Audio analysis"
            }
            
            analysis_data = {
                "diarizedTranscript": diarized_segments,
                "summary": analysis_result.get("summary", ""),
                "sentiment": analysis_result.get("sentiment", {}),
                "emotionAnalysis": analysis_result.get("emotionAnalysis", []),
                "actionItems": analysis_result.get("actionItems", []),
                "keyDecisions": analysis_result.get("keyDecisions", []),
                "speakers": list(set([seg["speaker"] for seg in diarized_segments]))
            }
            
            meeting = crud.save_complete_meeting_data(
                db=db,
                user_id=user_id,
                meeting_data=meeting_data,
                analysis_data=analysis_data
            )
            
            logger.info(f"Meeting saved with ID: {meeting.id}")
            
        except Exception as db_error:
            logger.error(f"Database save error: {str(db_error)}")
            # Continue even if database save fails
        
        # Return the analysis result
        return JSONResponse({
            "success": True,
            "analysis": {
                "diarizedTranscript": diarized_segments,
                "summary": analysis_result.get("summary", ""),
                "sentiment": analysis_result.get("sentiment", {"overall": "Neutral", "highlights": []}),
                "emotionAnalysis": analysis_result.get("emotionAnalysis", []),
                "actionItems": analysis_result.get("actionItems", []),
                "keyDecisions": analysis_result.get("keyDecisions", [])
            },
            "meetingId": meeting.id if 'meeting' in locals() else None
        })
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during analysis: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.post("/api/query-context")
async def query_context_endpoint(request: QueryContextRequest):
    """Query meeting context using chat"""
    try:
        answer = query_meeting_context(
            request.transcript,
            request.summary,
            request.sentiment,
            request.emotionAnalysis,
            request.actionItems,
            request.keyDecisions,
            request.question
        )
        return JSONResponse({"success": True, "answer": answer})
    except Exception as e:
        logger.error(f"Query context error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")

@app.post("/api/process-realtime-complete")
async def process_realtime_complete_endpoint(
    request: ProcessRealtimeCompleteRequest,
    user_id: str = Depends(verify_token),
    db: Session = Depends(get_db),
    is_collaborative: bool = Query(False),
    meeting_id: Optional[str] = Query(None)
):
    """Process complete real-time recording with transcription, diarization, and analysis"""
    temp_file_path = None
    converted_wav_path = None
    
    try:
        logger.info("Processing real-time complete recording...")
        
        # Decode base64 audio
        audio_data = base64.b64decode(request.audio_base64)
        logger.info(f"Decoded audio data: {len(audio_data)} bytes, mime_type: {request.mime_type}")
        
        # Determine file extension
        mime_to_ext = {
            "audio/mpeg": ".mp3",
            "audio/mp3": ".mp3",
            "audio/wav": ".wav",
            "audio/x-wav": ".wav",
            "audio/webm": ".webm",
            "audio/ogg": ".ogg",
        }
        suffix = mime_to_ext.get(request.mime_type, ".webm")
        
        # Save temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(audio_data)
            temp_file_path = temp_file.name
        
        logger.info(f"Saved temporary file: {temp_file_path} ({os.path.getsize(temp_file_path)} bytes)")
        
        # ========== CRITICAL FIX: PROPER WAV CONVERSION ==========
        # Convert to WAV if needed - using the EXACT pattern from your working code
        import subprocess
        
        # ALWAYS convert to ensure proper format - even if it's already .wav
        # Create converted file path using the EXACT pattern that works
        converted_wav_path = temp_file_path.replace(suffix, "_converted.wav")
        
        logger.info(f"Converting to WAV format...")
        logger.info(f"Input: {temp_file_path}")
        logger.info(f"Output: {converted_wav_path}")
        
        try:
            # Use FFmpeg with EXACT settings that work
            ffmpeg_result = subprocess.run([
                "ffmpeg",
                "-i", temp_file_path,
                "-ar", "16000",      # 16kHz sample rate
                "-ac", "1",          # Mono
                "-c:a", "pcm_s16le", # 16-bit PCM
                "-y",                # Overwrite
                converted_wav_path
            ], check=True, capture_output=True, text=True, timeout=60)
            
            logger.info(f"FFmpeg conversion completed successfully")
            
            # Verify the converted file exists and has content
            if not os.path.exists(converted_wav_path):
                raise Exception("FFmpeg did not create the converted file")
            
            converted_size = os.path.getsize(converted_wav_path)
            logger.info(f"Converted file size: {converted_size} bytes")
            
            if converted_size < 1000:
                raise Exception(f"Converted file is suspiciously small: {converted_size} bytes")
            
            # THIS IS THE KEY: Use the converted file for processing
            audio_file_for_processing = converted_wav_path
            logger.info(f"✓ Will use converted file: {audio_file_for_processing}")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg conversion failed with return code {e.returncode}")
            logger.error(f"FFmpeg stderr: {e.stderr}")
            raise Exception(f"Audio conversion failed: {e.stderr}")
            
        except subprocess.TimeoutExpired:
            raise Exception("FFmpeg conversion timed out after 60 seconds")
            
        except FileNotFoundError:
            logger.error("FFmpeg not found. Please install FFmpeg.")
            raise Exception("FFmpeg is not installed. Please install it to process audio.")
        
        # ========== END OF CRITICAL FIX ==========
        
        # Transcribe
        logger.info("Starting transcription...")
        transcription_result = transcribe_audio(audio_file_for_processing)
        
        if not transcription_result or len(transcription_result) == 0:
            raise Exception("No transcription generated.")
        
        logger.info(f"✓ Transcription complete: {len(transcription_result)} segments")
        
        # Diarize
        logger.info("Starting diarization...")
        diarization_result = diarize_audio(audio_file_for_processing)
        
        logger.info(f"✓ Diarization complete: {len(diarization_result)} segments")

        
        # Combine
        combined_transcript = combine_transcription_and_diarization(
            transcription_result,
            diarization_result
        )
        
        # Analyze
        logger.info("Starting analysis...")
        analysis_result = analyze_transcript(combined_transcript)
        
        # Generate spectrogram
        spectrogram_path = None
        try:
            spectrogram_path = create_spectrogram_image(audio_file_for_processing)
            logger.info(f"✓ Spectrogram generated")
        except Exception as spec_error:
            logger.error(f"Failed to generate spectrogram: {spec_error}")
        
        # Format diarized segments
        diarized_segments = []
        current_speaker = None
        current_text = []
        
        for segment in diarization_result:
            speaker = segment["speaker"]
            segment_texts = []
            for trans_seg in transcription_result:
                if (trans_seg["start"] < segment["end"] and 
                    trans_seg["end"] > segment["start"]):
                    segment_texts.append(trans_seg["text"])
            
            segment_text = " ".join(segment_texts).strip()
            
            if segment_text:
                if speaker == current_speaker:
                    current_text.append(segment_text)
                else:
                    if current_speaker and current_text:
                        diarized_segments.append({
                            "speaker": current_speaker,
                            "text": " ".join(current_text)
                        })
                    current_speaker = speaker
                    current_text = [segment_text]
        
        if current_speaker and current_text:
            diarized_segments.append({
                "speaker": current_speaker,
                "text": " ".join(current_text)
            })
        
        # Save to database with collaboration support
        try:
            logger.info("Saving meeting to database...")
            meeting_data = {
                "title": f"{'Collaborative ' if is_collaborative else ''}Meeting - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                "description": "Real-time recording"
            }
            
            analysis_data = {
                "diarizedTranscript": diarized_segments,
                "summary": analysis_result.get("summary", ""),
                "sentiment": analysis_result.get("sentiment", {}),
                "emotionAnalysis": analysis_result.get("emotionAnalysis", []),
                "actionItems": analysis_result.get("actionItems", []),
                "keyDecisions": analysis_result.get("keyDecisions", []),
                "speakers": list(set([segment["speaker"] for segment in diarization_result]))
            }
            
            # Handle collaborative meetings
            if meeting_id:
                meeting = crud.get_meeting_by_id(db, meeting_id)
                if meeting:
                    # Update existing collaborative meeting
                    crud.save_complete_meeting_data(
                        db=db,
                        user_id=meeting.user_id,
                        meeting_data={
                            "title": meeting.title,
                            "description": meeting.description or "Real-time recording"
                        },
                        analysis_data=analysis_data,
                        spectrogram_url=f"/{spectrogram_path}" if spectrogram_path else None,
                        is_collaborative=True,
                        meeting_id=meeting_id
                    )
                    
                    crud.update_meeting(db, meeting_id, schemas.MeetingUpdate(
                        status="completed",
                        is_live=False,
                        ended_at=datetime.now()
                    ))
                    
                    # Broadcast to WebSocket clients
                    if meeting_id in active_ws_connections:
                        completion_message = {
                            "type": "analysis_complete",
                            "data": {
                                "meetingId": meeting_id,
                                "analysis": {
                                    "diarizedTranscript": diarized_segments,
                                    "summary": analysis_result.get("summary", ""),
                                    "sentiment": analysis_result.get("sentiment", {}),
                                    "emotionAnalysis": analysis_result.get("emotionAnalysis", []),
                                    "actionItems": analysis_result.get("actionItems", []),
                                    "keyDecisions": analysis_result.get("keyDecisions", [])
                                },
                                "spectrogramUrl": f"/{spectrogram_path}" if spectrogram_path else None
                            }
                        }
                        
                        disconnected = set()
                        for ws in active_ws_connections[meeting_id]:
                            try:
                                await ws.send_json(completion_message)
                            except Exception as e:
                                logger.error(f"WebSocket send failed: {e}")
                                disconnected.add(ws)
                        
                        for ws in disconnected:
                            active_ws_connections[meeting_id].discard(ws)
                        
                        logger.info(f"Broadcasted to {len(active_ws_connections[meeting_id])} clients")
            else:
                # Create new meeting
                meeting = crud.save_complete_meeting_data(
                    db=db,
                    user_id=user_id,
                    meeting_data=meeting_data,
                    analysis_data=analysis_data,
                    spectrogram_url=f"/{spectrogram_path}" if spectrogram_path else None,
                    is_collaborative=is_collaborative
                )
            
            logger.info(f"✓ Meeting saved: {meeting.id}")
            
        except Exception as db_error:
            logger.error(f"Database save error: {str(db_error)}")
            import traceback
            logger.error(traceback.format_exc())
        
        # Return response
        response_data = {
            "success": True,
            "analysis": {
                "diarizedTranscript": diarized_segments,
                "summary": analysis_result.get("summary", ""),
                "sentiment": analysis_result.get("sentiment", {
                    "overall": "Neutral",
                    "highlights": []
                }),
                "emotionAnalysis": analysis_result.get("emotionAnalysis", []),
                "actionItems": analysis_result.get("actionItems", []),
                "keyDecisions": analysis_result.get("keyDecisions", [])
            }
        }
        
        if spectrogram_path:
            response_data["spectrogramUrl"] = f"/{spectrogram_path}"
        
        if 'meeting' in locals():
            response_data["meetingId"] = meeting.id
        
        return JSONResponse(response_data)
            
    except Exception as e:
        logger.error(f"Error during real-time processing: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")
        
    finally:
        # Cleanup temporary files
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
                logger.info(f"Cleaned up: {temp_file_path}")
            except Exception as e:
                logger.error(f"Failed to delete {temp_file_path}: {str(e)}")
        
        if converted_wav_path and os.path.exists(converted_wav_path):
            try:
                os.unlink(converted_wav_path)
                logger.info(f"Cleaned up: {converted_wav_path}")
            except Exception as e:
                logger.error(f"Failed to delete {converted_wav_path}: {str(e)}")


def combine_transcription_and_diarization(transcription_segments, diarization_segments):
    """Combine transcription segments with speaker diarization"""
    combined = []
    
    for trans_seg in transcription_segments:
        trans_start = trans_seg["start"]
        trans_end = trans_seg["end"]
        trans_text = trans_seg["text"]
        
        speaker = "Unknown"
        max_overlap = 0
        
        for diar_seg in diarization_segments:
            diar_start = diar_seg["start"]
            diar_end = diar_seg["end"]
            
            overlap_start = max(trans_start, diar_start)
            overlap_end = min(trans_end, diar_end)
            overlap = max(0, overlap_end - overlap_start)
            
            if overlap > max_overlap:
                max_overlap = overlap
                speaker = diar_seg["speaker"]
        
        combined.append({
            "start": trans_start,
            "end": trans_end,
            "text": trans_text,
            "speaker": speaker
        })
    
    formatted_transcript = ""
    current_speaker = None
    
    for segment in combined:
        if segment["speaker"] != current_speaker:
            if formatted_transcript:
                formatted_transcript += "\n\n"
            formatted_transcript += f"{segment['speaker']}: "
            current_speaker = segment["speaker"]
        else:
            formatted_transcript += " "
        formatted_transcript += segment["text"]
    
    return formatted_transcript.strip()

# ==================== TRANSLATION ENDPOINTS ====================

@app.get("/api/languages")
async def get_languages_endpoint():
    """Get available translation languages"""
    try:
        languages = get_available_languages()
        return JSONResponse({"success": True, "languages": languages})
    except Exception as e:
        logger.error(f"Error fetching languages: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch languages: {str(e)}")

@app.post("/api/translate")
async def translate_endpoint(request: TranslateRequest):
    """Translate meeting content"""
    try:
        if not request.content:
            raise HTTPException(status_code=400, detail="Content is required")
        
        logger.info(f"Translating content to {request.target_language}...")
        translated_content = translate_meeting_content(
            request.content, request.target_language, request.source_language
        )
        
        return JSONResponse({"success": True, "translated_content": translated_content})
    except Exception as e:
        logger.error(f"Translation error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Translation failed: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")