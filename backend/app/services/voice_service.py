"""
Voice transcription service using Google Gemini 1.5 Flash (free tier).

Free tier: 15 requests/min, 1 million tokens/day.
Supported audio: webm, ogg, mp3, wav, aac, flac.
"""

import asyncio
import base64
import logging
from typing import Optional

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class VoiceServiceException(Exception):
    """Voice service specific exception."""

    pass


class VoiceService:
    """
    Transcribes audio recordings to text via Google Gemini 1.5 Flash.

    Uses lazy initialization — model is loaded on first transcription request.
    """

    # MIME types Gemini supports for audio
    SUPPORTED_MIME_TYPES = {
        "audio/webm",
        "audio/ogg",
        "audio/mp3",
        "audio/mpeg",
        "audio/wav",
        "audio/aac",
        "audio/flac",
    }

    def __init__(self):
        self._model = None
        self._initialized = False

    # ── Initialization ────────────────────────────────────────────────────────

    def _initialize(self) -> None:
        """Lazy-load the Gemini client on first use."""
        if self._initialized:
            return

        if not settings.GEMINI_API_KEY:
            raise VoiceServiceException(
                "GEMINI_API_KEY is not set. "
                "Get a free key at https://aistudio.google.com and add it to backend/.env"
            )

        try:
            import google.generativeai as genai
            from dotenv import dotenv_values

            # Force load directly from .env to bypass broken Windows system environment variables
            env_dict = dotenv_values(".env")
            gemini_key = env_dict.get("GEMINI_API_KEY", "")

            genai.configure(api_key=gemini_key)
            self._model = genai.GenerativeModel("gemini-2.0-flash-lite")
            self._initialized = True
            logger.info("Gemini voice service initialised (gemini-2.0-flash-lite)")
        except ImportError:
            raise VoiceServiceException(
                "google-generativeai package not installed. "
                "Run: pip install google-generativeai"
            )
        except Exception as e:
            raise VoiceServiceException(f"Failed to initialise Gemini: {e}")

    # ── Public API ────────────────────────────────────────────────────────────

    async def transcribe(
        self,
        audio_bytes: bytes,
        mime_type: str = "audio/webm",
    ) -> str:
        """
        Transcribe raw audio bytes to text.

        Args:
            audio_bytes: Raw audio data from the browser MediaRecorder API.
            mime_type:   MIME type reported by the browser (e.g. audio/webm).

        Returns:
            Transcribed text string.
        """
        if not audio_bytes:
            raise VoiceServiceException("Empty audio data received.")

        # Normalise MIME type (browser may send "audio/webm;codecs=opus")
        mime_type = mime_type.split(";")[0].strip().lower()
        if mime_type not in self.SUPPORTED_MIME_TYPES:
            logger.warning(
                f"Unsupported MIME type '{mime_type}', falling back to audio/webm"
            )
            mime_type = "audio/webm"

        # Run the blocking Gemini call in a thread pool
        loop = asyncio.get_event_loop()
        transcript = await loop.run_in_executor(
            None,
            self._transcribe_sync,
            audio_bytes,
            mime_type,
        )
        return transcript

    def is_available(self) -> bool:
        """Return True when GEMINI_API_KEY is configured."""
        return bool(settings.GEMINI_API_KEY)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _transcribe_sync(self, audio_bytes: bytes, mime_type: str) -> str:
        """Blocking Gemini API call — always run inside run_in_executor."""
        self._initialize()

        try:
            audio_b64 = base64.standard_b64encode(audio_bytes).decode("utf-8")

            response = self._model.generate_content(
                {
                    "parts": [
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": audio_b64,
                            }
                        },
                        {
                            "text": (
                                "Transcribe this audio accurately. "
                                "Return only the transcribed text — no labels, "
                                "no commentary, no formatting."
                            )
                        },
                    ]
                }
            )

            transcript = (response.text or "").strip()
            logger.info(
                f"Transcribed {len(audio_bytes):,} bytes → {len(transcript)} chars"
            )
            return transcript

        except Exception as e:
            logger.error(f"Gemini transcription error: {e}", exc_info=True)
            raise VoiceServiceException(f"Transcription failed: {e}")


# Singleton instance
voice_service = VoiceService()
