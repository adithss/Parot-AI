from pyannote.audio import Pipeline
import torch
import logging
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("diarization_service")

_pipeline = None

HF_AUTH_TOKEN = os.getenv("HF_AUTH_TOKEN")


def get_pipeline():
    global _pipeline

    if _pipeline is not None:
        return _pipeline

    try:
        logger.info("Loading Pyannote speaker diarization pipeline...")
        
        if HF_AUTH_TOKEN:
            logger.info("HuggingFace token found in environment")
        else:
            logger.warning("No HuggingFace token found - this may cause authentication errors")

        # Use version 3.0 pipeline which is compatible with pyannote.audio 3.0.1
        _pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.0",
            use_auth_token=HF_AUTH_TOKEN
        )

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        _pipeline.to(device)

        logger.info(f"Pipeline loaded successfully on {device}")
        return _pipeline

    except Exception as e:
        logger.error(f"Failed to load pyannote pipeline - Full error: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None


def diarize_audio(audio_path: str):
    try:
        pipeline = get_pipeline()
        if pipeline is None:
            raise Exception(
                "Pyannote pipeline could not be loaded. "
                "Check the logs above for the specific error. "
                "Common issues: "
                "1. Model license not accepted at https://huggingface.co/pyannote/speaker-diarization-3.0 "
                "2. Missing HuggingFace authentication token in .env file "
                "3. Missing dependencies (pyannote.audio, torch)"
            )

        logger.info(f"Starting diarization for: {audio_path}")

        diarization = pipeline(audio_path)

        results = []
        for segment, _, speaker in diarization.itertracks(yield_label=True):
            results.append({
                "speaker": speaker,
                "start": float(segment.start),
                "end": float(segment.end)
            })

        logger.info(f"Diarization completed: {len(results)} segments found")
        return results

    except Exception as e:
        logger.error(f"Diarization error: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise Exception(f"Failed to diarize audio: {str(e)}")