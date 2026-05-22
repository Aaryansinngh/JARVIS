"""
voice/wake_word.py — Wake word detection using Porcupine

Runs a tiny on-device model listening for "Jarvis" (or any keyword).
Uses almost zero CPU. Only wakes up when it hears the trigger word.

Free tier allows: "jarvis", "hey siri", "alexa", "computer", etc.
Get a free API key from: https://console.picovoice.ai/
"""
import threading
import struct
import numpy as np
from utils.logger import logger
from utils.config import get


class WakeWordDetector:
    """
    Runs in a background thread.
    Calls on_detected() callback when wake word is heard.
    """

    def __init__(self, on_detected: callable, access_key: str = ""):
        self.on_detected = on_detected
        self.access_key = access_key
        self._running = False
        self._thread = None
        self._porcupine = None

    def _load(self):
        """Load the Porcupine engine."""
        try:
            import pvporcupine
            self._porcupine = pvporcupine.create(
                access_key=self.access_key,
                keywords=["jarvis"],   # Built-in keyword
            )
            logger.info(f"Wake word detection ready. Say '{get('assistant','wake_word','jarvis')}' to activate.")
        except Exception as e:
            logger.error(f"Porcupine failed to load: {e}")
            logger.warning("Wake word detection disabled. Falling back to ENTER key.")
            self._porcupine = None

    def _loop(self):
        """Background thread: continuously read mic, check for wake word."""
        import sounddevice as sd

        frame_length = self._porcupine.frame_length if self._porcupine else 512
        sample_rate = 16000

        with sd.RawInputStream(
            samplerate=sample_rate,
            channels=1,
            dtype="int16",
            blocksize=frame_length,
        ) as stream:
            while self._running:
                data, _ = stream.read(frame_length)
                pcm = struct.unpack_from(f"{frame_length}h", bytes(data))

                if self._porcupine:
                    result = self._porcupine.process(pcm)
                    if result >= 0:
                        logger.info("🎙️  Wake word detected!")
                        self.on_detected()

    def start(self):
        """Start listening in a background thread."""
        self._load()
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the background listener."""
        self._running = False
        if self._porcupine:
            self._porcupine.delete()
        logger.info("Wake word detector stopped.")


class KeyboardTrigger:
    """
    Fallback when Porcupine isn't available.
    Press CTRL+SPACE to activate Jarvis.
    """

    def __init__(self, on_detected: callable):
        self.on_detected = on_detected

    def start(self):
        import keyboard
        keyboard.add_hotkey("ctrl+space", self.on_detected)
        logger.info("Keyboard trigger active. Press CTRL+SPACE to activate Jarvis.")

    def stop(self):
        import keyboard
        keyboard.remove_all_hotkeys()
