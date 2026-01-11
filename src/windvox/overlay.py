"""Overlay window for real-time ASR result display.

Uses a subprocess to run Tkinter in its own process,
since Tkinter must run in the main thread.
"""

import logging
import subprocess
import sys
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Overlay subprocess script
OVERLAY_SCRIPT = '''
import tkinter as tk
import sys
import select

def main():
    root = tk.Tk()
    root.withdraw()
    root.overrideredirect(True)
    root.attributes('-topmost', True)
    try:
        root.attributes('-alpha', 0.92)
    except:
        pass
    
    frame = tk.Frame(root, bg='#1a1a1a', padx=16, pady=12)
    frame.pack(fill='both', expand=True)
    
    label = tk.Label(
        frame,
        text="🎤 正在聆听...",
        font=('Sans', 14, 'bold'),
        fg='#ffffff',
        bg='#1a1a1a',
        justify='left',
        wraplength=560,
        anchor='nw'
    )
    label.pack(fill='both', expand=True)
    root.configure(bg='#1a1a1a')
    
    visible = False
    
    def check_stdin():
        nonlocal visible
        try:
            if select.select([sys.stdin], [], [], 0)[0]:
                line = sys.stdin.readline().strip()
                if line == 'QUIT':
                    root.quit()
                    return
                elif line == 'SHOW':
                    screen_w = root.winfo_screenwidth()
                    screen_h = root.winfo_screenheight()
                    win_w, win_h = 600, 120  # Large enough for 3 lines
                    x = (screen_w - win_w) // 2
                    y = screen_h - win_h - 60
                    root.geometry(f"{win_w}x{win_h}+{x}+{y}")
                    root.deiconify()
                    root.lift()
                    visible = True
                elif line == 'HIDE':
                    root.withdraw()
                    visible = False
                elif line.startswith('TEXT:'):
                    text = line[5:]
                    if visible:
                        label.config(text=text if text else "🎤 正在聆听...")
        except:
            pass
        root.after(50, check_stdin)
    
    root.after(50, check_stdin)
    root.mainloop()

if __name__ == '__main__':
    main()
'''


class OverlayWindow:
    """Overlay window using subprocess for Tkinter compatibility."""
    
    def __init__(self):
        self._process: Optional[subprocess.Popen] = None
        self._visible = False
    
    def start(self) -> None:
        """Start the overlay subprocess."""
        if self._process:
            return
        
        try:
            self._process = subprocess.Popen(
                [sys.executable, '-c', OVERLAY_SCRIPT],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            logger.debug("Overlay subprocess started")
        except Exception as e:
            logger.error(f"Failed to start overlay: {e}")
            self._process = None
    
    def stop(self) -> None:
        """Stop the overlay subprocess."""
        if not self._process:
            return
        
        try:
            self._send('QUIT')
            self._process.wait(timeout=1)
        except:
            try:
                self._process.kill()
            except:
                pass
        
        self._process = None
        self._visible = False
        logger.debug("Overlay subprocess stopped")
    
    def _send(self, message: str) -> None:
        """Send a message to the subprocess."""
        if not self._process or not self._process.stdin:
            return
        
        try:
            self._process.stdin.write(message + '\n')
            self._process.stdin.flush()
        except:
            pass
    
    def show(self, x: Optional[int] = None, y: Optional[int] = None) -> None:
        """Show the overlay window."""
        self._send('SHOW')
        self._visible = True
    
    def hide(self) -> None:
        """Hide the overlay window."""
        self._send('HIDE')
        self._visible = False
    
    def update_text(self, text: str) -> None:
        """Update the displayed text."""
        display_text = text if text else "🎤 正在聆听..."
        self._send(f'TEXT:{display_text}')
    
    @property
    def is_visible(self) -> bool:
        return self._visible


# Check if we can run
TK_AVAILABLE = True
GTK_AVAILABLE = True

def start_gtk_main_loop() -> None:
    pass

def stop_gtk_main_loop() -> None:
    pass
