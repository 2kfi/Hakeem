import base64
import logging
import queue
import struct
import sys
import threading
import time
import wave
from io import BytesIO
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger("hakeem-cli")


class MicrophoneStream:
    def __init__(
        self,
        sample_rate: int = 16000,
        chunk_size: int = 1280,
        channels: int = 1,
        format_width: int = 2,
    ):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.channels = channels
        self.format_width = format_width
        self.format = None
        self.pyaudio = None
        self.stream = None
        self._open()

    def _get_format(self):
        if self.pyaudio is None:
            import pyaudio
            self.pyaudio = pyaudio
        return self.pyaudio.paInt16

    def _open(self):
        import pyaudio
        self.pyaudio = pyaudio
        self.format = pyaudio.paInt16
        self.stream = pyaudio.PyAudio().open(
            format=self.format,
            channels=self.channels,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size,
        )

    def read(self) -> np.ndarray:
        raw = self.stream.read(self.chunk_size, exception_on_overflow=False)
        return np.frombuffer(raw, dtype=np.int16)

    def read_bytes(self, num_chunks: int) -> bytes:
        frames = []
        for _ in range(num_chunks):
            raw = self.stream.read(self.chunk_size, exception_on_overflow=False)
            frames.append(raw)
        return b"".join(frames)

    def close(self):
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception:
                pass
        if self.pyaudio:
            try:
                self.pyaudio.PyAudio().terminate()
            except Exception:
                pass


class AudioPlayer:
    def __init__(self, sample_rate: int = 22050):
        self.sample_rate = sample_rate
        self.p = None
        self.stream = None

    def _ensure(self):
        if self.stream is None:
            import pyaudio
            self.p = pyaudio.PyAudio()
            self.stream = self.p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                output=True,
            )

    def play_wav_bytes(self, wav_data: bytes):
        self._ensure()
        try:
            with wave.open(BytesIO(wav_data), "rb") as wf:
                data = wf.readframes(wf.getnframes())
                self.stream.write(data)
        except Exception:
            self.stream.write(wav_data)

    def play_raw_pcm(self, pcm_data: bytes, rate: int = 22050):
        self._ensure()
        self.stream.write(pcm_data)

    def close(self):
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception:
                pass
        if self.p:
            try:
                self.p.terminate()
            except Exception:
                pass


def record_until_silence(
    mic: MicrophoneStream,
    wakeword_detector=None,
    silence_threshold: float = 0.01,
    min_chunks: int = 20,
    max_seconds: int = 10,
) -> bytes:
    chunks = []
    silent_chunks = 0
    required_silent = int(0.8 * 16000 / mic.chunk_size)
    max_chunks = int(max_seconds * 16000 / mic.chunk_size)
    started = False
    start_time = time.time()

    while len(chunks) < max_chunks:
        audio = mic.read()
        energy = np.abs(audio).mean() / 32768.0

        if energy > silence_threshold:
            if not started:
                started = True
            silent_chunks = 0
        else:
            if started:
                silent_chunks += 1

        if started:
            chunks.append(audio.tobytes())

        elapsed = time.time() - start_time
        if started and silent_chunks >= required_silent and len(chunks) >= min_chunks:
            logger.debug("Silence detected, stopping recording")
            break

        if wakeword_detector and not started:
            scores = wakeword_detector.predict(audio)
            detected, _ = wakeword_detector.any_detected(scores)
            if detected:
                started = True

    elapsed = time.time() - start_time
    logger.debug("Recorded %.1fs (%d chunks)", elapsed, len(chunks))
    return b"".join(chunks)


def pcm_to_wav(pcm_data: bytes, sample_rate: int = 16000) -> bytes:
    buf = BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()


def wav_to_base64(wav_data: bytes) -> str:
    return base64.b64encode(wav_data).decode("ascii")
