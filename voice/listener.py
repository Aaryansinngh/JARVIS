"""
voice/listener.py — Microphone recorder using PyAudio
"""

import io
import wave
import numpy as np
from utils.logger import logger


class VoiceListener:

    def __init__(self):
        self.sample_rate = 16000
        self.channels    = 1
        self.chunk       = 1024
        self.duration    = 5
        self.format      = None  # set on first use

    def record_until_silence(self) -> np.ndarray:
        import pyaudio

        pa     = pyaudio.PyAudio()
        fmt    = pyaudio.paInt16

        logger.info(f"Recording for {self.duration} seconds...")

        stream = pa.open(
            format=fmt,
            channels=self.channels,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk,
        )

        frames = []
        total_chunks = int(self.sample_rate / self.chunk * self.duration)

        for _ in range(total_chunks):
            frames.append(stream.read(self.chunk, exception_on_overflow=False))

        stream.stop_stream()
        stream.close()
        pa.terminate()

        logger.info("Recording complete.")

        # Convert to float32 numpy array
        raw = b"".join(frames)
        audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

        # Save debug wav
        with wave.open("debug.wav", "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(raw)

        logger.info("Saved recording to debug.wav")
        return audio

    def listen_once(self) -> np.ndarray:
        return self.record_until_silence()