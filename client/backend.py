import asyncio
import base64
import json
import logging
import time
from typing import Optional

logger = logging.getLogger("hakeem-cli")


class HakeemBackendClient:
    def __init__(
        self,
        url: str,
        token: str,
        device_id: str = "hakeem-cli",
        user_id: str = "cli-user",
        heartbeat_interval: int = 30,
    ):
        self.url = url
        self.token = token
        self.device_id = device_id
        self.user_id = user_id
        self.heartbeat_interval = heartbeat_interval
        self.ws = None
        self.connected = False

    async def connect(self) -> bool:
        try:
            import websockets
        except ImportError:
            print("ERROR: websockets not installed.")
            print("  pip install -r client/requirements-onnx.txt")
            return False

        try:
            uri = f"{self.url}?token={self.token}"
            self.ws = await websockets.connect(uri, ping_interval=None)
            connect_msg = json.dumps({
                "type": "connect",
                "capabilities": ["cli-client"],
                "tools": [],
            })
            await self.ws.send(connect_msg)
            resp = await asyncio.wait_for(self.ws.recv(), timeout=10)
            data = json.loads(resp)
            if data.get("type") == "connected":
                self.connected = True
                logger.info("Connected to backend: device_id=%s node_id=%s",
                            data.get("device_id"), data.get("node_id"))
                return True
            else:
                logger.error("Unexpected connect response: %s", resp)
                return False
        except Exception as e:
            logger.error("Failed to connect: %s", e)
            return False

    async def send_audio(self, audio_b64: str, language: str = "") -> Optional[dict]:
        if not self.ws:
            return None
        msg = json.dumps({
            "type": "audio",
            "audio_data": audio_b64,
            "language": language,
        })
        await self.ws.send(msg)
        return None

    async def send_text(self, text: str, language: str = "", skip_tts: bool = False):
        if not self.ws:
            return
        msg = json.dumps({
            "type": "text",
            "text": text,
            "language": language,
            "skip_tts": skip_tts,
        })
        await self.ws.send(msg)

    async def listen(self, timeout: float = 30.0) -> Optional[dict]:
        if not self.ws:
            return None
        try:
            raw = await asyncio.wait_for(self.ws.recv(), timeout=timeout)
            return json.loads(raw)
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            logger.error("Listen error: %s", e)
            return None

    async def handle_messages(self, audio_player=None) -> tuple[Optional[str], Optional[str]]:
        last_text = None
        last_audio_b64 = None

        while True:
            msg = await self.listen(timeout=self.heartbeat_interval + 5)
            if msg is None:
                logger.debug("No message, sending heartbeat")
                await self.send_heartbeat()
                continue

            msg_type = msg.get("type", "")

            if msg_type == "heartbeat":
                await self.send_heartbeat_ack(msg.get("timestamp"))

            elif msg_type == "accepted":
                logger.debug("Audio accepted by backend")

            elif msg_type == "processing":
                logger.info("Backend thinking: %s", msg.get("text", ""))

            elif msg_type == "response":
                last_audio_b64 = msg.get("audio_data", "")
                last_text = msg.get("text", "")
                logger.info("Response: %s", last_text)
                break

            elif msg_type == "audio_chunk":
                last_audio_b64 = msg.get("audio_data", "")
                last_text = msg.get("text", "")
                if msg.get("text_only"):
                    logger.info("Response (text): %s", last_text)
                else:
                    logger.info("Response: %s", last_text)
                if audio_player and last_audio_b64:
                    try:
                        wav_bytes = base64.b64decode(last_audio_b64)
                        audio_player.play_wav_bytes(wav_bytes)
                    except Exception as e:
                        logger.warning("Audio playback failed: %s", e)
                break

            elif msg_type == "tool_request":
                logger.info("Tool request: %s %s",
                            msg.get("tool"), msg.get("params"))
                await self.send_tool_response(msg.get("correlation_id"), {"status": "not_implemented"})

            elif msg_type == "error":
                logger.error("Backend error: %s", msg.get("message", ""))

            elif msg_type == "heartbeat_ack":
                pass

            else:
                logger.debug("Unknown message type: %s", msg_type)

        return last_text, last_audio_b64

    async def send_heartbeat(self):
        if self.ws:
            try:
                await self.ws.send(json.dumps({"type": "heartbeat", "timestamp": time.time()}))
            except Exception:
                pass

    async def send_heartbeat_ack(self, ts: float):
        if self.ws:
            try:
                await self.ws.send(json.dumps({"type": "heartbeat", "timestamp": ts}))
            except Exception:
                pass

    async def send_tool_response(self, correlation_id: str, result: dict):
        if self.ws:
            msg = json.dumps({
                "type": "tool_response",
                "correlation_id": correlation_id,
                "result": result,
            })
            await self.ws.send(msg)

    async def close(self):
        self.connected = False
        if self.ws:
            try:
                await self.ws.close()
            except Exception:
                pass
            self.ws = None
