import asyncio
import websockets
import json
import base64
import sys
import os
import time
import subprocess
import tempfile

APP_DIR = "/run/media/2kfi/DATA/Work-files/Projects/najim-backend"
sys.path.insert(0, APP_DIR)
os.chdir(APP_DIR)

from core.config import get_settings
from core.jwt_auth import JWTManager


async def send_audio(file_path: str):
    s = get_settings()
    jwt = JWTManager()
    token = jwt.create_token("test-user", "test-device")

    receive_timeout = 180

    async with websockets.connect(
        f"ws://localhost:8080/api/v1/connect?token={token}",
        ping_interval=None,
    ) as ws:
        await ws.send(json.dumps({"type": "connect"}))

        with open(file_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()

        await ws.send(
            json.dumps(
                {
                    "type": "audio",
                    "audio_data": b64,
                    "mime_type": "audio/wav",
                    "task": "transcribe",
                    "chunk_index": 0,
                    "total_chunks": 1,
                }
            )
        )
        print(f"Sent audio, waiting for response (timeout: {receive_timeout}s)...")

        last_heartbeat = time.time()
        received_response = False
        response_text = ""
        audio_b64 = ""

        try:
            while True:
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=receive_timeout)
                    data = json.loads(msg)
                    msg_type = data.get("type")

                    if msg_type == "heartbeat":
                        last_heartbeat = time.time()
                        elapsed = int(time.time() - last_heartbeat)
                        print(f"[{elapsed}s] Heartbeat")
                        await ws.send(json.dumps({
                            "type": "heartbeat",
                            "timestamp": data.get("timestamp")
                        }))

                    elif msg_type == "audio_chunk":
                        print("=== RESPONSE ===")
                        response_text = data.get("text", "")
                        audio_b64 = data.get("audio_data", "")

                        if response_text:
                            print(f"Text ({len(response_text)} chars): {response_text[:200]}...")
                        else:
                            print("Text: (empty)")

                        if audio_b64:
                            print(f"Audio: {len(audio_b64)} bytes")
                            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                                f.write(base64.b64decode(audio_b64))
                                tmp_path = f.name

                            try:
                                subprocess.run(["paplay", tmp_path], check=True)
                                print("Played audio via PulseAudio")
                            except subprocess.CalledProcessError:
                                try:
                                    subprocess.run(["aplay", tmp_path], check=True)
                                    print("Played audio via ALSA")
                                except subprocess.CalledProcessError:
                                    print("Failed to play audio (no audio server?)")
                            finally:
                                os.unlink(tmp_path)
                        else:
                            print("Audio: (empty)")

                        print("===============")
                        received_response = True
                        break

                    elif msg_type == "accepted":
                        print("Processing accepted")

                    elif msg_type == "error":
                        print(f"Error: {data.get('message')}")
                        break

                    elif msg_type == "connected":
                        print(f"Connected: {data.get('device_id')} on node {data.get('node_id')}")

                    else:
                        print(f"Received: {msg_type}")

                except asyncio.TimeoutError:
                    print(f"No message received for {receive_timeout}s, closing...")
                    await ws.send(json.dumps({"type": "disconnect"}))
                    break

        except websockets.ConnectionClosed as e:
            print(f"Connection closed: {e.code} - {e.reason}")

        if not received_response:
            print("No audio_chunk received - pipeline may have failed")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test.py <audio_file.wav>")
        sys.exit(1)
    asyncio.run(send_audio(sys.argv[1]))