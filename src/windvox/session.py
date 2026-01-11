"""Session monitor module for detecting screen lock/unlock events."""

import logging
import threading
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Try to import D-Bus
DBUS_AVAILABLE = False
try:
    import dbus
    from dbus.mainloop.glib import DBusGMainLoop
    from gi.repository import GLib
    DBUS_AVAILABLE = True
except ImportError:
    logger.warning("D-Bus libraries not available, session monitoring disabled")


class SessionMonitor:
    """Monitor session lock/unlock events via D-Bus.
    
    Listens to org.freedesktop.ScreenSaver.ActiveChanged signal to detect
    when the screen is locked or unlocked.
    """
    
    def __init__(self):
        """Initialize session monitor."""
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional["GLib.MainLoop"] = None
        
        # Callbacks
        self._on_lock: Optional[Callable[[], None]] = None
        self._on_unlock: Optional[Callable[[], None]] = None
    
    def on_lock(self, callback: Callable[[], None]) -> None:
        """Set callback for session lock event."""
        self._on_lock = callback
    
    def on_unlock(self, callback: Callable[[], None]) -> None:
        """Set callback for session unlock event."""
        self._on_unlock = callback
    
    def _handle_screensaver_active(self, active: bool) -> None:
        """Handle screensaver ActiveChanged signal.
        
        Args:
            active: True if screen is locked, False if unlocked.
        """
        if active:
            logger.info("Screen locked detected")
            if self._on_lock:
                try:
                    self._on_lock()
                except Exception as e:
                    logger.error(f"Lock callback error: {e}")
        else:
            logger.info("Screen unlocked detected")
            if self._on_unlock:
                try:
                    self._on_unlock()
                except Exception as e:
                    logger.error(f"Unlock callback error: {e}")
    
    def _run_dbus_loop(self) -> None:
        """Run the D-Bus main loop in a background thread."""
        if not DBUS_AVAILABLE:
            return
        
        try:
            # Set up D-Bus main loop integration with GLib
            DBusGMainLoop(set_as_default=True)
            
            # Connect to session bus
            bus = dbus.SessionBus()
            
            # Listen for org.freedesktop.ScreenSaver.ActiveChanged
            bus.add_signal_receiver(
                self._handle_screensaver_active,
                dbus_interface="org.freedesktop.ScreenSaver",
                signal_name="ActiveChanged",
            )
            
            # Also listen for GNOME screensaver (used by some distros)
            bus.add_signal_receiver(
                self._handle_screensaver_active,
                dbus_interface="org.gnome.ScreenSaver",
                signal_name="ActiveChanged",
            )
            
            logger.info("Session monitor started, listening for lock/unlock events")
            
            # Run the main loop
            self._loop = GLib.MainLoop()
            self._loop.run()
            
        except Exception as e:
            logger.error(f"D-Bus session monitor error: {e}")
    
    def start(self) -> None:
        """Start monitoring session events."""
        if self._running:
            return
        
        if not DBUS_AVAILABLE:
            logger.warning("Session monitoring not available (D-Bus not installed)")
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._run_dbus_loop, daemon=True)
        self._thread.start()
        
        logger.info("Session monitor started")
    
    def stop(self) -> None:
        """Stop monitoring session events."""
        if not self._running:
            return
        
        self._running = False
        
        if self._loop:
            self._loop.quit()
            self._loop = None
        
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None
        
        logger.info("Session monitor stopped")
