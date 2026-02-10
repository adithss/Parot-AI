from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import tempfile
import os
import base64
from pathlib import Path
import logging

from transcription_service import transcribe_audio
from diarization_service import diarize_audio
from analysis_service import analyze_transcript
from chat_service import query_meeting_context

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Parot Transcription API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

@app.get("/")
async def root():
    return {"message": "Parot Transcription API is running"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "API is running"}

@app.post("/api/transcribe")
async def transcribe_endpoint(request: TranscribeRequest):
    """
    Endpoint to transcribe and diarize audio file from Base64
    """
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
        
        logger.info("Transcription and diarization complete")
        
        return JSONResponse({
            "success": True,
            "transcript": combined_transcript,
            "speakers": list(set([segment["speaker"] for segment in diarization_result]))
        })
            
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
async def analyze_endpoint(request: AnalyzeRequest):
    """
    Endpoint to analyze transcript using Gemini
    """
    try:
        transcript = request.transcript
        
        if not transcript or not transcript.strip():
            raise HTTPException(status_code=400, detail="Transcript is required and cannot be empty")
        
        logger.info(f"Starting analysis for transcript of length {len(transcript)}...")
        analysis_result = analyze_transcript(transcript)
        
        logger.info("Analysis complete")
        
        # Parse the transcript into diarized segments if it's a string with speaker labels
        # Format: "Speaker 1: text\n\nSpeaker 2: text"
        diarized_segments = []
        if isinstance(transcript, str) and ":" in transcript:
            # Split by double newlines to get speaker segments
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
        
        # If no segments were parsed, create a default one
        if not diarized_segments:
            diarized_segments = [{"speaker": "Speaker", "text": transcript}]
        
        # Return the analysis result with diarizedTranscript as array
        return JSONResponse({
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
        })
        
    except Exception as e:
        logger.error(f"Error during analysis: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.post("/api/query-context")
async def query_context_endpoint(request: QueryContextRequest):
    """
    Endpoint to answer questions about the meeting using context.
    This returns a conversational answer, not structured data.
    """
    try:
        # Validate required fields
        if not request.question or not request.question.strip():
            raise HTTPException(status_code=400, detail="Question is required and cannot be empty")
        
        logger.info(f"Processing contextual query: {request.question}")
        
        # Format transcript from diarized segments if it's a list
        transcript_text = request.transcript
        
        # Use the new chat service to get a conversational answer
        answer = query_meeting_context(
            transcript=transcript_text,
            summary=request.summary,
            sentiment=request.sentiment,
            emotion_analysis=request.emotionAnalysis,
            action_items=request.actionItems,
            key_decisions=request.keyDecisions,
            question=request.question
        )
        
        logger.info("Context query complete")
        
        return JSONResponse({
            "success": True,
            "answer": answer
        })
        
    except Exception as e:
        logger.error(f"Error during context query: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Context query failed: {str(e)}")

@app.post("/api/process-realtime-complete")
async def process_realtime_complete_endpoint(request: ProcessRealtimeCompleteRequest):
    """
    Process complete real-time audio after recording finishes.
    Receives audio as base64, runs diarization and Gemini analysis.
    Same flow as /api/transcribe + /api/analyze but combined.
    """
    temp_file_path = None
    
    try:
        logger.info(f"Received real-time audio data, mime_type: {request.mime_type}")
        
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
        logger.info("Starting transcription for real-time audio...")
        transcription_result = transcribe_audio(temp_file_path)
        
        if not transcription_result or len(transcription_result) == 0:
            raise Exception("No transcription generated. The audio file may be empty or contain no speech.")
        
        # Step 2: Diarize audio using Pyannote
        logger.info("Starting diarization for real-time audio...")
        diarization_result = diarize_audio(temp_file_path)
        
        # Step 3: Combine transcription with diarization
        logger.info("Combining transcription with diarization...")
        combined_transcript = combine_transcription_and_diarization(
            transcription_result,
            diarization_result
        )
        
        # Step 4: Analyze the transcript using Gemini
        logger.info("Starting Gemini analysis for real-time audio...")
        analysis_result = analyze_transcript(combined_transcript)
        
        logger.info("Real-time audio processing complete")
        
        # Format diarization result for frontend
        diarized_segments = []
        current_speaker = None
        current_text = []
        
        for segment in diarization_result:
            speaker = segment["speaker"]
            
            # Find corresponding transcription text for this time segment
            segment_texts = []
            for trans_seg in transcription_result:
                # Check if transcription segment overlaps with diarization segment
                if (trans_seg["start"] < segment["end"] and 
                    trans_seg["end"] > segment["start"]):
                    segment_texts.append(trans_seg["text"])
            
            segment_text = " ".join(segment_texts).strip()
            
            if segment_text:
                # Group consecutive segments from same speaker
                if speaker == current_speaker:
                    current_text.append(segment_text)
                else:
                    # Save previous speaker's text
                    if current_speaker and current_text:
                        diarized_segments.append({
                            "speaker": current_speaker,
                            "text": " ".join(current_text)
                        })
                    # Start new speaker
                    current_speaker = speaker
                    current_text = [segment_text]
        
        # Add the last speaker's text
        if current_speaker and current_text:
            diarized_segments.append({
                "speaker": current_speaker,
                "text": " ".join(current_text)
            })
        
        # Return complete analysis in the same format as audio upload
        return JSONResponse({
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
        })
            
    except Exception as e:
        logger.error(f"Error during real-time complete processing: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Real-time processing failed: {str(e)}")
        
    finally:
        # Clean up temporary file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
                logger.info(f"Cleaned up temporary file: {temp_file_path}")
            except Exception as e:
                logger.error(f"Failed to delete temporary file: {str(e)}")

def combine_transcription_and_diarization(transcription_segments, diarization_segments):
    """
    Combine transcription segments with speaker diarization
    """
    combined = []
    
    for trans_seg in transcription_segments:
        trans_start = trans_seg["start"]
        trans_end = trans_seg["end"]
        trans_text = trans_seg["text"]
        
        # Find the speaker for this time segment
        speaker = "Unknown"
        max_overlap = 0
        
        for diar_seg in diarization_segments:
            diar_start = diar_seg["start"]
            diar_end = diar_seg["end"]
            
            # Calculate overlap
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
    
    # Format as readable transcript
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")