"""Hotkey listener module."""

import logging
import threading
from typing import Callable, Optional

from pynput import keyboard as kb

logger = logging.getLogger(__name__)


class HotkeyManager:
    """Global hotkey listener for recording control."""
    
    def __init__(
        self,
        trigger_key: str = "f2",
        mode: str = "push_to_talk",
    ):
        """Initialize hotkey manager.
        
        Args:
            trigger_key: Key to trigger recording (e.g., "f2", "ctrl+shift+r").
            mode: "push_to_talk" (hold to record) or "toggle" (press to start/stop).
        """
        self.trigger_key = trigger_key.lower()
        self.mode = mode
        
        self._listener: Optional[kb.Listener] = None
        self._running = False
        self._recording = False
        self._key_pressed = False
        
        # Parse trigger key
        self._target_key = self._parse_key(self.trigger_key)
        
        # Callbacks
        self._on_start: Optional[Callable[[], None]] = None
        self._on_stop: Optional[Callable[[], None]] = None
    
    def _parse_key(self, key_str: str) -> kb.Key | kb.KeyCode:
        """Parse key string to pynput key."""
        key_str = key_str.lower().strip()
        
        # Try special keys first
        special_keys = {
            "f1": kb.Key.f1,
            "f2": kb.Key.f2,
            "f3": kb.Key.f3,
            "f4": kb.Key.f4,
            "f5": kb.Key.f5,
            "f6": kb.Key.f6,
            "f7": kb.Key.f7,
            "f8": kb.Key.f8,
            "f9": kb.Key.f9,
            "f10": kb.Key.f10,
            "f11": kb.Key.f11,
            "f12": kb.Key.f12,
            "space": kb.Key.space,
            "enter": kb.Key.enter,
            "tab": kb.Key.tab,
            "escape": kb.Key.esc,
            "esc": kb.Key.esc,
            "ctrl": kb.Key.ctrl,
            "alt": kb.Key.alt,
            "shift": kb.Key.shift,
            "caps_lock": kb.Key.caps_lock,
            "insert": kb.Key.insert,
            "delete": kb.Key.delete,
            "home": kb.Key.home,
            "end": kb.Key.end,
            "page_up": kb.Key.page_up,
            "page_down": kb.Key.page_down,
            "pause": kb.Key.pause,
            "scroll_lock": kb.Key.scroll_lock,
            "print_screen": kb.Key.print_screen,
        }
        
        if key_str in special_keys:
            return special_keys[key_str]
        
        # Single character
        if len(key_str) == 1:
            return kb.KeyCode.from_char(key_str)
        
        # Default to F2
        logger.warning(f"Unknown key '{key_str}', defaulting to F2")
        return kb.Key.f2
    
    def _on_press(self, key: kb.Key | kb.KeyCode | None) -> None:
        """Handle key press event."""
        if key == self._target_key and not self._key_pressed:
            self._key_pressed = True
            
            if self.mode == "push_to_talk":
                # Start recording on key press
                if not self._recording:
                    self._recording = True
                    logger.info("Recording started (push-to-talk)")
                    if self._on_start:
                        threading.Thread(target=self._on_start, daemon=True).start()
            
            elif self.mode == "toggle":
                # Toggle recording state
                if self._recording:
                    self._recording = False
                    logger.info("Recording stopped (toggle)")
                    if self._on_stop:
                        threading.Thread(target=self._on_stop, daemon=True).start()
                else:
                    self._recording = True
                    logger.info("Recording started (toggle)")
                    if self._on_start:
                        threading.Thread(target=self._on_start, daemon=True).start()
    
    def _on_release(self, key: kb.Key | kb.KeyCode | None) -> None:
        """Handle key release event."""
        if key == self._target_key:
            self._key_pressed = False
            
            if self.mode == "push_to_talk":
                # Stop recording on key release
                if self._recording:
                    self._recording = False
                    logger.info("Recording stopped (push-to-talk)")
                    if self._on_stop:
                        threading.Thread(target=self._on_stop, daemon=True).start()
    
    def start(self) -> None:
        """Start listening for hotkeys."""
        if self._running:
            return
        
        logger.info(f"Starting hotkey listener (key={self.trigger_key}, mode={self.mode})")
        
        self._running = True
        self._recording = False
        self._key_pressed = False
        
        self._listener = kb.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.start()
        
        logger.info("Hotkey listener started")
    
    def stop(self) -> None:
        """Stop listening for hotkeys."""
        if not self._running:
            return
        
        logger.info("Stopping hotkey listener")
        self._running = False
        
        if self._listener:
            self._listener.stop()
            self._listener = None
        
        logger.info("Hotkey listener stopped")
    
    def on_record_start(self, callback: Callable[[], None]) -> None:
        """Set callback for recording start."""
        self._on_start = callback
    
    def on_record_stop(self, callback: Callable[[], None]) -> None:
        """Set callback for recording stop."""
        self._on_stop = callback
    
    @property
    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self._recording
