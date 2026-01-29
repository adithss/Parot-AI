from faster_whisper import WhisperModel
import logging

logger = logging.getLogger(__name__)

# Initialize the Faster Whisper model
# Options: "tiny", "base", "small", "medium", "large-v2", "large-v3"
# Use "base" or "small" for faster processing, "medium" or "large-v3" for better accuracy
MODEL_SIZE = "base"
model = None

def get_model():
    """
    Lazy load the Whisper model
    """
    global model
    if model is None:
        logger.info(f"Loading Faster Whisper model: {MODEL_SIZE}")
        # device can be "cpu" or "cuda"
        # compute_type can be "int8", "float16", "float32"
        model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
        logger.info("Model loaded successfully")
    return model

def transcribe_audio(audio_path: str):
    """
    Transcribe audio file using Faster Whisper
    
    Args:
        audio_path: Path to the audio file
        
    Returns:
        List of transcription segments with timestamps
    """
    try:
        whisper_model = get_model()
        
        # Transcribe with word-level timestamps
        segments, info = whisper_model.transcribe(
            audio_path,
            beam_size=5,
            word_timestamps=True,
            vad_filter=True,  # Voice Activity Detection
            vad_parameters=dict(min_silence_duration_ms=500)
        )
        
        logger.info(f"Detected language: {info.language} with probability {info.language_probability}")
        
        # Convert generator to list and extract relevant information
        transcription_segments = []
        for segment in segments:
            transcription_segments.append({
                "start": segment.start,
                "end": segment.end,
                "text": segment.text.strip()
            })
            
        logger.info(f"Transcribed {len(transcription_segments)} segments")
        return transcription_segments
        
    except Exception as e:
        logger.error(f"Transcription error: {str(e)}")
        raise Exception(f"Failed to transcribe audio: {str(e)}")