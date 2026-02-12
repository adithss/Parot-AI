from fastapi import FastAPI, File, UploadFile, HTTPException, Depends
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
from typing import Optional, List
import jwt

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
        
        # Verify user owns this meeting
        if meeting.user_id != user_id:
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
    db: Session = Depends(get_db)
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
        suffix = mime_to_ext.get(request.mime_type, ".webm")  # Default to webm for browser recordings
        
        # Save temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(audio_data)
            temp_file_path = temp_file.name
        
        logger.info(f"Saved temporary file: {temp_file_path}")
        
        # 🔧 FIX: Convert to proper WAV format for pyannote
        # Browser MediaRecorder creates WebM/Opus which pyannote can't read directly
        import subprocess
        converted_wav_path = temp_file_path.replace(suffix, "_converted.wav")
        
        try:
            # Use ffmpeg to convert to 16kHz mono WAV (required for pyannote)
            subprocess.run([
                "ffmpeg",
                "-i", temp_file_path,
                "-ar", "16000",  # Sample rate 16kHz
                "-ac", "1",      # Mono
                "-c:a", "pcm_s16le",  # 16-bit PCM
                "-y",            # Overwrite output
                converted_wav_path
            ], check=True, capture_output=True, text=True)
            
            logger.info(f"Converted audio to WAV: {converted_wav_path}")
            
            # Use the converted file for processing
            audio_file_for_processing = converted_wav_path
            
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg conversion failed: {e.stderr}")
            # Fallback: try using original file
            audio_file_for_processing = temp_file_path
        except FileNotFoundError:
            logger.warning("FFmpeg not found. Install ffmpeg for better audio format support.")
            # Fallback: try using original file
            audio_file_for_processing = temp_file_path
        
        # Transcribe
        logger.info("Starting transcription...")
        transcription_result = transcribe_audio(audio_file_for_processing)
        
        if not transcription_result or len(transcription_result) == 0:
            raise Exception("No transcription generated.")
        
        # Diarize
        logger.info("Starting diarization...")
        diarization_result = diarize_audio(audio_file_for_processing)
        
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
        
        # Save to database
        try:
            logger.info("Saving realtime meeting to database...")
            meeting_data = {
                "title": f"Real-time Meeting - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
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
            
            meeting = crud.save_complete_meeting_data(
                db=db,
                user_id=user_id,
                meeting_data=meeting_data,
                analysis_data=analysis_data,
                spectrogram_url=f"/{spectrogram_path}" if spectrogram_path else None
            )
            
            logger.info(f"Realtime meeting saved with ID: {meeting.id}")
            
        except Exception as db_error:
            logger.error(f"Database save error: {str(db_error)}")
        
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
        
        # Add meeting ID to response
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
            except Exception as e:
                logger.error(f"Failed to delete temporary file: {str(e)}")
        
        if converted_wav_path and os.path.exists(converted_wav_path):
            try:
                os.unlink(converted_wav_path)
            except Exception as e:
                logger.error(f"Failed to delete converted file: {str(e)}")


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