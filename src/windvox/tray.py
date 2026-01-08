"""System tray icon module."""

import logging
import threading
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)


class TrayState(Enum):
    """Tray icon states."""
    IDLE = "idle"
    RECORDING = "recording"
    PROCESSING = "processing"
    ERROR = "error"


class TrayIcon:
    """System tray icon for WindVox status display."""
    
    ICON_SIZE = 64
    
    # Colors for different states
    COLORS = {
        TrayState.IDLE: "#808080",       # Gray
        TrayState.RECORDING: "#FF4444",   # Red
        TrayState.PROCESSING: "#FFAA00", # Yellow/Orange
        TrayState.ERROR: "#FF0000",       # Bright Red
    }
    
    def __init__(self):
        """Initialize tray icon."""
        self._icon = None
        self._state = TrayState.IDLE
        self._thread: Optional[threading.Thread] = None
        self._running = False
        
        # Callbacks
        self._on_quit: Optional[Callable[[], None]] = None
        
        # Generate icons
        self._icons = {state: self._create_icon(state) for state in TrayState}
    
    def _create_icon(self, state: TrayState) -> Image.Image:
        """Create an icon for the given state.
        
        Args:
            state: Icon state.
            
        Returns:
            PIL Image object.
        """
        size = self.ICON_SIZE
        color = self.COLORS[state]
        
        # Create transparent background
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        # Draw filled circle
        margin = 4
        draw.ellipse(
            [margin, margin, size - margin, size - margin],
            fill=color,
        )
        
        # Add state-specific decorations
        if state == TrayState.RECORDING:
            # Add inner darker circle for "recording" effect
            inner_margin = 16
            draw.ellipse(
                [inner_margin, inner_margin, size - inner_margin, size - inner_margin],
                fill="#CC0000",
            )
        
        elif state == TrayState.PROCESSING:
            # Add rotating dots (static representation)
            center = size // 2
            dot_radius = 4
            for i in range(3):
                angle = i * 120
                import math
                x = center + int(12 * math.cos(math.radians(angle)))
                y = center + int(12 * math.sin(math.radians(angle)))
                draw.ellipse(
                    [x - dot_radius, y - dot_radius, x + dot_radius, y + dot_radius],
                    fill="#FFFFFF",
                )
        
        elif state == TrayState.ERROR:
            # Add X mark
            line_color = "#FFFFFF"
            line_width = 4
            offset = 18
            draw.line(
                [(offset, offset), (size - offset, size - offset)],
                fill=line_color,
                width=line_width,
            )
            draw.line(
                [(size - offset, offset), (offset, size - offset)],
                fill=line_color,
                width=line_width,
            )
        
        return img
    
    def _create_menu(self):
        """Create the tray menu."""
        import pystray
        
        return pystray.Menu(
            pystray.MenuItem("WindVox", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._handle_quit),
        )
    
    def _handle_quit(self, icon, item) -> None:
        """Handle quit menu item."""
        logger.info("Quit requested from tray")
        if self._on_quit:
            self._on_quit()
        self.stop()
    
    def start(self) -> None:
        """Start the tray icon in a background thread."""
        if self._running:
            return
        
        logger.info("Starting tray icon")
        self._running = True
        
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
    
    def _run(self) -> None:
        """Run the tray icon (blocking)."""
        try:
            import pystray
            
            self._icon = pystray.Icon(
                name="windvox",
                icon=self._icons[TrayState.IDLE],
                title="WindVox - Ready",
                menu=self._create_menu(),
            )
            
            logger.info("Tray icon running")
            self._icon.run()
            
        except Exception as e:
            logger.error(f"Tray icon error: {e}")
        finally:
            self._running = False
            logger.info("Tray icon stopped")
    
    def stop(self) -> None:
        """Stop the tray icon."""
        if not self._running:
            return
        
        logger.info("Stopping tray icon")
        self._running = False
        
        if self._icon:
            try:
                self._icon.stop()
            except Exception as e:
                logger.warning(f"Error stopping tray icon: {e}")
            self._icon = None
    
    def set_state(self, state: TrayState) -> None:
        """Update the tray icon state.
        
        Args:
            state: New state.
        """
        if state == self._state:
            return
        
        self._state = state
        logger.debug(f"Tray state: {state.value}")
        
        if self._icon:
            try:
                self._icon.icon = self._icons[state]
                
                # Update title
                titles = {
                    TrayState.IDLE: "WindVox - Ready",
                    TrayState.RECORDING: "WindVox - Recording...",
                    TrayState.PROCESSING: "WindVox - Processing...",
                    TrayState.ERROR: "WindVox - Error",
                }
                self._icon.title = titles.get(state, "WindVox")
                
            except Exception as e:
                logger.warning(f"Failed to update tray icon: {e}")
    
    def on_quit(self, callback: Callable[[], None]) -> None:
        """Set callback for quit action."""
        self._on_quit = callback
    
    @property
    def is_running(self) -> bool:
        """Check if tray icon is running."""
        return self._running
