"""Audio capture module with VAD support."""

import asyncio
import logging
import threading
from collections import deque
from typing import AsyncIterator, Callable, Optional

import numpy as np
import sounddevice as sd

logger = logging.getLogger(__name__)


class AudioCapture:
    """Real-time audio capture with optional Voice Activity Detection (VAD)."""
    
    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        chunk_duration_ms: int = 100,
        device_index: Optional[int] = None,
        vad_threshold: float = 0.01,
        enable_vad: bool = False,
    ):
        """Initialize audio capture.
        
        Args:
            sample_rate: Sample rate in Hz (default 16000 for ASR).
            channels: Number of audio channels (1 = mono).
            chunk_duration_ms: Duration of each audio chunk in milliseconds.
            device_index: Audio device index (None = default).
            vad_threshold: RMS threshold for voice activity detection.
            enable_vad: Whether to filter silent chunks.
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_duration_ms = chunk_duration_ms
        self.device_index = device_index
        self.vad_threshold = vad_threshold
        self.enable_vad = enable_vad
        
        # Calculate samples per chunk
        self.chunk_samples = int(sample_rate * chunk_duration_ms / 1000)
        
        # Audio buffer (thread-safe deque)
        self._buffer: deque[bytes] = deque(maxlen=100)
        self._buffer_lock = threading.Lock()
        
        # Stream control
        self._stream: Optional[sd.InputStream] = None
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._data_event = asyncio.Event()
        
        # Callbacks
        self._on_audio_callback: Optional[Callable[[bytes], None]] = None
    
    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: dict,
        status: sd.CallbackFlags,
    ) -> None:
        """Callback for audio stream."""
        if status:
            logger.warning(f"Audio callback status: {status}")
        
        if not self._running:
            return
        
        # Convert to int16 bytes (little-endian)
        audio_data = (indata * 32767).astype(np.int16).tobytes()
        
        # Apply VAD if enabled
        if self.enable_vad:
            rms = np.sqrt(np.mean(indata ** 2))
            if rms < self.vad_threshold:
                return  # Skip silent chunk
        
        # Add to buffer
        with self._buffer_lock:
            self._buffer.append(audio_data)
        
        # Signal that data is available
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._data_event.set)
        
        # Call callback if set
        if self._on_audio_callback:
            try:
                self._on_audio_callback(audio_data)
            except Exception as e:
                logger.error(f"Audio callback error: {e}")
    
    def start(self) -> None:
        """Start audio capture."""
        if self._running:
            return
        
        logger.info(f"Starting audio capture (device={self.device_index}, rate={self.sample_rate})")
        
        self._running = True
        self._buffer.clear()
        
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None
        
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype=np.float32,
            blocksize=self.chunk_samples,
            device=self.device_index,
            callback=self._audio_callback,
        )
        self._stream.start()
        
        logger.info("Audio capture started")
    
    def stop(self) -> None:
        """Stop audio capture."""
        if not self._running:
            return
        
        logger.info("Stopping audio capture")
        self._running = False
        
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        
        # Signal to wake up any waiting consumers
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._data_event.set)
        
        logger.info("Audio capture stopped")
    
    async def read_chunks(self) -> AsyncIterator[bytes]:
        """Async generator that yields audio chunks.
        
        Yields:
            Audio data as bytes (int16, little-endian).
        """
        while self._running:
            # Wait for data
            await self._data_event.wait()
            self._data_event.clear()
            
            # Yield all available chunks
            while True:
                with self._buffer_lock:
                    if not self._buffer:
                        break
                    chunk = self._buffer.popleft()
                
                yield chunk
    
    def get_chunk(self) -> Optional[bytes]:
        """Get a single audio chunk (non-blocking).
        
        Returns:
            Audio data as bytes, or None if no data available.
        """
        with self._buffer_lock:
            if self._buffer:
                return self._buffer.popleft()
        return None
    
    def set_audio_callback(self, callback: Optional[Callable[[bytes], None]]) -> None:
        """Set a callback to be called for each audio chunk.
        
        Args:
            callback: Function that takes audio bytes, or None to clear.
        """
        self._on_audio_callback = callback
    
    @staticmethod
    def list_devices() -> list[dict]:
        """List available audio input devices.
        
        Returns:
            List of device info dictionaries.
        """
        devices = []
        for i, dev in enumerate(sd.query_devices()):
            if dev["max_input_channels"] > 0:
                devices.append({
                    "index": i,
                    "name": dev["name"],
                    "channels": dev["max_input_channels"],
                    "sample_rate": dev["default_samplerate"],
                    "is_default": i == sd.default.device[0],
                })
        return devices
    
    @property
    def is_running(self) -> bool:
        """Check if audio capture is running."""
        return self._running
