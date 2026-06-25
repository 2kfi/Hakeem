import asyncio
import base64
import json
import logging
import time
from typing import Optional
from urllib.parse import urlencode, urlunsplit, urlsplit, SplitResult

import websockets

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
        self.response_queue: asyncio.Queue = asyncio.Queue()
        self._listener_task: Optional[asyncio.Task] = None

    def _build_uri(self) -> str:
        parts = urlsplit(self.url)
        query = parts.query
        if self.token:
            token_param = urlencode({"token": self.token})
            query = f"{query}&{token_param}" if query else token_param
        return urlunsplit(SplitResult(
            scheme=parts.scheme,
            netloc=parts.netloc,
            path=parts.path,
            query=query,
            fragment="",
        ))

    async def __close_ws(self):
        if self.ws is not None:
            try:
                await self.ws.close()
            except Exception:
                pass

    async def connect(self) -> bool:
        try:
            import websockets
        except ImportError:
            print("ERROR: websockets not installed.")
            print("  pip install -r client/requirements-onnx.txt")
            return False

        try:
            await self.__close_ws()
            uri = self._build_uri()
            self.ws = await asyncio.wait_for(
                websockets.connect(uri, ping_interval=None), timeout=15
            )
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
            if not self.token:
                logger.error("No token available. Run server with --no-auth or set api_key in client config")
            else:
                logger.error("Failed to connect: %s", e)
            return False

    async def send_audio(self, audio_b64: str, language: str = ""):
        if not self.ws:
            return
        msg = json.dumps({
            "type": "audio",
            "audio_data": audio_b64,
            "language": language,
        })
        await self.ws.send(msg)

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
        except websockets.ConnectionClosed as e:
            logger.warning("WebSocket connection closed: %s", e)
            self.connected = False
            raise

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

            elif msg_type == "disconnect":
                logger.info("Server disconnected")
                break

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
                await self.ws.send(json.dumps({"type": "heartbeat_ack", "timestamp": ts}))
            except Exception:
                pass

    async def send_tool_response(self, correlation_id: str, result: dict):
        if not self.ws:
            return
        try:
            msg = json.dumps({
                "type": "tool_response",
                "correlation_id": correlation_id,
                "result": result,
            })
            await self.ws.send(msg)
        except Exception:
            pass

    def start_listening(self, audio_player=None):
        if self._listener_task is None:
            self._listener_task = asyncio.create_task(self._listen_loop(audio_player))

    async def stop_listening(self):
        if self._listener_task is not None:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
            self._listener_task = None

    async def _drain_response_queue(self):
        while not self.response_queue.empty():
            try:
                self.response_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

    async def wait_for_response(self, timeout: float = 120.0) -> tuple[Optional[str], Optional[str]]:
        await self._drain_response_queue()
        try:
            text, audio_b64 = await asyncio.wait_for(
                self.response_queue.get(), timeout=timeout
            )
            return text, audio_b64
        except asyncio.TimeoutError:
            return None, None

    async def _reconnect(self) -> bool:
        self.connected = False
        for attempt in range(5):
            await asyncio.sleep(min(2 ** attempt, 30))
            logger.info(f"Reconnection attempt {attempt + 1}/5...")
            if await self.connect():
                logger.info("Reconnected to backend")
                return True
        logger.error("Failed to reconnect after 5 attempts")
        return False

    async def _listen_loop(self, audio_player=None):
        """Background task: listen for messages from the server indefinitely."""
        try:
            while True:
                try:
                    msg = await self.listen(timeout=self.heartbeat_interval + 5)
                except Exception:
                    logger.error("Listener: connection lost, attempting reconnect...")
                    if await self._reconnect():
                        continue
                    break

                if msg is None:
                    await self.send_heartbeat()
                    continue

                try:
                    msg_type = msg.get("type", "")

                    if msg_type == "heartbeat":
                        await self.send_heartbeat_ack(msg.get("timestamp"))

                    elif msg_type == "accepted":
                        logger.debug("Audio accepted by backend")

                    elif msg_type == "processing":
                        logger.info("Backend thinking: %s", msg.get("text", ""))

                    elif msg_type == "response":
                        text = msg.get("text", "")
                        audio_b64 = msg.get("audio_data", "")
                        logger.info("Response: %s", text)
                        await self.response_queue.put((text, audio_b64))
                        if audio_player and audio_b64:
                            try:
                                wav_bytes = base64.b64decode(audio_b64)
                                audio_player.play_wav_bytes(wav_bytes)
                            except Exception as e:
                                logger.warning("Audio playback failed: %s", e)

                    elif msg_type == "audio_chunk":
                        text = msg.get("text", "")
                        audio_b64 = msg.get("audio_data", "")
                        if msg.get("text_only"):
                            logger.info("Response (text): %s", text)
                        else:
                            logger.info("Response: %s", text)
                        await self.response_queue.put((text, audio_b64))
                        if audio_player and audio_b64:
                            try:
                                wav_bytes = base64.b64decode(audio_b64)
                                audio_player.play_wav_bytes(wav_bytes)
                            except Exception as e:
                                logger.warning("Audio playback failed: %s", e)

                    elif msg_type == "tool_request":
                        logger.info("Tool request: %s %s", msg.get("tool"), msg.get("params"))
                        await self.send_tool_response(msg.get("correlation_id"), {"status": "not_implemented"})

                    elif msg_type == "error":
                        logger.error("Backend error: %s", msg.get("message", ""))

                    elif msg_type == "heartbeat_ack":
                        pass

                    elif msg_type == "disconnect":
                        logger.info("Server disconnected, attempting reconnect...")
                        if await self._reconnect():
                            continue
                        break

                    else:
                        logger.debug("Unknown message type: %s", msg_type)

                except Exception as e:
                    logger.error("Listener: message handler error: %s", e, exc_info=True)

        finally:
            self._listener_task = None

    async def close(self):
        await self.stop_listening()
        self.connected = False
        if self.ws:
            try:
                await self.ws.close()
            except Exception:
                pass
            self.ws = None
