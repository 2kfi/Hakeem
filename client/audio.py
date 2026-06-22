import base64
import logging
import math
import struct
import time
import wave
from io import BytesIO
from typing import Callable, Optional

import numpy as np

logger = logging.getLogger("hakeem-cli")


class MicrophoneStream:
    def __init__(
        self,
        sample_rate: int = 16000,
        chunk_size: int = 1280,
        channels: int = 1,
        format_width: int = 2,
        input_device: Optional[int] = None,
    ):
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.channels = channels
        self.format_width = format_width
        self.input_device = input_device
        self._pyaudio_module = None
        self._pyaudio_instance = None
        self.stream = None
        self._open()

    def _open(self):
        import pyaudio
        self._pyaudio_module = pyaudio
        self._pyaudio_instance = pyaudio.PyAudio()
        kwargs = dict(
            format=pyaudio.paInt16,
            channels=self.channels,
            rate=self.sample_rate,
            input=True,
            frames_per_buffer=self.chunk_size,
        )
        if self.input_device is not None:
            kwargs["input_device_index"] = self.input_device
        self.stream = self._pyaudio_instance.open(**kwargs)

    def read(self) -> np.ndarray:
        raw = self.stream.read(self.chunk_size, exception_on_overflow=False)
        if len(raw) < self.chunk_size * self.format_width:
            logger.warning("Mic read underflow: expected %d bytes, got %d",
                           self.chunk_size * self.format_width, len(raw))
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
            self.stream = None
        if self._pyaudio_instance:
            try:
                self._pyaudio_instance.terminate()
            except Exception:
                pass
            self._pyaudio_instance = None


class AudioPlayer:
    def __init__(self, sample_rate: int = 22050):
        if sample_rate <= 0:
            raise ValueError(f"sample_rate must be positive, got {sample_rate}")
        self.sample_rate = sample_rate
        self.p = None
        self.stream = None

    def _ensure(self, rate: int = None):
        target_rate = rate or self.sample_rate
        if self.stream is None or target_rate != self.sample_rate:
            self.close()
            self.sample_rate = target_rate
            import pyaudio
            self.p = pyaudio.PyAudio()
            self.stream = self.p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                output=True,
            )

    def play_wav_bytes(self, wav_data: bytes):
        try:
            with wave.open(BytesIO(wav_data), "rb") as wf:
                wav_rate = wf.getframerate()
                data = wf.readframes(wf.getnframes())
                self._ensure(rate=wav_rate)
                self.stream.write(data)
        except wave.Error:
            logger.warning("Invalid WAV data, skipping playback")

    def play_raw_pcm(self, pcm_data: bytes):
        self._ensure()
        self.stream.write(pcm_data)

    def play_beep(self, frequency: float = 880, duration: float = 0.15, volume: float = 0.3, sample_rate: int = 22050):
        self._ensure(rate=sample_rate)
        n = int(sample_rate * duration)
        if n == 0:
            return
        samples = bytearray(n * 2)
        for i in range(n):
            val = int(volume * 32767 * math.sin(2 * math.pi * frequency * i / sample_rate))
            samples[i * 2:i * 2 + 2] = struct.pack('<h', val)
        self.stream.write(bytes(samples))

    def close(self):
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception:
                pass
            self.stream = None
        if self.p:
            try:
                self.p.terminate()
            except Exception:
                pass
            self.p = None


def record_until_silence(
    mic: MicrophoneStream,
    wakeword_detector=None,
    silence_threshold: float = 0.01,
    min_chunks: int = 20,
    max_seconds: int = 10,
    pre_timeout: float = 60.0,
    on_wakeword: Optional[Callable[[], None]] = None,
    on_silence: Optional[Callable[[], None]] = None,
) -> bytes:
    chunks = []
    silent_chunks = 0
    required_silent = int(1.5 * mic.sample_rate / mic.chunk_size)
    grace_chunks = int(1.0 * mic.sample_rate / mic.chunk_size)
    grace_remaining = 0
    max_chunks = int(max_seconds * mic.sample_rate / mic.chunk_size)
    started = False
    start_time = 0.0
    pre_start = time.time()

    while len(chunks) < max_chunks:
        audio = mic.read()

        if not started:
            if time.time() - pre_start > pre_timeout:
                logger.debug("Wake word timeout (%.0fs), stopping", pre_timeout)
                return b""

            should_start = False
            if wakeword_detector:
                scores = wakeword_detector.predict(audio)
                detected, _ = wakeword_detector.any_detected(scores)
                if detected:
                    should_start = True
            else:
                energy = np.abs(audio).mean() / 32767.0
                if energy > silence_threshold:
                    should_start = True

            if not should_start:
                continue

            started = True
            start_time = time.time()
            grace_remaining = grace_chunks
            if on_wakeword:
                on_wakeword()

        energy = np.abs(audio).mean() / 32767.0

        if energy > silence_threshold:
            silent_chunks = 0
        elif grace_remaining > 0:
            grace_remaining -= 1
        else:
            silent_chunks += 1

        chunks.append(audio.tobytes())

        if silent_chunks >= required_silent and len(chunks) >= min_chunks:
            if on_silence:
                on_silence()
            logger.debug("Silence detected, stopping recording")
            break

    elapsed = time.time() - start_time if start_time else 0.0
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
