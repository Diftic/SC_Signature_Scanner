#!/usr/bin/env python3
"""
Identifier Window for SC Signature Scanner.
A calibration overlay that the user positions over the HUD targeting circle.
"""

import json
import tkinter as tk
from pathlib import Path
from typing import Optional, Tuple, Callable


class IdentifierWindow:
    """A semi-transparent overlay window with a circle for HUD calibration."""
    
    CONFIG_FILE = Path(__file__).parent / "identifier_config.json"
    
    # Default signature offset multipliers (relative to circle diameter)
    # Signature is to the upper-right of the circle
    DEFAULT_OFFSET_X = 5.0  # Multiplier for X offset (positive = right)
    DEFAULT_OFFSET_Y = -3.5  # Multiplier for Y offset (negative = up)
    DEFAULT_SCAN_PADDING = 1.5  # Padding around signature center
    
    def __init__(self, on_save_callback: Optional[Callable] = None):
        """Initialize the identifier window.
        
        Args:
            on_save_callback: Function to call when position is saved.
                             Receives (center_x, center_y, diameter) as args.
        """
        self.on_save_callback = on_save_callback
        self.root: Optional[tk.Tk] = None
        self.canvas: Optional[tk.Canvas] = None
        
        # Window state
        self.is_open = False
        self._drag_start_x = 0
        self._drag_start_y = 0
        
        # Load saved config
        self.config = self._load_config()
    
    def _load_config(self) -> dict:
        """Load saved configuration."""
        default = {
            'x': 100,
            'y': 100,
            'size': 200,  # Window size (square)
            'offset_x': self.DEFAULT_OFFSET_X,
            'offset_y': self.DEFAULT_OFFSET_Y,
            'scan_padding': self.DEFAULT_SCAN_PADDING,
        }
        
        if self.CONFIG_FILE.exists():
            try:
                with open(self.CONFIG_FILE, 'r') as f:
                    saved = json.load(f)
                    default.update(saved)
            except (json.JSONDecodeError, IOError):
                pass
        
        return default
    
    def _save_config(self):
        """Save current configuration."""
        try:
            with open(self.CONFIG_FILE, 'w') as f:
                json.dump(self.config, f, indent=2)
        except IOError as e:
            print(f"Failed to save config: {e}")
    
    def open(self):
        """Open the identifier window."""
        if self.is_open:
            self.root.lift()
            return
        
        self.root = tk.Tk()
        self.root.title("HUD Identifier")
        
        # Window properties
        size = self.config['size']
        x = self.config['x']
        y = self.config['y']
        
        self.root.geometry(f"{size}x{size}+{x}+{y}")
        self.root.attributes('-topmost', True)  # Always on top
        self.root.attributes('-alpha', 0.7)  # Semi-transparent
        self.root.resizable(True, True)
        
        # Remove window decorations for cleaner look (optional)
        # self.root.overrideredirect(True)
        
        # Canvas for drawing
        self.canvas = tk.Canvas(
            self.root, 
            bg='black',
            highlightthickness=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Draw the circle
        self._draw_circle()
        
        # Bindings
        self.canvas.bind('<Button-1>', self._on_drag_start)
        self.canvas.bind('<B1-Motion>', self._on_drag)
        self.canvas.bind('<ButtonRelease-1>', self._on_drag_end)
        self.root.bind('<Configure>', self._on_resize)
        self.root.bind('<Escape>', lambda e: self.close())
        self.root.bind('<Return>', lambda e: self._save_and_close())
        self.root.bind('<s>', lambda e: self._save_and_close())
        
        # Instructions label
        self.instructions = tk.Label(
            self.root,
            text="Drag to move | Resize edges | Enter/S to save | Esc to cancel",
            bg='black',
            fg='yellow',
            font=('Arial', 8)
        )
        self.instructions.place(relx=0.5, rely=0.95, anchor='center')
        
        self.is_open = True
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.mainloop()
    
    def _draw_circle(self):
        """Draw the targeting circle on the canvas."""
        if not self.canvas:
            return
        
        self.canvas.delete('all')
        
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        
        if w < 10 or h < 10:
            return
        
        # Circle parameters
        padding = 10  # Pixels from edge
        cx, cy = w // 2, h // 2
        radius = min(w, h) // 2 - padding
        
        # Draw outer circle (the targeting ring)
        self.canvas.create_oval(
            cx - radius, cy - radius,
            cx + radius, cy + radius,
            outline='#00FF00',  # Green
            width=3
        )
        
        # Draw center crosshair
        cross_size = 10
        self.canvas.create_line(cx - cross_size, cy, cx + cross_size, cy, fill='#00FF00', width=1)
        self.canvas.create_line(cx, cy - cross_size, cx, cy + cross_size, fill='#00FF00', width=1)
        
        # Draw center dot
        self.canvas.create_oval(
            cx - 3, cy - 3, cx + 3, cy + 3,
            fill='#FF0000', outline='#FF0000'
        )
        
        # Show current diameter
        diameter = radius * 2
        self.canvas.create_text(
            cx, cy + radius + 15,
            text=f"⌀ {diameter}px",
            fill='yellow',
            font=('Arial', 10)
        )
    
    def _on_drag_start(self, event):
        """Start dragging the window."""
        self._drag_start_x = event.x
        self._drag_start_y = event.y
    
    def _on_drag(self, event):
        """Drag the window."""
        if not self.root:
            return
        
        dx = event.x - self._drag_start_x
        dy = event.y - self._drag_start_y
        
        x = self.root.winfo_x() + dx
        y = self.root.winfo_y() + dy
        
        self.root.geometry(f"+{x}+{y}")
    
    def _on_drag_end(self, event):
        """End dragging - update config."""
        if self.root:
            self.config['x'] = self.root.winfo_x()
            self.config['y'] = self.root.winfo_y()
    
    def _on_resize(self, event):
        """Handle window resize."""
        if event.widget == self.root:
            # Keep it square
            size = max(event.width, event.height)
            if event.width != event.height:
                self.root.geometry(f"{size}x{size}")
            
            self.config['size'] = size
            self._draw_circle()
    
    def _save_and_close(self):
        """Save position and close."""
        if self.root:
            self.config['x'] = self.root.winfo_x()
            self.config['y'] = self.root.winfo_y()
            self.config['size'] = self.root.winfo_width()
        
        self._save_config()
        
        # Calculate circle center in screen coordinates
        center_x, center_y, diameter = self.get_circle_position()
        
        print(f"Saved: Center ({center_x}, {center_y}), Diameter {diameter}px")
        
        if self.on_save_callback:
            self.on_save_callback(center_x, center_y, diameter)
        
        self.close()
    
    def close(self):
        """Close the window without saving."""
        self.is_open = False
        if self.root:
            self.root.destroy()
            self.root = None
            self.canvas = None
    
    def get_circle_position(self) -> Tuple[int, int, int]:
        """Get the current circle position in screen coordinates.
        
        Returns:
            Tuple of (center_x, center_y, diameter) in screen pixels.
        """
        x = self.config['x']
        y = self.config['y']
        size = self.config['size']
        
        padding = 10
        diameter = size - (padding * 2)
        
        center_x = x + size // 2
        center_y = y + size // 2
        
        return (center_x, center_y, diameter)
    
    def get_signature_region(self) -> Tuple[int, int, int, int]:
        """Calculate the signature scan region based on circle position.
        
        Returns:
            Tuple of (x1, y1, x2, y2) defining the scan rectangle.
        """
        center_x, center_y, diameter = self.get_circle_position()
        
        # Signature offset (relative to circle center)
        offset_x = int(diameter * self.config['offset_x'])
        offset_y = int(diameter * self.config['offset_y'])
        
        # Signature center
        sig_x = center_x + offset_x
        sig_y = center_y + offset_y
        
        # Scan region padding
        padding = int(diameter * self.config['scan_padding'])
        
        x1 = sig_x - padding
        y1 = sig_y - padding
        x2 = sig_x + padding
        y2 = sig_y + padding
        
        return (x1, y1, x2, y2)
    
    def is_configured(self) -> bool:
        """Check if the identifier has been configured (saved at least once)."""
        return self.CONFIG_FILE.exists()

