"""Volcengine Doubao Streaming ASR client.

Implemented based on official arkitect library:
https://github.com/volcengine/ai-app-lab/blob/main/arkitect/core/component/asr/asr_client.py

Protocol documentation:
- WebSocket endpoint: wss://openspeech.bytedance.com/api/v3/sauc/bigmodel
- Binary protocol with header + optional sequence + payload size + payload
"""

import asyncio
import gzip
import json
import logging
import uuid
from dataclasses import dataclass
from typing import Callable, Optional

import websockets
from websockets.client import WebSocketClientProtocol

logger = logging.getLogger(__name__)


# Protocol constants (from arkitect/utils/binary_protocol.py)
PROTOCOL_VERSION = 0b0001
DEFAULT_HEADER_SIZE = 0b0001

# Message Types
FULL_CLIENT_REQUEST = 0b0001
AUDIO_ONLY_REQUEST = 0b0010
FULL_SERVER_RESPONSE = 0b1001
SERVER_ACK = 0b1011
SERVER_ERROR_RESPONSE = 0b1111

# Message Type Specific Flags
NO_SEQUENCE = 0b0000
POS_SEQUENCE = 0b0001
NEG_SEQUENCE = 0b0010

# Serialization & Compression
JSON_SERIALIZATION = 0b0001
GZIP_COMPRESSION = 0b0001
NO_COMPRESSION = 0b0000


def generate_header(
    message_type: int = FULL_CLIENT_REQUEST,
    message_type_specific_flags: int = NO_SEQUENCE,
    serial_method: int = JSON_SERIALIZATION,
    compression_type: int = GZIP_COMPRESSION,
) -> bytearray:
    """Generate 4-byte protocol header."""
    header = bytearray()
    header_size = 1
    header.append((PROTOCOL_VERSION << 4) | header_size)
    header.append((message_type << 4) | message_type_specific_flags)
    header.append((serial_method << 4) | compression_type)
    header.append(0x00)  # reserved
    return header


def generate_sequence(sequence: int) -> bytearray:
    """Generate 4-byte sequence number."""
    return bytearray(sequence.to_bytes(4, "big", signed=True))


def parse_response(res: bytes) -> dict:
    """Parse server response."""
    header_size = res[0] & 0x0F
    message_type = res[1] >> 4
    message_type_specific_flags = res[1] & 0x0F
    serialization_method = res[2] >> 4
    message_compression = res[2] & 0x0F
    
    payload = res[header_size * 4:]
    result = {"is_last_package": False}
    payload_msg = None
    
    # Check for sequence
    if message_type_specific_flags & 0x01:
        seq = int.from_bytes(payload[:4], "big", signed=True)
        result["payload_sequence"] = seq
        payload = payload[4:]
    
    # Check for last package flag
    if message_type_specific_flags & 0x02:
        result["is_last_package"] = True
    
    if message_type == FULL_SERVER_RESPONSE:
        payload_size = int.from_bytes(payload[:4], "big", signed=True)
        payload_msg = payload[4:]
    elif message_type == SERVER_ACK:
        seq = int.from_bytes(payload[:4], "big", signed=True)
        result["seq"] = seq
        if len(payload) >= 8:
            payload_size = int.from_bytes(payload[4:8], "big", signed=False)
            payload_msg = payload[8:]
    elif message_type == SERVER_ERROR_RESPONSE:
        code = int.from_bytes(payload[:4], "big", signed=False)
        result["code"] = code
        payload_size = int.from_bytes(payload[4:8], "big", signed=False)
        payload_msg = payload[8:]
    
    if payload_msg is None:
        return result
    
    if message_compression == GZIP_COMPRESSION:
        payload_msg = gzip.decompress(payload_msg)
    
    if serialization_method == JSON_SERIALIZATION:
        payload_msg = json.loads(payload_msg.decode("utf-8"))
    
    result["payload_msg"] = payload_msg
    return result


@dataclass
class ASRResult:
    """ASR recognition result."""
    text: str
    is_final: bool
    utterance_id: str = ""


class VolcengineASR:
    """Volcengine Doubao Streaming ASR client."""
    
    def __init__(
        self,
        app_key: str,
        access_key: str,
        resource_id: str = "volc.seedasr.sauc.duration",
        ws_url: str = "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async",
    ):
        """Initialize ASR client.
        
        Args:
            app_key: Volcengine App ID.
            access_key: Volcengine Access Token.
            resource_id: ASR resource ID.
            ws_url: WebSocket endpoint URL.
        """
        self.app_key = app_key
        self.access_key = access_key
        self.resource_id = resource_id
        self.ws_url = ws_url
        
        self._ws: Optional[WebSocketClientProtocol] = None
        self._request_id: str = ""
        self._connected = False
        self._sequence = 0
        
        # Callbacks
        self._on_partial: Optional[Callable[[str], None]] = None
        self._on_final: Optional[Callable[[str], None]] = None
        self._on_error: Optional[Callable[[str], None]] = None
        
        # Collected results
        self._final_text = ""
        self._current_text = ""
        self._receive_task: Optional[asyncio.Task] = None
    
    async def connect(self) -> bool:
        """Establish WebSocket connection.
        
        Returns:
            True if connected successfully.
        """
        self._request_id = str(uuid.uuid4())
        
        headers = {
            "X-Api-Resource-Id": self.resource_id,
            "X-Api-Access-Key": self.access_key,
            "X-Api-App-Key": self.app_key,
            "X-Api-Request-Id": self._request_id,
        }
        
        logger.info(f"Connecting to {self.ws_url}")
        logger.debug(f"Headers: {headers}")
        
        try:
            self._ws = await websockets.connect(
                self.ws_url,
                additional_headers=headers,
            )
            self._connected = True
            self._sequence = 0
            self._final_text = ""
            self._current_text = ""
            
            logger.info("WebSocket connected")
            
            # Send initial configuration
            await self._send_config()
            
            # Start receiving responses
            self._receive_task = asyncio.create_task(self._receive_loop())
            
            return True
            
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            if self._on_error:
                self._on_error(str(e))
            return False
    
    async def _send_config(self) -> None:
        """Send initial ASR configuration."""
        config = {
            "user": {
                "uid": self._request_id,
            },
            "audio": {
                "format": "pcm",
                "rate": 16000,
                "bits": 16,
                "channel": 1,
                "language": "zh-CN",
            },
            "request": {
                "model_name": "bigmodel",
            }
        }
        
        # Serialize and compress
        payload_bytes = json.dumps(config).encode("utf-8")
        payload_bytes = gzip.compress(payload_bytes)
        
        # Build message
        message = bytearray(generate_header(
            message_type=FULL_CLIENT_REQUEST,
            message_type_specific_flags=POS_SEQUENCE,
        ))
        message.extend(generate_sequence(1))  # sequence = 1
        message.extend(len(payload_bytes).to_bytes(4, "big"))  # payload size
        message.extend(payload_bytes)  # payload
        
        await self._ws.send(message)
        
        # Wait for init response
        response = await self._ws.recv()
        parsed = parse_response(response)
        logger.info(f"Init response: {parsed}")
    
    async def _receive_loop(self) -> None:
        """Background task to receive and process responses."""
        try:
            async for message in self._ws:
                if isinstance(message, bytes):
                    result = parse_response(message)
                    logger.debug(f"Received: {result}")
                    
                    # Extract text from response
                    payload_msg = result.get("payload_msg", {})
                    if isinstance(payload_msg, dict):
                        asr_result = payload_msg.get("result", {})
                        text = asr_result.get("text", "")
                        
                        if text:
                            self._current_text = text
                            
                            if result.get("is_last_package"):
                                self._final_text = text
                                if self._on_final:
                                    self._on_final(text)
                            else:
                                if self._on_partial:
                                    self._on_partial(text)
                                    
        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket connection closed")
        except Exception as e:
            logger.error(f"Receive error: {e}")
            if self._on_error:
                self._on_error(str(e))
    
    async def send_audio(self, audio_data: bytes) -> None:
        """Send audio data to ASR.
        
        Args:
            audio_data: PCM audio data (16kHz, 16-bit, mono).
        """
        if not self._connected or self._ws is None:
            return
        
        # Compress audio
        payload_bytes = gzip.compress(audio_data)
        
        # Build message
        message = bytearray(generate_header(
            message_type=AUDIO_ONLY_REQUEST,
            message_type_specific_flags=NO_SEQUENCE,
            serial_method=0,  # No serialization for audio
            compression_type=GZIP_COMPRESSION,
        ))
        message.extend(len(payload_bytes).to_bytes(4, "big"))
        message.extend(payload_bytes)
        
        try:
            await self._ws.send(message)
        except Exception as e:
            logger.error(f"Send error: {e}")
    
    async def finish(self) -> str:
        """Signal end of audio and get final result.
        
        Returns:
            Final recognized text.
        """
        if not self._connected or self._ws is None:
            return self._current_text
        
        # Send empty audio with last flag
        payload_bytes = gzip.compress(b"")
        
        message = bytearray(generate_header(
            message_type=AUDIO_ONLY_REQUEST,
            message_type_specific_flags=NEG_SEQUENCE,  # last package flag
            serial_method=0,
            compression_type=GZIP_COMPRESSION,
        ))
        message.extend(len(payload_bytes).to_bytes(4, "big"))
        message.extend(payload_bytes)
        
        try:
            await self._ws.send(message)
        except Exception as e:
            logger.error(f"Finish error: {e}")
        
        # Wait a bit for final response
        await asyncio.sleep(0.5)
        
        return self._final_text if self._final_text else self._current_text
    
    async def disconnect(self) -> None:
        """Close WebSocket connection."""
        self._connected = False
        
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
            self._receive_task = None
        
        if self._ws:
            await self._ws.close()
            self._ws = None
        
        logger.info("Disconnected")
    
    def on_partial_result(self, callback: Callable[[str], None]) -> None:
        """Set callback for partial results."""
        self._on_partial = callback
    
    def on_final_result(self, callback: Callable[[str], None]) -> None:
        """Set callback for final result."""
        self._on_final = callback
    
    def on_error(self, callback: Callable[[str], None]) -> None:
        """Set callback for errors."""
        self._on_error = callback
    
    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected
