"""
voice/transcriber.py — Speech-to-Text using OpenAI Whisper (local)

Whisper runs 100% offline on your PC.
Model sizes: tiny (fast) → base → small → medium → large (accurate)
Recommended: "base" for most laptops, "small" for good GPUs.
"""
import numpy as np
from utils.logger import logger
from utils.config import get


class Transcriber:
    """Wraps faster-whisper for efficient local transcription."""

    def __init__(self):
        self._model = None
        self.model_size = get("voice", "whisper_model", "base")

    def _load_model(self):
        """Lazy-load Whisper on first use."""
        if self._model is None:
            logger.info(f"Loading Whisper model '{self.model_size}'... (first run downloads it)")
            try:
                from faster_whisper import WhisperModel
                # Use int8 quantisation for faster CPU inference
                self._model = WhisperModel(
                    self.model_size,
                    device="cpu",
                    compute_type="int8",
                )
            except ImportError:
                # Fallback to original whisper
                import whisper
                self._model = whisper.load_model(self.model_size)
                self._use_original = True
                logger.warning("faster-whisper not found, using original whisper (slower).")
            else:
                self._use_original = False
            logger.info("Whisper ready.")

    def transcribe(self, audio: np.ndarray) -> str:
        """
        Convert audio numpy array → text string.
        Returns empty string if audio is too short or empty.
        """
        if len(audio) < 1000:
            return ""

        self._load_model()

        try:
            if self._use_original:
                result = self._model.transcribe(audio, language="en", fp16=False)
                text = result["text"].strip()
            else:
                segments, _ = self._model.transcribe(
                    audio,
                    language="en",
                    beam_size=5,
                    vad_filter=True,   # built-in VAD as extra filter
                )
                text = " ".join(seg.text for seg in segments).strip()

            logger.info(f"Transcribed: '{text}'")
            return text

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return ""
