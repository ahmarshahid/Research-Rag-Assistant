"""
Voice transcription API route — Phase 8 Voice Input.

POST /api/voice/transcribe  — transcribe audio → text (requires auth)
GET  /api/voice/health      — check whether GEMINI_API_KEY is configured
"""

from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.api.dependencies import get_current_user_id
from app.services.voice_service import VoiceServiceException, voice_service
from app.utils.logger import get_logger

router = APIRouter(prefix="/api", tags=["voice"])
logger = get_logger(__name__)

_MAX_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/voice/transcribe", response_model=dict, status_code=200)
async def transcribe_audio(
    audio: UploadFile = File(
        ..., description="Audio recording (webm / ogg / mp3 / wav)"
    ),
    user_id: UUID = Depends(get_current_user_id),
) -> dict:
    """
    Transcribe a voice recording to text using Google Gemini 1.5 Flash.

    - **Max size**: 10 MB
    - **Accepted formats**: audio/webm, audio/ogg, audio/mp3, audio/wav
    - **Returns**: `{ "text": "transcribed text" }`

    Requires `GEMINI_API_KEY` to be set in `backend/.env`.
    """
    if not voice_service.is_available():
        raise HTTPException(
            status_code=503,
            detail=(
                "Voice service is not configured. "
                "Add GEMINI_API_KEY to backend/.env "
                "(free key at https://aistudio.google.com)."
            ),
        )

    audio_bytes = await audio.read()

    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file.")

    if len(audio_bytes) > _MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Audio too large ({len(audio_bytes) // 1024} KB). Max 10 MB.",
        )

    try:
        mime_type = audio.content_type or "audio/webm"
        transcript = await voice_service.transcribe(audio_bytes, mime_type)

        if not transcript:
            raise HTTPException(
                status_code=422,
                detail="Could not transcribe audio — try speaking more clearly.",
            )

        logger.info(f"User {user_id} transcribed {len(audio_bytes):,} bytes")

        return {
            "text": transcript,
            "audio_size_bytes": len(audio_bytes),
            "mime_type": mime_type,
        }

    except VoiceServiceException as e:
        logger.error(f"Voice service error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Unexpected transcription error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Transcription failed.")


@router.get("/voice/health", response_model=dict, status_code=200)
async def voice_health() -> dict:
    """Check whether the voice transcription service is configured."""
    available = voice_service.is_available()
    return {
        "available": available,
        "model": "gemini-2.5-flash",
        "message": "Voice service ready"
        if available
        else "Set GEMINI_API_KEY in backend/.env to enable",
    }
