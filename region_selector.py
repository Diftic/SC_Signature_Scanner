#!/usr/bin/env python3
"""
Region Selector for SC Signature Scanner.
GUI tool for defining the signature scan region on a screenshot.
"""

import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
from typing import Optional, Tuple, Callable
from PIL import Image, ImageTk
import json


CONFIG_FILE = Path(__file__).parent / "scan_region.json"


def load_region() -> Optional[Tuple[int, int, int, int]]:
    """Load saved scan region.
    
    Returns:
        Tuple of (x1, y1, x2, y2) or None if not configured.
    """
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                data = json.load(f)
                return (
                    data['x1'],
                    data['y1'],
                    data['x2'],
                    data['y2']
                )
        except (json.JSONDecodeError, KeyError, IOError):
            pass
    return None


def save_region(x1: int, y1: int, x2: int, y2: int):
    """Save scan region to config."""
    data = {
        'x1': x1,
        'y1': y1,
        'x2': x2,
        'y2': y2,
        'width': x2 - x1,
        'height': y2 - y1
    }
    with open(CONFIG_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def clear_region():
    """Clear saved scan region."""
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()


def is_configured() -> bool:
    """Check if a scan region has been configured."""
    return CONFIG_FILE.exists()


class RegionSelector:
    """GUI for selecting scan region on a screenshot."""
    
    def __init__(self, parent: Optional[tk.Tk] = None, on_save: Optional[Callable] = None):
        """Initialize the region selector.
        
        Args:
            parent: Parent window (if None, creates standalone window)
            on_save: Callback when region is saved, receives (x1, y1, x2, y2)
        """
        self.on_save = on_save
        self.parent = parent
        
        # Image state
        self.original_image: Optional[Image.Image] = None
        self.display_image: Optional[ImageTk.PhotoImage] = None
        self.scale_factor = 1.0
        
        # Selection state
        self.start_x = 0
        self.start_y = 0
        self.rect_id = None
        self.selection: Optional[Tuple[int, int, int, int]] = None  # In original image coords
        
        self.root: Optional[tk.Toplevel] = None
        self.canvas: Optional[tk.Canvas] = None
    
    def open(self, image_path: Optional[Path] = None):
        """Open the region selector.
        
        Args:
            image_path: Path to screenshot. If None, prompts user to select.
        """
        # Get image path
        if image_path is None:
            image_path = filedialog.askopenfilename(
                title="Select Screenshot",
                filetypes=[
                    ("Image files", "*.png *.jpg *.jpeg"),
                    ("PNG files", "*.png"),
                    ("JPEG files", "*.jpg *.jpeg"),
                ]
            )
            if not image_path:
                return
            image_path = Path(image_path)
        
        # Load image
        try:
            self.original_image = Image.open(image_path)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load image:\n{e}")
            return
        
        # Create window
        if self.parent:
            self.root = tk.Toplevel(self.parent)
        else:
            self.root = tk.Tk()
        
        self.root.title("Define Scan Region")
        self.root.configure(bg='#1a1a2e')
        
        # Calculate display size (fit to screen with margin)
        screen_w = self.root.winfo_screenwidth() - 100
        screen_h = self.root.winfo_screenheight() - 200
        
        img_w, img_h = self.original_image.size
        
        # Scale to fit
        scale_w = screen_w / img_w
        scale_h = screen_h / img_h
        self.scale_factor = min(scale_w, scale_h, 1.0)  # Don't upscale
        
        display_w = int(img_w * self.scale_factor)
        display_h = int(img_h * self.scale_factor)
        
        # Instructions
        instructions = tk.Label(
            self.root,
            text="Click and drag to define the scan region around where signatures appear",
            bg='#1a1a2e',
            fg='#f4a259',
            font=('Segoe UI', 10)
        )
        instructions.pack(pady=(10, 5))
        
        # Canvas for image
        self.canvas = tk.Canvas(
            self.root,
            width=display_w,
            height=display_h,
            bg='#0d0d1a',
            highlightthickness=1,
            highlightbackground='#333'
        )
        self.canvas.pack(padx=10, pady=5)
        
        # Display scaled image
        display_img = self.original_image.resize((display_w, display_h), Image.Resampling.LANCZOS)
        self.display_image = ImageTk.PhotoImage(display_img)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.display_image)
        
        # Load existing region if any
        existing = load_region()
        if existing:
            x1, y1, x2, y2 = existing
            self.selection = existing
            self._draw_rect(
                int(x1 * self.scale_factor),
                int(y1 * self.scale_factor),
                int(x2 * self.scale_factor),
                int(y2 * self.scale_factor)
            )
        
        # Bindings
        self.canvas.bind('<Button-1>', self._on_press)
        self.canvas.bind('<B1-Motion>', self._on_drag)
        self.canvas.bind('<ButtonRelease-1>', self._on_release)
        
        # Info label
        self.info_label = tk.Label(
            self.root,
            text="No region selected",
            bg='#1a1a2e',
            fg='#888',
            font=('Consolas', 9)
        )
        self.info_label.pack(pady=5)
        
        if existing:
            self._update_info()
        
        # Buttons
        btn_frame = tk.Frame(self.root, bg='#1a1a2e')
        btn_frame.pack(pady=10)
        
        save_btn = tk.Button(
            btn_frame,
            text="✓ Save Region",
            bg='#4ecca3',
            fg='#1a1a2e',
            font=('Segoe UI', 10, 'bold'),
            relief='flat',
            padx=20,
            pady=8,
            cursor='hand2',
            command=self._save
        )
        save_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        clear_btn = tk.Button(
            btn_frame,
            text="✕ Clear",
            bg='#444',
            fg='#fff',
            font=('Segoe UI', 10),
            relief='flat',
            padx=20,
            pady=8,
            cursor='hand2',
            command=self._clear
        )
        clear_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        cancel_btn = tk.Button(
            btn_frame,
            text="Cancel",
            bg='#333',
            fg='#aaa',
            font=('Segoe UI', 10),
            relief='flat',
            padx=20,
            pady=8,
            cursor='hand2',
            command=self._cancel
        )
        cancel_btn.pack(side=tk.LEFT)
        
        # Center window
        self.root.update_idletasks()
        win_w = self.root.winfo_width()
        win_h = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() - win_w) // 2
        y = (self.root.winfo_screenheight() - win_h) // 2
        self.root.geometry(f"+{x}+{y}")
        
        # Make modal if has parent
        if self.parent:
            self.root.transient(self.parent)
            self.root.grab_set()
        
        self.root.mainloop()
    
    def _on_press(self, event):
        """Handle mouse press - start drawing rectangle."""
        self.start_x = event.x
        self.start_y = event.y
        
        # Remove existing rectangle
        if self.rect_id:
            self.canvas.delete(self.rect_id)
            self.rect_id = None
    
    def _on_drag(self, event):
        """Handle mouse drag - update rectangle."""
        # Get current position
        x1 = min(self.start_x, event.x)
        y1 = min(self.start_y, event.y)
        x2 = max(self.start_x, event.x)
        y2 = max(self.start_y, event.y)
        
        # Clamp to canvas bounds
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(canvas_w, x2)
        y2 = min(canvas_h, y2)
        
        # Draw rectangle
        self._draw_rect(x1, y1, x2, y2)
        
        # Store selection in original image coordinates
        self.selection = (
            int(x1 / self.scale_factor),
            int(y1 / self.scale_factor),
            int(x2 / self.scale_factor),
            int(y2 / self.scale_factor)
        )
        
        self._update_info()
    
    def _on_release(self, event):
        """Handle mouse release."""
        pass
    
    def _draw_rect(self, x1: int, y1: int, x2: int, y2: int):
        """Draw selection rectangle."""
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        
        self.rect_id = self.canvas.create_rectangle(
            x1, y1, x2, y2,
            outline='#4ecca3',
            width=2,
            dash=(5, 3)
        )
    
    def _update_info(self):
        """Update info label with current selection."""
        if self.selection:
            x1, y1, x2, y2 = self.selection
            w = x2 - x1
            h = y2 - y1
            self.info_label.configure(
                text=f"Region: ({x1}, {y1}) to ({x2}, {y2}) • Size: {w} × {h} px",
                fg='#4ecca3'
            )
        else:
            self.info_label.configure(
                text="No region selected",
                fg='#888'
            )
    
    def _save(self):
        """Save the selected region."""
        if not self.selection:
            messagebox.showwarning("No Selection", "Please draw a region first.")
            return
        
        x1, y1, x2, y2 = self.selection
        
        # Validate minimum size
        if (x2 - x1) < 20 or (y2 - y1) < 5:
            messagebox.showwarning("Region Too Small", "Please select a larger region.")
            return
        
        save_region(x1, y1, x2, y2)
        
        if self.on_save:
            self.on_save(x1, y1, x2, y2)
        
        messagebox.showinfo("Saved", f"Scan region saved:\n({x1}, {y1}) to ({x2}, {y2})")
        self._close()
    
    def _clear(self):
        """Clear the selection."""
        if self.rect_id:
            self.canvas.delete(self.rect_id)
            self.rect_id = None
        self.selection = None
        self._update_info()
    
    def _cancel(self):
        """Cancel and close."""
        self._close()
    
    def _close(self):
        """Close the window."""
        if self.root:
            self.root.destroy()
            self.root = None

