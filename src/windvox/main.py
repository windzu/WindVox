"""WindVox main entry point and service orchestration."""

import argparse
import asyncio
import logging
import signal
import sys
from enum import Enum
from pathlib import Path
from typing import Optional

from .asr import VolcengineASR
from .audio import AudioCapture
from .config import Config, get_config_path, load_config
from .hotkey import HotkeyManager
from .input import InputSimulator
from .overlay import OverlayWindow, TK_AVAILABLE
from .session import SessionMonitor
from .tray import TrayIcon, TrayState

logger = logging.getLogger(__name__)


class ServiceState(Enum):
    """Service operational states."""
    IDLE = "idle"
    RECORDING = "recording"
    PROCESSING = "processing"
    ERROR = "error"


class WindVoxService:
    """Main WindVox service orchestrator."""
    
    def __init__(self, config: Config):
        """Initialize the service.
        
        Args:
            config: Configuration object.
        """
        self.config = config
        self._state = ServiceState.IDLE
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        
        # Initialize components
        self._audio = AudioCapture(
            sample_rate=config.audio.sample_rate,
            channels=config.audio.channels,
            chunk_duration_ms=config.audio.chunk_duration_ms,
            device_index=config.audio.device_index,
        )
        
        self._asr = VolcengineASR(
            app_key=config.volcengine.app_key,
            access_key=config.volcengine.access_key,
            resource_id=config.volcengine.resource_id,
            ws_url=config.volcengine.ws_url,
        )
        
        self._hotkey = HotkeyManager(
            trigger_key=config.interaction.trigger_key,
            mode=config.interaction.mode,
        )
        
        self._input = InputSimulator(
            delay_ms=config.input.typing_delay_ms,
        )
        
        self._tray = TrayIcon()
        
        # Wire up callbacks
        self._hotkey.on_record_start(self._on_record_start)
        self._hotkey.on_record_stop(self._on_record_stop)
        
        # Set up ASR callbacks for real-time display
        self._asr.on_partial_result(self._on_partial_result)
        self._asr.on_final_result(self._on_final_result)
        self._tray.on_quit(self._on_quit)
        
        # Session monitor for lock screen detection
        self._session = SessionMonitor()
        self._session.on_lock(self._on_session_lock)
        self._session.on_unlock(self._on_session_unlock)
        
        # Overlay window for real-time feedback
        self._overlay: Optional[OverlayWindow] = None
        if TK_AVAILABLE:
            self._overlay = OverlayWindow()
        
        # Audio streaming task
        self._stream_task: Optional[asyncio.Task] = None
    
    def _set_state(self, state: ServiceState) -> None:
        """Update service state and tray icon."""
        if state == self._state:
            return
        
        self._state = state
        logger.info(f"State: {state.value}")
        
        # Map service state to tray state
        tray_states = {
            ServiceState.IDLE: TrayState.IDLE,
            ServiceState.RECORDING: TrayState.RECORDING,
            ServiceState.PROCESSING: TrayState.PROCESSING,
            ServiceState.ERROR: TrayState.ERROR,
        }
        self._tray.set_state(tray_states[state])
    
    def _on_record_start(self) -> None:
        """Handle recording start."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._start_recording(),
                self._loop
            )
    
    def _on_record_stop(self) -> None:
        """Handle recording stop."""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self._stop_recording(),
                self._loop
            )
    
    def _on_quit(self) -> None:
        """Handle quit request."""
        logger.info("Quit requested")
        self._running = False
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
    
    def _on_session_lock(self) -> None:
        """Handle session lock - pause hotkey listener."""
        logger.info("Session locked, pausing hotkey listener")
        self._hotkey.pause()
    
    def _on_session_unlock(self) -> None:
        """Handle session unlock - resume hotkey listener."""
        logger.info("Session unlocked, resuming hotkey listener")
        self._hotkey.resume()
    
    def _on_partial_result(self, text: str) -> None:
        """Handle partial ASR result - update overlay display."""
        if self._overlay and self._state == ServiceState.RECORDING:
            self._overlay.update_text(text)
    
    def _on_final_result(self, text: str) -> None:
        """Handle final ASR result."""
        logger.debug(f"Final result callback: {text}")
    
    async def _start_recording(self) -> None:
        """Start recording and streaming audio."""
        if self._state != ServiceState.IDLE:
            return
        
        logger.info("Starting recording")
        self._set_state(ServiceState.RECORDING)
        
        try:
            # Save active window BEFORE showing overlay
            self._input.window_manager.save_active_window()
            
            # Show overlay window for real-time feedback
            if self._overlay:
                self._overlay.show()
                self._overlay.update_text("🎤 正在聆听...")
            
            # Connect to ASR
            if not await self._asr.connect():
                logger.error("Failed to connect to ASR")
                if self._overlay:
                    self._overlay.hide()
                self._input.window_manager.clear_saved_window()
                self._set_state(ServiceState.ERROR)
                await asyncio.sleep(2)
                self._set_state(ServiceState.IDLE)
                return
            
            # Start audio capture
            self._audio.start()
            
            # Start streaming task
            self._stream_task = asyncio.create_task(self._stream_audio())
            
        except Exception as e:
            logger.error(f"Recording start error: {e}")
            if self._overlay:
                self._overlay.hide()
            self._input.window_manager.clear_saved_window()
            self._set_state(ServiceState.ERROR)
            await asyncio.sleep(2)
            self._set_state(ServiceState.IDLE)
    
    async def _stream_audio(self) -> None:
        """Stream audio chunks to ASR."""
        try:
            async for chunk in self._audio.read_chunks():
                if self._state != ServiceState.RECORDING:
                    break
                await self._asr.send_audio(chunk)
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Streaming error: {e}")
    
    async def _stop_recording(self) -> None:
        """Stop recording and process result."""
        if self._state != ServiceState.RECORDING:
            return
        
        logger.info("Stopping recording")
        self._set_state(ServiceState.PROCESSING)
        
        try:
            # Hide overlay immediately
            if self._overlay:
                self._overlay.hide()
            
            # Stop audio capture
            self._audio.stop()
            
            # Cancel streaming task
            if self._stream_task:
                self._stream_task.cancel()
                try:
                    await self._stream_task
                except asyncio.CancelledError:
                    pass
                self._stream_task = None
            
            # Get final result
            result = await self._asr.finish()
            
            # Disconnect ASR
            await self._asr.disconnect()
            
            # Type the final result
            if result:
                logger.info(f"Final result: {result}")
                await self._input.type_text_async(result)
            else:
                logger.info("No recognition result")
            
        except Exception as e:
            logger.error(f"Processing error: {e}")
            self._set_state(ServiceState.ERROR)
            await asyncio.sleep(2)
        finally:
            self._input.window_manager.clear_saved_window()
            self._set_state(ServiceState.IDLE)
    
    async def run_async(self) -> None:
        """Run the service (async)."""
        self._loop = asyncio.get_running_loop()
        self._running = True
        
        logger.info("WindVox service starting")
        
        # Start overlay window
        if self._overlay:
            self._overlay.start()
        
        # Start components
        self._session.start()
        self._tray.start()
        self._hotkey.start()
        
        logger.info("WindVox ready. Press F2 to start recording.")
        
        # Keep running until stopped
        try:
            while self._running:
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass
        
        # Cleanup
        await self._cleanup()
    
    async def _cleanup(self) -> None:
        """Clean up resources."""
        logger.info("Cleaning up...")
        
        self._hotkey.stop()
        self._session.stop()
        self._audio.stop()
        
        if self._asr.is_connected:
            await self._asr.disconnect()
        
        if self._overlay:
            self._overlay.stop()
        
        self._tray.stop()
        
        logger.info("Cleanup complete")
    
    def run(self) -> None:
        """Run the service (blocking)."""
        # Set up signal handlers
        def signal_handler(sig, frame):
            logger.info(f"Received signal {sig}")
            self._running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Run async event loop
        asyncio.run(self.run_async())


def setup_logging(verbose: bool = False) -> None:
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    
    # Reduce noise from libraries
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("pynput").setLevel(logging.WARNING)


def list_audio_devices() -> None:
    """List available audio input devices."""
    from .audio import AudioCapture
    
    devices = AudioCapture.list_devices()
    
    print("\nAvailable audio input devices:")
    print("-" * 60)
    
    for dev in devices:
        default = " (DEFAULT)" if dev["is_default"] else ""
        print(f"  [{dev['index']}] {dev['name']}{default}")
        print(f"      Channels: {dev['channels']}, Sample Rate: {dev['sample_rate']}")
    
    print("-" * 60)


def validate_config() -> None:
    """Validate configuration file."""
    try:
        config = load_config()
        print(f"✓ Configuration valid: {get_config_path()}")
        print(f"  App Key: {config.volcengine.app_key[:8]}...")
        print(f"  Trigger Key: {config.interaction.trigger_key}")
        print(f"  Mode: {config.interaction.mode}")
    except FileNotFoundError as e:
        print(f"✗ Configuration error: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"✗ Validation error: {e}")
        sys.exit(1)


def test_connection() -> None:
    """Test WebSocket connection to Volcengine."""
    import asyncio
    
    async def _test():
        config = load_config()
        asr = VolcengineASR(
            app_key=config.volcengine.app_key,
            access_key=config.volcengine.access_key,
            resource_id=config.volcengine.resource_id,
            ws_url=config.volcengine.ws_url,
        )
        
        print("Testing connection to Volcengine ASR...")
        
        if await asr.connect():
            print("✓ Connection successful!")
            await asr.disconnect()
        else:
            print("✗ Connection failed")
            sys.exit(1)
    
    asyncio.run(_test())


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="WindVox - Linux Voice Input Service",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List available audio input devices",
    )
    
    parser.add_argument(
        "--validate-config",
        action="store_true",
        help="Validate configuration file",
    )
    
    parser.add_argument(
        "--test-connection",
        action="store_true",
        help="Test connection to Volcengine ASR",
    )
    
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to configuration file",
    )
    
    args = parser.parse_args()
    
    setup_logging(args.verbose)
    
    # Handle utility commands
    if args.list_devices:
        list_audio_devices()
        return
    
    if args.validate_config:
        validate_config()
        return
    
    if args.test_connection:
        test_connection()
        return
    
    # Load configuration
    try:
        config = load_config(args.config)
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    
    # Run service
    service = WindVoxService(config)
    service.run()


if __name__ == "__main__":
    main()
