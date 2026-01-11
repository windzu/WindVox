"""Simple keyboard input using shell commands."""

import subprocess
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class WindowManager:
    """Manages window focus."""
    
    def __init__(self):
        self._saved_window_id: Optional[str] = None
    
    def save_active_window(self) -> bool:
        """Save the currently active window ID."""
        try:
            result = subprocess.run(
                ["xdotool", "getactivewindow"],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0:
                self._saved_window_id = result.stdout.strip()
                logger.debug(f"Saved window: {self._saved_window_id}")
                return True
        except Exception as e:
            logger.warning(f"Failed to save window: {e}")
        return False
    
    def restore_active_window(self) -> bool:
        """Restore focus to the saved window."""
        if not self._saved_window_id:
            return False
        try:
            subprocess.run(
                ["xdotool", "windowactivate", "--sync", self._saved_window_id],
                timeout=2
            )
            return True
        except Exception as e:
            logger.warning(f"Failed to restore window: {e}")
        return False
    
    def clear_saved_window(self) -> None:
        """Clear saved window."""
        self._saved_window_id = None


class InputSimulator:
    """Simple text input using xclip + xdotool."""
    
    def __init__(self, delay_ms: int = 10):
        self.delay_ms = delay_ms
        self.window_manager = WindowManager()
    
    def _get_clipboard(self) -> Optional[bytes]:
        """Get current clipboard content."""
        try:
            result = subprocess.run(
                ["xclip", "-selection", "clipboard", "-o"],
                capture_output=True,
                timeout=2
            )
            if result.returncode == 0:
                return result.stdout
        except Exception as e:
            logger.debug(f"Failed to get clipboard: {e}")
        return None
    
    def _set_clipboard(self, content: bytes) -> None:
        """Set clipboard content."""
        try:
            proc = subprocess.Popen(
                ["xclip", "-selection", "clipboard"],
                stdin=subprocess.PIPE
            )
            proc.communicate(input=content, timeout=5)
        except Exception as e:
            logger.debug(f"Failed to set clipboard: {e}")
    
    def type_text(self, text: str, restore_focus: bool = True) -> None:
        """Type text using clipboard paste.
        
        Uses the exact same method as the verified shell command:
        echo "text" | xclip -selection clipboard && xdotool key ctrl+v
        
        Preserves the user's original clipboard content by saving and restoring it.
        """
        if not text:
            return
        
        logger.info(f"Pasting: {text[:50]}...")
        
        # Save original clipboard content
        original_clipboard = self._get_clipboard()
        
        # Restore focus first
        if restore_focus:
            self.window_manager.restore_active_window()
        
        try:
            # Copy to clipboard (same as: echo "text" | xclip -selection clipboard)
            proc = subprocess.Popen(
                ["xclip", "-selection", "clipboard"],
                stdin=subprocess.PIPE
            )
            proc.communicate(input=text.encode('utf-8'), timeout=5)
            
            # Paste (same as: xdotool key ctrl+v)
            subprocess.run(
                ["xdotool", "key", "ctrl+v"],
                timeout=5
            )
            
            logger.info("Paste complete")
            
        except Exception as e:
            logger.error(f"Paste failed: {e}")
        finally:
            # Restore original clipboard content
            if original_clipboard is not None:
                # Small delay to ensure paste completes before restoring
                import time
                time.sleep(0.1)
                self._set_clipboard(original_clipboard)
                logger.debug("Clipboard restored")
    
    async def type_text_async(self, text: str, restore_focus: bool = True) -> None:
        """Async wrapper - just calls sync version directly."""
        self.type_text(text, restore_focus)

