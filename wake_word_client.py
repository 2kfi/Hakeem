#!/usr/bin/env python3
"""
Wake Word Client - ALPHA V.17
Hakeem Voice Assistant Client

Listens for wake word "Hakeem", records speech until silence,
sends to pipeline API, plays TTS response via pyaudio.
"""

import os
import sys
import io
import wave
import json
import time
import logging
import threading
import argparse
import signal

import pyaudio
import numpy as np
import requests
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from openwakeword.model import Model
    OWW_AVAILABLE = True
except ImportError:
    OWW_AVAILABLE = False
    print("[WARNING] openwakeword not available, using placeholder")

try:
    import webrtcvad
    VAD_AVAILABLE = True
except ImportError:
    VAD_AVAILABLE = False
    print("[WARNING] webrtcvad not available, using energy-based detection")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("WakeWordClient")


class AudioConfig:
    SAMPLE_RATE = 16000
    CHUNK_SIZE = 1280
    CHANNELS = 1
    FORMAT = pyaudio.paInt16
    SILENCE_THRESHOLD_MS = 1500
    MIN_AUDIO_LENGTH_MS = 300
    MAX_AUDIO_LENGTH_MS = 30000


class WakeWordClient:
    def __init__(self, api_url="http://localhost:8003/process-audio",
                 model_path="models/Hakeem/Hakeem.onnx",
                 oww_threshold=0.5,
                 inference_framework="onnx",
                 silence_threshold_ms=1500,
                 debug=False):
        
        self.api_url = api_url
        self.model_path = model_path
        self.oww_threshold = oww_threshold
        self.silence_threshold_ms = silence_threshold_ms
        self.debug = debug
        self.running = True
        
        self.oww_model = None
        self.vad = None
        self.audio = None
        self.stream = None
        
        self._init_models()
        
    def _init_models(self):
        if OWW_AVAILABLE and os.path.exists(self.model_path):
            logger.info(f"Loading OWW model: {self.model_path}")
            try:
                self.oww_model = Model(
                    wakeword_models=[self.model_path],
                    inference_framework=inference_framework
                )
                logger.info(f"OWW model loaded. Available models: {list(self.oww_model.models.keys())}")
            except Exception as e:
                logger.error(f"Failed to load OWW model: {e}")
                self.oww_model = None
        else:
            logger.warning(f"OWW model not found at {self.model_path}")
            
        if VAD_AVAILABLE:
            logger.info("Initializing WebRTC VAD")
            self.vad = webrtcvad.Vad(2)
            self.vad.set_mode(2)
        else:
            logger.info("Using energy-based silence detection")
            
    def _create_audio_stream(self):
        self.audio = pyaudio.PyAudio()
        self.stream = self.audio.open(
            format=AudioConfig.FORMAT,
            channels=AudioConfig.CHANNELS,
            rate=AudioConfig.SAMPLE_RATE,
            input=True,
            frames_per_buffer=AudioConfig.CHUNK_SIZE
        )
        logger.info("Microphone stream started")
        
    def _close_audio_stream(self):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        if self.audio:
            self.audio.terminate()
        logger.info("Microphone stream closed")
        
    def _detect_wakeword(self, audio_chunk):
        if self.oww_model is None:
            return False
            
        prediction = self.oww_model.predict(audio_chunk)
        
        for model_name, scores in prediction.items():
            current_score = scores[-1] if scores else 0
            if current_score > self.oww_threshold:
                logger.info(f"Wakeword detected! {model_name} score: {current_score:.3f}")
                return True
        return False
    
    def _is_silence(self, audio_chunk):
        if VAD_AVAILABLE and self.vad:
            try:
                audio_bytes = (audio_chunk.astype(np.int16)).tobytes()
                return not self.vad.is_speech(audio_bytes, AudioConfig.SAMPLE_RATE)
            except:
                pass
        
        energy = np.abs(audio_chunk).mean()
        return energy < 500
    
    def _record_until_silence(self):
        logger.info("Recording speech...")
        audio_buffer = []
        silence_chunks = 0
        min_chunks = int(AudioConfig.MIN_AUDIO_LENGTH_MS / (AudioConfig.CHUNK_SIZE * 1000 / AudioConfig.SAMPLE_RATE))
        max_chunks = int(AudioConfig.MAX_AUDIO_LENGTH_MS / (AudioConfig.CHUNK_SIZE * 1000 / AudioConfig.SAMPLE_RATE))
        silence_limit = int(self.silence_threshold_ms / (AudioConfig.CHUNK_SIZE * 1000 / AudioConfig.SAMPLE_RATE))
        
        chunk_count = 0
        start_time = time.time()
        
        while chunk_count < max_chunks:
            try:
                data = self.stream.read(AudioConfig.CHUNK_SIZE, exception_on_overflow=False)
                audio_chunk = np.frombuffer(data, dtype=np.int16)
            except Exception as e:
                logger.error(f"Error reading audio: {e}")
                break
                
            audio_buffer.append(audio_chunk)
            chunk_count += 1
            
            if chunk_count >= min_chunks:
                if self._is_silence(audio_chunk):
                    silence_chunks += 1
                    if silence_chunks >= silence_limit:
                        logger.info("Silence detected, stopping recording")
                        break
                else:
                    silence_chunks = 0
                    
        elapsed = time.time() - start_time
        logger.info(f"Recording complete: {len(audio_buffer)} chunks, {elapsed:.2f}s")
        
        if self.debug and audio_buffer:
            debug_path = f"debug_recording_{int(time.time())}.wav"
            self._save_debug_audio(np.concatenate(audio_buffer), debug_path)
            
        return np.concatenate(audio_buffer) if audio_buffer else np.array([], dtype=np.int16)
    
    def _save_debug_audio(self, audio_data, filename):
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(AudioConfig.CHANNELS)
            wf.setsampwidth(2)
            wf.setframerate(AudioConfig.SAMPLE_RATE)
            wf.writeframes(audio_data.tobytes())
        logger.info(f"Debug audio saved to {filename}")
        
    def _send_to_api(self, audio_data):
        if len(audio_data) < 100:
            logger.warning("Audio too short, skipping API call")
            return None
            
        wav_io = io.BytesIO()
        with wave.open(wav_io, 'wb') as wf:
            wf.setnchannels(AudioConfig.CHANNELS)
            wf.setsampwidth(2)
            wf.setframerate(AudioConfig.SAMPLE_RATE)
            wf.writeframes(audio_data.tobytes())
        
        wav_io.seek(0)
        
        try:
            logger.info(f"Sending audio to API: {self.api_url}")
            response = requests.post(
                self.api_url,
                files={'file': ('audio.wav', wav_io, 'audio/wav')},
                timeout=60
            )
            logger.info(f"API response status: {response.status_code}")
            return response
        except requests.exceptions.Timeout:
            logger.error("API request timed out")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            return None
            
    def _play_audio(self, wav_data):
        try:
            wf = wave.open(io.BytesIO(wav_data), 'rb')
        except Exception as e:
            logger.error(f"Failed to open audio data: {e}")
            return
            
        play_audio = pyaudio.PyAudio()
        play_stream = play_audio.open(
            format=play_audio.get_format_from_width(wf.getsampwidth()),
            channels=wf.getnchannels(),
            rate=wf.getframerate(),
            output=True
        )
        
        logger.info("Playing TTS response...")
        
        chunk_size = 1024
        data = wf.readframes(chunk_size)
        while data:
            play_stream.write(data)
            data = wf.readframes(chunk_size)
            
        play_stream.stop_stream()
        play_stream.close()
        play_audio.terminate()
        logger.info("TTS playback complete")
        
    def run(self):
        self._create_audio_stream()
        
        logger.info("=" * 50)
        logger.info("Hakeem Wake Word Client Started")
        logger.info(f"API: {self.api_url}")
        logger.info(f"OWW Model: {self.model_path}")
        logger.info(f"Threshold: {self.oww_threshold}")
        logger.info("=" * 50)
        
        while self.running:
            try:
                data = self.stream.read(AudioConfig.CHUNK_SIZE, exception_on_overflow=False)
                audio_chunk = np.frombuffer(data, dtype=np.int16)
                
                if self._detect_wakeword(audio_chunk):
                    audio_data = self._record_until_silence()
                    
                    if len(audio_data) > 0:
                        response = self._send_to_api(audio_data)
                        
                        if response and response.status_code == 200:
                            self._play_audio(response.content)
                        elif response:
                            logger.error(f"API returned {response.status_code}: {response.text}")
                        else:
                            logger.error("No response from API")
                            
                    logger.info("Returning to listening mode...")
                    
            except KeyboardInterrupt:
                logger.info("Interrupted by user")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(0.1)
                
        self._close_audio_stream()
        
    def stop(self):
        self.running = False


def signal_handler(sig, frame):
    print("\nShutting down...")
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="Hakeem Wake Word Client")
    parser.add_argument('--api-url', type=str, 
                        default=os.environ.get('API_URL', 'http://localhost:8003/process-audio'),
                        help='Pipeline API URL')
    parser.add_argument('--model-path', type=str,
                        default=os.environ.get('OWW_MODEL_PATH', 'models/Hakeem/Hakeem.onnx'),
                        help='Path to OWW model')
    parser.add_argument('--threshold', type=float, default=0.5,
                        help='Wake word detection threshold (0-1)')
    parser.add_argument('--framework', type=str, default='onnx', choices=['onnx', 'tflite'],
                        help='OWW inference framework')
    parser.add_argument('--silence-ms', type=int, default=1500,
                        help='Silence threshold in milliseconds')
    parser.add_argument('--debug', action='store_true',
                        help='Save recorded audio for debugging')
    
    args = parser.parse_args()
    
    signal.signal(signal.SIGINT, signal_handler)
    
    client = WakeWordClient(
        api_url=args.api_url,
        model_path=args.model_path,
        oww_threshold=args.threshold,
        inference_framework=args.framework,
        silence_threshold_ms=args.silence_ms,
        debug=args.debug
    )
    
    client.run()


if __name__ == "__main__":
    main()