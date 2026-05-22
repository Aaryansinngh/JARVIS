"""
voice/listener.py — Stable microphone recorder for Jarvis
"""

import numpy as np
import sounddevice as sd
import soundfile as sf

from utils.logger import logger


class VoiceListener:

    def __init__(self):

        # Stable working microphone device
        self.device = 16

        # Stable working sample rate
        self.sample_rate = 44100

    def record_until_silence(self) -> np.ndarray:

        duration = 5

        logger.info(
            f"Recording for {duration} seconds..."
        )

        audio = sd.rec(
            int(duration * self.sample_rate),
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            device=self.device,
        )

        sd.wait()

        logger.info("Recording complete.")

        # BIG gain boost
        audio = audio * 25.0

        # Prevent clipping
        audio = np.clip(audio, -1.0, 1.0)

        # Save debug recording
        sf.write(
            "debug.wav",
            audio,
            self.sample_rate
        )

        logger.info(
            "Saved recording to debug.wav"
        )

        return audio.flatten()

    def listen_once(self) -> np.ndarray:

        return self.record_until_silence()