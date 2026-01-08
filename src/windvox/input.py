"""Keyboard input simulation module."""

import asyncio
import logging
import shutil
import subprocess
import time
from typing import Optional

logger = logging.getLogger(__name__)


class InputSimulator:
    """Simulates keyboard input to type text."""
    
    def __init__(self, delay_ms: int = 10):
        """Initialize input simulator.
        
        Args:
            delay_ms: Delay between keystrokes in milliseconds.
        """
        self.delay_ms = delay_ms
        self._use_xdotool = shutil.which("xdotool") is not None
        
        if self._use_xdotool:
            logger.debug("Using xdotool for input simulation")
        else:
            logger.debug("Using pynput for input simulation")
            from pynput import keyboard as kb
            self._controller = kb.Controller()
    
    def type_text(self, text: str) -> None:
        """Type text by simulating keyboard input.
        
        Args:
            text: Text to type (supports Unicode/Chinese).
        """
        if not text:
            return
        
        logger.info(f"Typing text: {text[:50]}...")
        
        if self._use_xdotool:
            self._type_with_xdotool(text)
        else:
            self._type_with_pynput(text)
        
        logger.info("Text input complete")
    
    def _type_with_xdotool(self, text: str) -> None:
        """Type text using xdotool (more reliable for Unicode)."""
        try:
            # xdotool type handles Unicode well
            # Add delay between characters for reliability
            subprocess.run(
                ["xdotool", "type", "--delay", str(self.delay_ms), "--", text],
                check=True,
                timeout=30
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"xdotool type failed: {e}")
        except subprocess.TimeoutExpired:
            logger.error("xdotool type timed out")
    
    def _type_with_pynput(self, text: str) -> None:
        """Type text using pynput."""
        from pynput import keyboard as kb
        
        delay_sec = self.delay_ms / 1000.0
        controller = getattr(self, '_controller', kb.Controller())
        
        for char in text:
            try:
                controller.type(char)
                if delay_sec > 0:
                    time.sleep(delay_sec)
            except Exception as e:
                logger.warning(f"Failed to type character '{char}': {e}")
    
    async def type_text_async(self, text: str) -> None:
        """Async version of type_text.
        
        Args:
            text: Text to type.
        """
        if not text:
            return
        
        logger.info(f"Typing text (async): {text[:50]}...")
        
        if self._use_xdotool:
            # Run xdotool in executor to not block event loop
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._type_with_xdotool, text)
        else:
            await self._type_with_pynput_async(text)
        
        logger.info("Text input complete")
    
    async def _type_with_pynput_async(self, text: str) -> None:
        """Type text using pynput (async)."""
        from pynput import keyboard as kb
        
        delay_sec = self.delay_ms / 1000.0
        controller = getattr(self, '_controller', kb.Controller())
        
        for char in text:
            try:
                controller.type(char)
                if delay_sec > 0:
                    await asyncio.sleep(delay_sec)
            except Exception as e:
                logger.warning(f"Failed to type character '{char}': {e}")
    
    def press_key(self, key: str) -> None:
        """Press a single key.
        
        Args:
            key: Key to press (e.g., "enter", "tab", "a").
        """
        if self._use_xdotool:
            try:
                subprocess.run(["xdotool", "key", key], check=True, timeout=5)
            except Exception as e:
                logger.warning(f"Failed to press key '{key}': {e}")
        else:
            from pynput import keyboard as kb
            try:
                if hasattr(kb.Key, key.lower()):
                    self._controller.press(getattr(kb.Key, key.lower()))
                    self._controller.release(getattr(kb.Key, key.lower()))
                else:
                    self._controller.press(key)
                    self._controller.release(key)
            except Exception as e:
                logger.warning(f"Failed to press key '{key}': {e}")
    
    def press_combo(self, *keys: str) -> None:
        """Press a key combination.
        
        Args:
            keys: Keys to press together (e.g., "ctrl", "v").
        """
        if self._use_xdotool:
            try:
                combo = "+".join(keys)
                subprocess.run(["xdotool", "key", combo], check=True, timeout=5)
            except Exception as e:
                logger.warning(f"Failed to press combo {keys}: {e}")
        else:
            from pynput import keyboard as kb
            pressed = []
            try:
                for key in keys:
                    if hasattr(kb.Key, key.lower()):
                        k = getattr(kb.Key, key.lower())
                    else:
                        k = key
                    self._controller.press(k)
                    pressed.append(k)
                
                for k in reversed(pressed):
                    self._controller.release(k)
                    
            except Exception as e:
                logger.warning(f"Failed to press combo {keys}: {e}")
                for k in pressed:
                    try:
                        self._controller.release(k)
                    except:
                        pass
