#!/usr/bin/env python3
"""
Splash screen for SC Signature Scanner.
Shows immediately at startup while heavy modules load.
"""

import tkinter as tk
import random


class SplashScreen:
    """Heavily animated splash screen shown during startup."""

    # Colors - matching RegolithTheme
    BG_COLOR = "#0d1117"
    ACCENT_COLOR = "#f0883e"
    ACCENT_DIM = "#a85a20"
    ACCENT_BRIGHT = "#ffaa55"
    ACCENT_GLOW = "#ffcc88"
    TEXT_COLOR = "#e6edf3"
    MUTED_COLOR = "#8b949e"
    SCAN_COLOR = "#3fb950"
    WARN_COLOR = "#f85149"

    def __init__(self):
        self.root = tk.Tk()
        self.root.overrideredirect(True)  # No window decorations
        self.root.attributes('-topmost', True)
        self.root.configure(bg=self.BG_COLOR)

        # Size and center
        width = 450
        height = 200
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.root.geometry(f"{width}x{height}+{x}+{y}")

        # Animated border frame
        self.border = tk.Frame(self.root, bg=self.ACCENT_COLOR, padx=2, pady=2)
        self.border.pack(fill=tk.BOTH, expand=True)

        inner = tk.Frame(self.border, bg=self.BG_COLOR, padx=15, pady=12)
        inner.pack(fill=tk.BOTH, expand=True)

        # Top row with radar and activity indicator
        top_row = tk.Frame(inner, bg=self.BG_COLOR)
        top_row.pack(fill=tk.X, pady=(0, 5))

        # Radar icon
        self.radar_frames = ["📡", "📡 ·", "📡 · ·", "📡 · · ·", "📡 · ·", "📡 ·"]
        self.radar_label = tk.Label(
            top_row,
            text="📡",
            font=("Segoe UI", 27),
            bg=self.BG_COLOR
        )
        self.radar_label.pack(side=tk.LEFT)

        # Title (static)
        self.title = tk.Label(
            inner,
            text="SC Signature Scanner",
            font=("Segoe UI", 18, "bold"),
            fg=self.ACCENT_COLOR,
            bg=self.BG_COLOR
        )
        self.title.pack(pady=(0, 5))

        # Subtitle typing effect
        self.subtitle_text = "Initializing scanner systems..."
        self.subtitle = tk.Label(
            inner,
            text="",
            font=("Consolas", 9),
            fg=self.MUTED_COLOR,
            bg=self.BG_COLOR
        )
        self.subtitle.pack(pady=(0, 8))

        # Status message
        self.status_label = tk.Label(
            inner,
            text="Starting...",
            font=("Segoe UI", 10),
            fg=self.TEXT_COLOR,
            bg=self.BG_COLOR
        )
        self.status_label.pack(pady=(0, 8))

        # Scanning line
        scan_container = tk.Frame(inner, bg=self.BG_COLOR)
        scan_container.pack(fill=tk.X, pady=(0, 5))

        self.scan_label = tk.Label(
            scan_container,
            text="",
            font=("Consolas", 9),
            fg=self.ACCENT_COLOR,
            bg=self.BG_COLOR
        )
        self.scan_label.pack()

        # Progress bar with bouncing pixel
        self.progress_label = tk.Label(
            inner,
            text="",
            font=("Consolas", 9),
            fg=self.SCAN_COLOR,
            bg=self.BG_COLOR
        )
        self.progress_label.pack(fill=tk.X, pady=(5, 5))

        # Data stream at bottom
        self.data_label = tk.Label(
            inner,
            text="",
            font=("Consolas", 8),
            fg=self.MUTED_COLOR,
            bg=self.BG_COLOR
        )
        self.data_label.pack(pady=(5, 0))

        # Animation state
        self.frame = 0
        self.progress_pos = 0
        self.progress_dir = 1
        self.typing_pos = 0
        self._after_ids = []
        self._status_text = "Starting..."

        # Start animations
        self._animate_scan()
        self._animate_radar()
        self._animate_typing()
        self._animate_progress()
        self._animate_data()

        # Force display and run initial animation frames
        self.root.update()
        self.pump(20)  # Let animations run visibly at startup

    def _animate_scan(self):
        """Animate scanning effect."""
        width = 45

        # Scanner position bounces back and forth
        pos = self.frame % (width * 2)
        if pos >= width:
            pos = width * 2 - pos - 1

        # Build scan line with gradient trail
        chars = []
        for i in range(width):
            dist = abs(i - pos)
            if dist == 0:
                chars.append("█")
            elif dist == 1:
                chars.append("▓")
            elif dist == 2:
                chars.append("▒")
            elif dist == 3:
                chars.append("░")
            else:
                chars.append("·")
        self.scan_label.config(text="".join(chars))

        self.frame += 1
        self._after_ids.append(self.root.after(40, self._animate_scan))

    def _animate_radar(self):
        """Animate radar with signal pulses."""
        idx = (self.frame // 3) % len(self.radar_frames)
        self.radar_label.config(text=self.radar_frames[idx])
        self._after_ids.append(self.root.after(100, self._animate_radar))

    def _animate_typing(self):
        """Type out subtitle text."""
        if self.typing_pos <= len(self.subtitle_text):
            self.subtitle.config(text=self.subtitle_text[:self.typing_pos] + "█")
            self.typing_pos += 1
            self._after_ids.append(self.root.after(60, self._animate_typing))
        else:
            self.subtitle.config(text=self.subtitle_text)

    def _animate_progress(self):
        """Animate bouncing pixel on progress bar."""
        width = 45

        # Move pixel
        self.progress_pos += self.progress_dir
        if self.progress_pos >= width - 1:
            self.progress_dir = -1
        elif self.progress_pos <= 0:
            self.progress_dir = 1

        # Build bar with bouncing pixel
        chars = ["─"] * width
        chars[self.progress_pos] = "●"
        self.progress_label.config(text="".join(chars))

        self._after_ids.append(self.root.after(35, self._animate_progress))

    def _animate_data(self):
        """Animate data stream at bottom."""
        hex_chars = "0123456789ABCDEF"
        data = " ".join("".join(random.choice(hex_chars) for _ in range(2)) for _ in range(16))
        self.data_label.config(text=f"[{data}]")
        self._after_ids.append(self.root.after(60, self._animate_data))

    def set_status(self, message: str):
        """Update status message and pump event loop for animations."""
        self._status_text = message
        self.status_label.config(text=message)
        # Pump event loop multiple times to let animations run
        self.pump(15)

    def pump(self, iterations: int = 10):
        """Pump the event loop to allow animations to run during blocking imports."""
        import time
        for _ in range(iterations):
            try:
                self.root.update()
                time.sleep(0.03)  # ~30fps
            except:
                break

    def close(self):
        """Close the splash screen."""
        for after_id in self._after_ids:
            try:
                self.root.after_cancel(after_id)
            except:
                pass
        self.root.destroy()


def show_splash() -> SplashScreen:
    """Create and show splash screen. Returns instance for later closing."""
    return SplashScreen()
