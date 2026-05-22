"""
voice/speaker.py — Text-to-Speech output

Two backends:
  1. pyttsx3   — 100% offline, uses Windows built-in voices (default)
  2. ElevenLabs — Cloud-based, extremely natural voice (optional)
"""
import threading
from utils.logger import logger
from utils.config import get


class Speaker:
    """Speaks text aloud. Non-blocking by default."""

    def __init__(self):
        self._engine = None
        self._lock = threading.Lock()
        self.speed = get("assistant", "voice_speed", 175)

    def _load(self):
        if self._engine is None:
            import pyttsx3
            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", self.speed)
            self._engine.setProperty("volume", 0.9)

            # Prefer a natural-sounding voice
            voices = self._engine.getProperty("voices")
            for v in voices:
                if "zira" in v.name.lower() or "david" in v.name.lower():
                    self._engine.setProperty("voice", v.id)
                    break

    def speak(self, text: str, blocking: bool = False):
        """Speak text. Non-blocking by default (runs in background thread)."""
        logger.info(f"Speaking: '{text[:60]}...' " if len(text) > 60 else f"Speaking: '{text}'")

        if blocking:
            self._speak_sync(text)
        else:
            t = threading.Thread(target=self._speak_sync, args=(text,), daemon=True)
            t.start()

    def _speak_sync(self, text: str):
        with self._lock:
            self._load()
            self._engine.say(text)
            self._engine.runAndWait()

    def stop(self):
        """Interrupt speech immediately."""
        if self._engine:
            self._engine.stop()


class ElevenLabsSpeaker:
    """
    Premium cloud TTS using ElevenLabs.
    Requires: pip install elevenlabs
    Get API key: https://elevenlabs.io
    """

    def __init__(self, api_key: str, voice_id: str = "21m00Tcm4TlvDq8ikWAM"):
        self.api_key = api_key
        self.voice_id = voice_id  # Default: "Rachel" voice

    def speak(self, text: str, blocking: bool = False):
        def _play():
            try:
                from elevenlabs import generate, play, set_api_key
                set_api_key(self.api_key)
                audio = generate(text=text, voice=self.voice_id, model="eleven_monolingual_v1")
                play(audio)
            except Exception as e:
                logger.error(f"ElevenLabs TTS failed: {e}")

        if blocking:
            _play()
        else:
            threading.Thread(target=_play, daemon=True).start()
