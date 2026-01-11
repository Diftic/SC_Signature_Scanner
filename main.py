#!/usr/bin/env python3
"""
SC Signature Scanner
====================
Monitor Star Citizen screenshots for signature values and identify targets.

Features:
- Monitors screenshot folder for new images
- OCR detection of signature values
- Identifies ships, asteroids, deposits from signature
- Overlay popup with match results
"""

import json
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
import sys

# Local imports
from scanner import SignatureScanner
from overlay import OverlayPopup, PositionAdjuster
from monitor import ScreenshotMonitor
from config import Config
from theme import RegolithTheme, WarningBanner, StatusIndicator
import pricing
import version_checker


class SCSignatureScannerApp:
    """Main application class."""
    
    VERSION = version_checker.CURRENT_VERSION
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"SC Signature Scanner")
        self.root.resizable(False, False)
        
        # Apply theme
        RegolithTheme.apply(self.root)
        
        # Center window on screen
        window_width = 520
        window_height = 1000
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # Configuration
        self.config = Config()
        
        # Components
        self.scanner: Optional[SignatureScanner] = None
        self.monitor: Optional[ScreenshotMonitor] = None
        self.overlay: Optional[OverlayPopup] = None
        
        # State
        self.is_monitoring = False
        self.processed_files = set()
        self.overlay_position: Optional[Tuple[int, int]] = None
        self.screenshot_count = 0
        
        # Build UI
        self._create_ui()
        
        # Initialize scanner with signature database
        self._init_scanner()
        
        # Load config (after scanner exists so debug mode can be applied)
        self._load_config()
        
        # Initialize pricing system
        self._init_pricing()
        
        # Check for updates (background)
        self._check_for_updates()
    
    def _create_ui(self):
        """Create the main UI."""
        colors = RegolithTheme.COLORS
        fonts = RegolithTheme.FONTS
        
        # Main container
        main_container = tk.Frame(self.root, bg=colors['bg_main'])
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # === Header ===
        header = tk.Frame(main_container, bg=colors['bg_dark'], pady=15)
        header.pack(fill=tk.X)
        
        # Title with icon
        title_frame = tk.Frame(header, bg=colors['bg_dark'])
        title_frame.pack()
        
        title_icon = tk.Label(
            title_frame,
            text="📡",
            bg=colors['bg_dark'],
            font=('Segoe UI', 24)
        )
        title_icon.pack(side=tk.LEFT, padx=(0, 10))
        
        title_text = tk.Frame(title_frame, bg=colors['bg_dark'])
        title_text.pack(side=tk.LEFT)
        
        title = tk.Label(
            title_text,
            text="SIGNATURE SCANNER",
            bg=colors['bg_dark'],
            fg=colors['accent_primary'],
            font=('Segoe UI', 18, 'bold')
        )
        title.pack(anchor=tk.W)
        
        subtitle = tk.Label(
            title_text,
            text=f"Star Citizen Target Identification • v{self.VERSION}",
            bg=colors['bg_dark'],
            fg=colors['text_muted'],
            font=fonts['small']
        )
        subtitle.pack(anchor=tk.W)
        
        # Accent line
        accent_line = tk.Frame(header, bg=colors['accent_primary'], height=2)
        accent_line.pack(fill=tk.X, pady=(15, 0))
        
        # Warning banner
        warning = WarningBanner(main_container, "Requires Windowed or Borderless Windowed mode")
        warning.pack(fill=tk.X, padx=15, pady=15)
        
        # === Notebook (Tabs) ===
        notebook = ttk.Notebook(main_container)
        notebook.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))
        
        # === Scanner Tab ===
        scanner_tab = tk.Frame(notebook, bg=colors['bg_main'])
        notebook.add(scanner_tab, text="  Scanner  ")
        
        scanner_content = tk.Frame(scanner_tab, bg=colors['bg_main'], padx=5, pady=15)
        scanner_content.pack(fill=tk.BOTH, expand=True)
        
        # Screenshot folder section
        folder_section = tk.Frame(scanner_content, bg=colors['bg_main'])
        folder_section.pack(fill=tk.X, pady=(0, 15))
        
        folder_label = tk.Label(
            folder_section,
            text="SCREENSHOT FOLDER",
            bg=colors['bg_main'],
            fg=colors['accent_primary'],
            font=fonts['subheading']
        )
        folder_label.pack(anchor=tk.W, pady=(0, 8))
        
        folder_input = tk.Frame(folder_section, bg=colors['border'])
        folder_input.pack(fill=tk.X)
        
        folder_inner = tk.Frame(folder_input, bg=colors['bg_dark'], padx=2, pady=2)
        folder_inner.pack(fill=tk.X, padx=1, pady=1)
        
        self.folder_var = tk.StringVar()
        folder_entry = tk.Entry(
            folder_inner,
            textvariable=self.folder_var,
            bg=colors['bg_dark'],
            fg=colors['text_primary'],
            font=fonts['mono_small'],
            relief='flat',
            insertbackground=colors['accent_primary']
        )
        folder_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8, pady=8)
        
        browse_btn = tk.Button(
            folder_inner,
            text="Browse",
            bg=colors['bg_light'],
            fg=colors['text_primary'],
            font=fonts['body'],
            relief='flat',
            padx=15,
            pady=4,
            cursor='hand2',
            command=self._browse_folder
        )
        browse_btn.pack(side=tk.RIGHT, padx=(0, 4), pady=4)
        
        # Status section
        status_section = tk.Frame(scanner_content, bg=colors['bg_light'])
        status_section.pack(fill=tk.X, pady=(0, 15))
        
        # Add border effect
        status_border = tk.Frame(scanner_content, bg=colors['border'])
        status_border.pack(fill=tk.X, pady=(0, 15), before=status_section)
        status_section.pack_forget()
        
        status_inner = tk.Frame(status_border, bg=colors['bg_light'], padx=15, pady=12)
        status_inner.pack(fill=tk.X, padx=1, pady=1)
        
        status_header = tk.Frame(status_inner, bg=colors['bg_light'])
        status_header.pack(fill=tk.X)
        
        self.status_indicator = StatusIndicator(status_inner)
        self.status_indicator.configure(bg=colors['bg_light'])
        self.status_indicator.icon.configure(bg=colors['bg_light'])
        self.status_indicator.label.configure(bg=colors['bg_light'])
        self.status_indicator.pack(side=tk.LEFT)
        
        self.stats_label = tk.Label(
            status_inner,
            text="0 screenshots processed",
            bg=colors['bg_light'],
            fg=colors['text_muted'],
            font=fonts['small']
        )
        self.stats_label.pack(side=tk.RIGHT)
        
        # Control buttons
        btn_frame = tk.Frame(scanner_content, bg=colors['bg_main'])
        btn_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.start_btn = tk.Button(
            btn_frame,
            text="▶  START MONITORING",
            bg=colors['accent_primary'],
            fg=colors['bg_dark'],
            font=('Segoe UI', 11, 'bold'),
            relief='flat',
            padx=20,
            pady=10,
            cursor='hand2',
            command=self._toggle_monitoring
        )
        self.start_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        test_btn = tk.Button(
            btn_frame,
            text="🧪  Test Screenshot",
            bg=colors['bg_light'],
            fg=colors['text_primary'],
            font=fonts['body'],
            relief='flat',
            padx=15,
            pady=10,
            cursor='hand2',
            command=self._test_screenshot
        )
        test_btn.pack(side=tk.LEFT)
        
        # Log section
        log_label = tk.Label(
            scanner_content,
            text="DETECTION LOG",
            bg=colors['bg_main'],
            fg=colors['accent_primary'],
            font=fonts['subheading']
        )
        log_label.pack(anchor=tk.W, pady=(0, 8))
        
        log_border = tk.Frame(scanner_content, bg=colors['border'])
        log_border.pack(fill=tk.BOTH, expand=True)
        
        log_inner = tk.Frame(log_border, bg=colors['bg_dark'])
        log_inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        
        self.log_text = tk.Text(
            log_inner,
            bg=colors['bg_dark'],
            fg=colors['text_secondary'],
            font=fonts['mono_small'],
            relief='flat',
            padx=10,
            pady=10,
            height=10,
            state=tk.DISABLED,
            insertbackground=colors['accent_primary'],
            selectbackground=colors['accent_primary'],
            selectforeground=colors['bg_dark']
        )
        
        log_scroll = tk.Scrollbar(
            log_inner,
            orient=tk.VERTICAL,
            command=self.log_text.yview,
            bg=colors['bg_light'],
            troughcolor=colors['bg_dark'],
            width=12
        )
        
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # === Settings Tab ===
        settings_tab = tk.Frame(notebook, bg=colors['bg_main'])
        notebook.add(settings_tab, text="  Settings  ")
        
        settings_content = tk.Frame(settings_tab, bg=colors['bg_main'], padx=5, pady=10)
        settings_content.pack(fill=tk.BOTH, expand=True)
        
        # Popup Position section
        pos_label = tk.Label(
            settings_content,
            text="POPUP POSITION",
            bg=colors['bg_main'],
            fg=colors['accent_primary'],
            font=fonts['subheading']
        )
        pos_label.pack(anchor=tk.W, pady=(0, 5))
        
        pos_border = tk.Frame(settings_content, bg=colors['border'])
        pos_border.pack(fill=tk.X, pady=(0, 10))
        
        pos_inner = tk.Frame(pos_border, bg=colors['bg_light'], padx=15, pady=10)
        pos_inner.pack(fill=tk.X, padx=1, pady=1)
        
        pos_row = tk.Frame(pos_inner, bg=colors['bg_light'])
        pos_row.pack(fill=tk.X)
        
        pos_text = tk.Label(
            pos_row,
            text="Current:",
            bg=colors['bg_light'],
            fg=colors['text_secondary'],
            font=fonts['body']
        )
        pos_text.pack(side=tk.LEFT)
        
        self.position_label = tk.Label(
            pos_row,
            text="Not set (centered)",
            bg=colors['bg_light'],
            fg=colors['text_muted'],
            font=fonts['mono']
        )
        self.position_label.pack(side=tk.LEFT, padx=(8, 0))
        
        pos_btn_frame = tk.Frame(pos_inner, bg=colors['bg_light'])
        pos_btn_frame.pack(fill=tk.X, pady=(8, 0))
        
        adjust_btn = tk.Button(
            pos_btn_frame,
            text="📍  Adjust Position",
            bg=colors['cyan'],
            fg=colors['bg_dark'],
            font=('Segoe UI', 10, 'bold'),
            relief='flat',
            padx=15,
            pady=6,
            cursor='hand2',
            command=self._adjust_position
        )
        adjust_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        reset_btn = tk.Button(
            pos_btn_frame,
            text="↺  Reset",
            bg=colors['bg_hover'],
            fg=colors['text_primary'],
            font=fonts['body'],
            relief='flat',
            padx=15,
            pady=6,
            cursor='hand2',
            command=self._reset_position
        )
        reset_btn.pack(side=tk.LEFT)
        
        # Duration & Max Results on same row
        dur_max_label = tk.Label(
            settings_content,
            text="POPUP OPTIONS",
            bg=colors['bg_main'],
            fg=colors['accent_primary'],
            font=fonts['subheading']
        )
        dur_max_label.pack(anchor=tk.W, pady=(8, 5))
        
        dur_max_border = tk.Frame(settings_content, bg=colors['border'])
        dur_max_border.pack(fill=tk.X, pady=(0, 10))
        
        dur_max_inner = tk.Frame(dur_max_border, bg=colors['bg_light'], padx=15, pady=10)
        dur_max_inner.pack(fill=tk.X, padx=1, pady=1)
        
        dur_max_row = tk.Frame(dur_max_inner, bg=colors['bg_light'])
        dur_max_row.pack(fill=tk.X)
        
        # Duration
        self.duration_var = tk.IntVar(value=10)
        dur_spin = tk.Spinbox(
            dur_max_row,
            from_=1,
            to=30,
            textvariable=self.duration_var,
            width=4,
            bg=colors['bg_dark'],
            fg=colors['text_primary'],
            font=fonts['mono'],
            relief='flat',
            buttonbackground=colors['bg_light']
        )
        dur_spin.pack(side=tk.LEFT)
        
        dur_text = tk.Label(
            dur_max_row,
            text="sec duration",
            bg=colors['bg_light'],
            fg=colors['text_secondary'],
            font=fonts['body']
        )
        dur_text.pack(side=tk.LEFT, padx=(5, 0))
        
        # Popup Scale section
        scale_label = tk.Label(
            settings_content,
            text="POPUP SCALE",
            bg=colors['bg_main'],
            fg=colors['accent_primary'],
            font=fonts['subheading']
        )
        scale_label.pack(anchor=tk.W, pady=(8, 5))
        
        scale_border = tk.Frame(settings_content, bg=colors['border'])
        scale_border.pack(fill=tk.X, pady=(0, 10))
        
        scale_inner = tk.Frame(scale_border, bg=colors['bg_light'], padx=15, pady=10)
        scale_inner.pack(fill=tk.X, padx=1, pady=1)
        
        scale_row = tk.Frame(scale_inner, bg=colors['bg_light'])
        scale_row.pack(fill=tk.X)
        
        self.scale_var = tk.DoubleVar(value=1.0)
        
        scale_label_val = tk.Label(
            scale_row,
            text="50%",
            bg=colors['bg_light'],
            fg=colors['text_muted'],
            font=fonts['small'],
            width=4
        )
        scale_label_val.pack(side=tk.LEFT)
        
        def update_scale_label(val):
            self.scale_display.configure(text=f"{float(val):.0%}")
        
        scale_slider = tk.Scale(
            scale_row,
            from_=0.5,
            to=2.0,
            resolution=0.1,
            orient=tk.HORIZONTAL,
            variable=self.scale_var,
            bg=colors['bg_light'],
            fg=colors['text_primary'],
            highlightthickness=0,
            troughcolor=colors['bg_dark'],
            activebackground=colors['accent_primary'],
            length=200,
            showvalue=False,
            command=update_scale_label
        )
        scale_slider.pack(side=tk.LEFT, padx=(5, 5))
        
        scale_label_max = tk.Label(
            scale_row,
            text="200%",
            bg=colors['bg_light'],
            fg=colors['text_muted'],
            font=fonts['small'],
            width=4
        )
        scale_label_max.pack(side=tk.LEFT)
        
        self.scale_display = tk.Label(
            scale_row,
            text="100%",
            bg=colors['bg_light'],
            fg=colors['cyan'],
            font=fonts['mono']
        )
        self.scale_display.pack(side=tk.LEFT, padx=(15, 0))
        
        # Refinery Yield section
        yield_label = tk.Label(
            settings_content,
            text="REFINERY YIELD",
            bg=colors['bg_main'],
            fg=colors['accent_primary'],
            font=fonts['subheading']
        )
        yield_label.pack(anchor=tk.W, pady=(8, 5))
        
        yield_border = tk.Frame(settings_content, bg=colors['border'])
        yield_border.pack(fill=tk.X, pady=(0, 10))
        
        yield_inner = tk.Frame(yield_border, bg=colors['bg_light'], padx=15, pady=10)
        yield_inner.pack(fill=tk.X, padx=1, pady=1)
        
        yield_desc = tk.Label(
            yield_inner,
            text="Volume conversion factor for refined material (game may adjust this)",
            bg=colors['bg_light'],
            fg=colors['text_muted'],
            font=fonts['small']
        )
        yield_desc.pack(anchor=tk.W, pady=(0, 5))
        
        yield_row = tk.Frame(yield_inner, bg=colors['bg_light'])
        yield_row.pack(fill=tk.X)
        
        self.yield_var = tk.DoubleVar(value=0.5)
        
        yield_label_min = tk.Label(
            yield_row,
            text="0%",
            bg=colors['bg_light'],
            fg=colors['text_muted'],
            font=fonts['small'],
            width=4
        )
        yield_label_min.pack(side=tk.LEFT)
        
        def update_yield_label(val):
            pct = int(float(val) * 100)
            self.yield_display.configure(text=f"{pct}%")
        
        yield_slider = tk.Scale(
            yield_row,
            from_=0.0,
            to=1.0,
            resolution=0.05,
            orient=tk.HORIZONTAL,
            variable=self.yield_var,
            bg=colors['bg_light'],
            fg=colors['text_primary'],
            highlightthickness=0,
            troughcolor=colors['bg_dark'],
            activebackground=colors['accent_primary'],
            length=200,
            showvalue=False,
            command=update_yield_label
        )
        yield_slider.pack(side=tk.LEFT, padx=(5, 5))
        
        yield_label_max = tk.Label(
            yield_row,
            text="100%",
            bg=colors['bg_light'],
            fg=colors['text_muted'],
            font=fonts['small'],
            width=5
        )
        yield_label_max.pack(side=tk.LEFT)
        
        self.yield_display = tk.Label(
            yield_row,
            text="50%",
            bg=colors['bg_light'],
            fg=colors['cyan'],
            font=fonts['mono']
        )
        self.yield_display.pack(side=tk.LEFT, padx=(15, 0))
        
        # Pricing section
        pricing_label = tk.Label(
            settings_content,
            text="PRICING DATA",
            bg=colors['bg_main'],
            fg=colors['accent_primary'],
            font=fonts['subheading']
        )
        pricing_label.pack(anchor=tk.W, pady=(8, 5))
        
        pricing_border = tk.Frame(settings_content, bg=colors['border'])
        pricing_border.pack(fill=tk.X, pady=(0, 10))
        
        pricing_inner = tk.Frame(pricing_border, bg=colors['bg_light'], padx=15, pady=10)
        pricing_inner.pack(fill=tk.X, padx=1, pady=1)
        
        pricing_row = tk.Frame(pricing_inner, bg=colors['bg_light'])
        pricing_row.pack(fill=tk.X)
        
        pricing_status_text = tk.Label(
            pricing_row,
            text="Status:",
            bg=colors['bg_light'],
            fg=colors['text_secondary'],
            font=fonts['body']
        )
        pricing_status_text.pack(side=tk.LEFT)
        
        self.pricing_status_label = tk.Label(
            pricing_row,
            text="Not loaded",
            bg=colors['bg_light'],
            fg=colors['text_muted'],
            font=fonts['mono']
        )
        self.pricing_status_label.pack(side=tk.LEFT, padx=(8, 20))
        
        refresh_pricing_btn = tk.Button(
            pricing_row,
            text="🔄  Refresh",
            bg=colors['cyan'],
            fg=colors['bg_dark'],
            font=('Segoe UI', 9, 'bold'),
            relief='flat',
            padx=10,
            pady=4,
            cursor='hand2',
            command=self._refresh_pricing
        )
        refresh_pricing_btn.pack(side=tk.LEFT)
        
        # Debug Mode section
        debug_label = tk.Label(
            settings_content,
            text="DEBUG MODE",
            bg=colors['bg_main'],
            fg=colors['accent_primary'],
            font=fonts['subheading']
        )
        debug_label.pack(anchor=tk.W, pady=(8, 5))
        
        debug_border = tk.Frame(settings_content, bg=colors['border'])
        debug_border.pack(fill=tk.X, pady=(0, 10))
        
        debug_inner = tk.Frame(debug_border, bg=colors['bg_light'], padx=15, pady=10)
        debug_inner.pack(fill=tk.X, padx=1, pady=1)
        
        debug_row = tk.Frame(debug_inner, bg=colors['bg_light'])
        debug_row.pack(fill=tk.X)
        
        self.debug_var = tk.BooleanVar(value=False)
        debug_check = tk.Checkbutton(
            debug_row,
            text="Enable debug output",
            variable=self.debug_var,
            bg=colors['bg_light'],
            fg=colors['text_primary'],
            font=fonts['body'],
            selectcolor=colors['bg_dark'],
            activebackground=colors['bg_light'],
            activeforeground=colors['text_primary'],
            command=self._toggle_debug
        )
        debug_check.pack(side=tk.LEFT)
        
        open_debug_btn = tk.Button(
            debug_row,
            text="📂  Open Folder",
            bg=colors['bg_hover'],
            fg=colors['text_primary'],
            font=fonts['body'],
            relief='flat',
            padx=10,
            pady=4,
            cursor='hand2',
            command=self._open_debug_folder
        )
        open_debug_btn.pack(side=tk.RIGHT)
        
        debug_desc = tk.Label(
            debug_inner,
            text="Saves intermediate images to debug_output/ for troubleshooting OCR",
            bg=colors['bg_light'],
            fg=colors['text_muted'],
            font=fonts['small']
        )
        debug_desc.pack(anchor=tk.W, pady=(5, 0))
        
        # Action buttons
        action_frame = tk.Frame(settings_content, bg=colors['bg_main'])
        action_frame.pack(fill=tk.X, pady=(15, 0))
        
        test_popup_btn = tk.Button(
            action_frame,
            text="🔔  Test Popup",
            bg=colors['bg_light'],
            fg=colors['text_primary'],
            font=fonts['body'],
            relief='flat',
            padx=15,
            pady=6,
            cursor='hand2',
            command=self._test_popup
        )
        test_popup_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        save_btn = tk.Button(
            action_frame,
            text="💾  Save Settings",
            bg=colors['success'],
            fg=colors['bg_dark'],
            font=('Segoe UI', 10, 'bold'),
            relief='flat',
            padx=15,
            pady=6,
            cursor='hand2',
            command=self._save_config
        )
        save_btn.pack(side=tk.LEFT)
        
        # === About Tab ===
        about_tab = tk.Frame(notebook, bg=colors['bg_main'])
        notebook.add(about_tab, text="  About  ")
        
        about_content = tk.Frame(about_tab, bg=colors['bg_main'], padx=5, pady=15)
        about_content.pack(fill=tk.BOTH, expand=True)
        
        # Logo/Title
        about_header = tk.Frame(about_content, bg=colors['bg_main'])
        about_header.pack(fill=tk.X, pady=(0, 20))
        
        about_title = tk.Label(
            about_header,
            text="📡 SC SIGNATURE SCANNER",
            bg=colors['bg_main'],
            fg=colors['accent_primary'],
            font=('Segoe UI', 16, 'bold')
        )
        about_title.pack()
        
        about_ver = tk.Label(
            about_header,
            text=f"Version {self.VERSION}",
            bg=colors['bg_main'],
            fg=colors['text_muted'],
            font=fonts['small']
        )
        about_ver.pack()
        
        # Description
        desc_text = """Monitors Star Citizen screenshots for signature values
and identifies potential targets in real-time.

Contributed to Regolith.Rocks"""
        
        desc_label = tk.Label(
            about_content,
            text=desc_text,
            bg=colors['bg_main'],
            fg=colors['text_secondary'],
            font=fonts['body'],
            justify=tk.CENTER
        )
        desc_label.pack(pady=(0, 20))
        
        # How to use
        howto_label = tk.Label(
            about_content,
            text="HOW TO USE",
            bg=colors['bg_main'],
            fg=colors['accent_primary'],
            font=fonts['subheading']
        )
        howto_label.pack(anchor=tk.W, pady=(0, 8))
        
        howto_border = tk.Frame(about_content, bg=colors['border'])
        howto_border.pack(fill=tk.X, pady=(0, 15))
        
        howto_inner = tk.Frame(howto_border, bg=colors['bg_light'], padx=15, pady=12)
        howto_inner.pack(fill=tk.X, padx=1, pady=1)
        
        steps = [
            ("1.", "Set Star Citizen to Windowed or Borderless"),
            ("2.", "Select your screenshot folder"),
            ("3.", "Click Start Monitoring"),
            ("4.", "In-game: Press PrintScreen on signature"),
            ("5.", "Overlay shows identification results"),
        ]
        
        for num, text in steps:
            step_row = tk.Frame(howto_inner, bg=colors['bg_light'])
            step_row.pack(fill=tk.X, pady=2)
            
            num_label = tk.Label(
                step_row,
                text=num,
                bg=colors['bg_light'],
                fg=colors['accent_primary'],
                font=fonts['mono'],
                width=3
            )
            num_label.pack(side=tk.LEFT)
            
            text_label = tk.Label(
                step_row,
                text=text,
                bg=colors['bg_light'],
                fg=colors['text_primary'],
                font=fonts['body'],
                anchor=tk.W
            )
            text_label.pack(side=tk.LEFT, fill=tk.X)
        
        # Signature types
        sig_label = tk.Label(
            about_content,
            text="SIGNATURE TYPES",
            bg=colors['bg_main'],
            fg=colors['accent_primary'],
            font=fonts['subheading']
        )
        sig_label.pack(anchor=tk.W, pady=(10, 8))
        
        sig_border = tk.Frame(about_content, bg=colors['border'])
        sig_border.pack(fill=tk.X)
        
        sig_inner = tk.Frame(sig_border, bg=colors['bg_light'], padx=15, pady=12)
        sig_inner.pack(fill=tk.X, padx=1, pady=1)
        
        sig_types = [
            ("🚀", "Ships", "Radar cross-section"),
            ("🪨", "Asteroids", "I, C, S, P, M, Q, E types"),
            ("⛏️", "Deposits", "Surface mining rocks"),
            ("🔧", "Salvage", "2000 per hull panel"),
        ]
        
        for icon, name, desc in sig_types:
            sig_row = tk.Frame(sig_inner, bg=colors['bg_light'])
            sig_row.pack(fill=tk.X, pady=2)
            
            icon_label = tk.Label(
                sig_row,
                text=icon,
                bg=colors['bg_light'],
                font=('Segoe UI', 11),
                width=3
            )
            icon_label.pack(side=tk.LEFT)
            
            name_label = tk.Label(
                sig_row,
                text=name,
                bg=colors['bg_light'],
                fg=colors['text_primary'],
                font=('Segoe UI', 10, 'bold'),
                width=10,
                anchor=tk.W
            )
            name_label.pack(side=tk.LEFT)
            
            desc_label = tk.Label(
                sig_row,
                text=desc,
                bg=colors['bg_light'],
                fg=colors['text_muted'],
                font=fonts['small'],
                anchor=tk.W
            )
            desc_label.pack(side=tk.LEFT, fill=tk.X)
    
    def _browse_folder(self):
        """Open folder browser dialog."""
        folder = filedialog.askdirectory(title="Select Star Citizen Screenshots Folder")
        if folder:
            self.folder_var.set(folder)
            self._log(f"📁 Screenshot folder: {folder}")
            self._save_config(show_message=False)  # Auto-save folder selection
    
    def _toggle_monitoring(self):
        """Start or stop monitoring."""
        if self.is_monitoring:
            self._stop_monitoring()
        else:
            self._start_monitoring()
    
    def _start_monitoring(self):
        """Start monitoring the screenshot folder."""
        folder = self.folder_var.get()
        if not folder or not Path(folder).exists():
            messagebox.showerror("Error", "Please select a valid screenshot folder")
            return
        
        # Mark existing files to ignore
        self.processed_files = set(Path(folder).glob("*.png"))
        self.processed_files.update(Path(folder).glob("*.jpg"))
        self.processed_files.update(Path(folder).glob("*.jpeg"))
        self.processed_files.update(Path(folder).glob("*.jxr"))
        self.processed_files.update(Path(folder).glob("*.hdp"))
        self.processed_files.update(Path(folder).glob("*.wdp"))
        self.screenshot_count = 0
        
        # Start monitor
        self.monitor = ScreenshotMonitor(
            folder=folder,
            callback=self._on_new_screenshot,
            ignore_existing=self.processed_files
        )
        self.monitor.start()
        
        # Create overlay
        self.overlay = OverlayPopup(
            position=self.overlay_position,
            duration=self.duration_var.get(),
            scale=self.scale_var.get()
        )
        
        self.is_monitoring = True
        self.status_indicator.set_active()
        self.start_btn.configure(
            text="⏹  STOP MONITORING",
            bg=RegolithTheme.COLORS['error']
        )
        self._log(f"▶ Started monitoring")
        self._log(f"  Ignoring {len(self.processed_files)} existing files")
    
    def _stop_monitoring(self):
        """Stop monitoring."""
        if self.monitor:
            self.monitor.stop()
            self.monitor = None
        
        if self.overlay:
            self.overlay.destroy()
            self.overlay = None
        
        self.is_monitoring = False
        self.status_indicator.set_inactive()
        self.start_btn.configure(
            text="▶  START MONITORING",
            bg=RegolithTheme.COLORS['accent_primary']
        )
        self._log("⏹ Stopped monitoring")
    
    def _on_new_screenshot(self, filepath: Path):
        """Handle new screenshot detected."""
        self._log(f"📸 New: {filepath.name}")
        
        # Scan for signature
        if self.scanner:
            result = self.scanner.scan_image(filepath)
            
            # Check for errors
            if result and result.get('error'):
                self._log(f"   ⚠ Error: {result['error']}")
                self.screenshot_count += 1
                self.stats_label.configure(text=f"{self.screenshot_count} screenshots processed")
                return
            
            if result and result.get('signature'):
                sig = result['signature']
                matches = result.get('matches', [])
                all_sigs = result.get('all_signatures', [])
                
                self._log(f"   Signature: {sig:,}")
                if len(all_sigs) > 1:
                    self._log(f"   All found: {all_sigs}")
                self._log(f"   Matches: {len(matches)}")
                
                # Show debug info
                if self.debug_var.get() and result.get('debug'):
                    debug = result['debug']
                    self._log(f"   [DEBUG] Regions: {debug.get('regions_checked', 0)}")
                    for ocr in debug.get('raw_ocr_text', []):
                        text_preview = ocr['text'][:50] + '...' if len(ocr['text']) > 50 else ocr['text']
                        self._log(f"   [DEBUG] OCR ({ocr['region']}): {text_preview}")
                
                # Show overlay
                if matches:
                    # Create temporary overlay if not monitoring
                    if not self.overlay:
                        self.overlay = OverlayPopup(
                            position=self.overlay_position,
                            duration=self.duration_var.get(),
                            scale=self.scale_var.get()
                        )
                    self.overlay.show(sig, matches)
            else:
                self._log("   No signature detected")
                
                # Show debug info even on failure
                if self.debug_var.get() and self.scanner.last_debug_info:
                    debug = self.scanner.last_debug_info
                    self._log(f"   [DEBUG] Regions checked: {debug.get('regions_checked', 0)}")
                    self._log(f"   [DEBUG] Check debug_output/ for images")
        
        # Update stats
        self.screenshot_count += 1
        self.stats_label.configure(text=f"{self.screenshot_count} screenshots processed")
    
    def _test_screenshot(self):
        """Test with a manually selected screenshot."""
        filepath = filedialog.askopenfilename(
            title="Select Screenshot to Test",
            filetypes=[
                ("All supported", "*.png *.jpg *.jpeg *.jxr *.hdp *.wdp"),
                ("PNG files", "*.png"),
                ("JPEG files", "*.jpg *.jpeg"),
                ("JPEG XR files", "*.jxr *.hdp *.wdp"),
            ]
        )
        if filepath:
            self._on_new_screenshot(Path(filepath))
    
    def _adjust_position(self):
        """Open position adjuster window."""
        def on_save(x: int, y: int):
            self.overlay_position = (x, y)
            self._update_position_label()
            self._log(f"📍 Position set: ({x}, {y})")
            self._save_config(show_message=False)  # Auto-save position
            
            # Update overlay if running
            if self.overlay:
                self.overlay.set_position(x, y)
        
        # Show adjuster (modal - blocks until closed)
        adjuster = PositionAdjuster(
            parent=self.root,
            current_position=self.overlay_position,
            on_save=on_save
        )
        adjuster.run()
    
    def _reset_position(self):
        """Reset position to centered."""
        self.overlay_position = None
        self._update_position_label()
        self._log("📍 Position reset to center")
        self._save_config(show_message=False)  # Auto-save position reset
        
        if self.overlay:
            self.overlay.position = None
    
    def _update_position_label(self):
        """Update the position display label."""
        if self.overlay_position:
            x, y = self.overlay_position
            self.position_label.configure(
                text=f"({x}, {y})",
                fg=RegolithTheme.COLORS['success']
            )
        else:
            self.position_label.configure(
                text="Not set (centered)",
                fg=RegolithTheme.COLORS['text_muted']
            )
    
    def _test_popup(self):
        """Show a test popup at current position."""
        # Clean up any existing test overlay
        if hasattr(self, '_test_overlay') and self._test_overlay:
            self._test_overlay.destroy()
        
        # Create temporary overlay (store as instance var so timer works)
        self._test_overlay = OverlayPopup(
            position=self.overlay_position,
            duration=self.duration_var.get(),
            scale=self.scale_var.get()
        )
        
        # Test data for E-type asteroid
        test_signature = 1900
        test_matches = [{
            'type': 'known',
            'name': 'E-type Asteroid',
            'category': 'asteroid',
            'rock_type': 'ETYPE',
            'signature': 1900,
            'confidence': 1.0,
            'est_value': 67000,
            'composition': [
                {'name': 'Quantanium', 'prob': 0.05, 'medPct': 0.30, 'value': 117000, 'price': 88},
                {'name': 'Taranite', 'prob': 0.10, 'medPct': 0.31, 'value': 59000, 'price': 61},
                {'name': 'Bexalite', 'prob': 0.12, 'medPct': 0.30, 'value': 76000, 'price': 44},
                {'name': 'Gold', 'prob': 0.29, 'medPct': 0.31, 'value': 11000, 'price': 7},
                {'name': 'Beryl', 'prob': 0.39, 'medPct': 0.42, 'value': 69000, 'price': 4},
                {'name': 'Tungsten', 'prob': 0.18, 'medPct': 0.46, 'value': 5000, 'price': 4},
                {'name': 'Titanium', 'prob': 0.12, 'medPct': 0.49, 'value': 21000, 'price': 8},
                {'name': 'Quartz', 'prob': 0.13, 'medPct': 0.48, 'value': 30000, 'price': 2},
            ]
        }]
        
        self._test_overlay.show(test_signature, test_matches)
        self._log(f"🔔 Test popup displayed")
    
    def _init_scanner(self):
        """Initialize the signature scanner with database."""
        db_path = Path(__file__).parent / "data" / "combat_analyst_db.json"
        
        if db_path.exists():
            self.scanner = SignatureScanner(db_path)
            self._log(f"✓ Signature database loaded")
            
            # Check JXR support
            if self.scanner._check_jxr_support():
                self._log(f"✓ JXR support: {self.scanner._jxr_tool_path}")
            else:
                self._log("⚠ JXR not supported (install ImageMagick)")
        else:
            self._log("⚠ Signature database not found!")
            self._log(f"  Expected: {db_path}")
    
    def _toggle_debug(self):
        """Toggle debug mode on/off."""
        enabled = self.debug_var.get()
        if self.scanner:
            self.scanner.enable_debug(enabled)
            if enabled:
                self._log("🔧 Debug mode ENABLED")
                self._log(f"   Output: {self.scanner.debug_dir}")
            else:
                self._log("🔧 Debug mode disabled")
        self._save_config(show_message=False)  # Auto-save debug setting
    
    def _open_debug_folder(self):
        """Open the debug output folder in file explorer."""
        if self.scanner:
            debug_dir = self.scanner.debug_dir
            debug_dir.mkdir(exist_ok=True)
            
            import os
            import platform
            
            if platform.system() == 'Windows':
                os.startfile(debug_dir)
            elif platform.system() == 'Darwin':  # macOS
                os.system(f'open "{debug_dir}"')
            else:  # Linux
                os.system(f'xdg-open "{debug_dir}"')
            
            self._log(f"📂 Opened: {debug_dir}")
    
    def _init_pricing(self):
        """Initialize pricing system on startup."""
        self._log("Loading pricing data...")
        
        success, error = pricing.initialize_pricing()
        
        if success:
            manager = pricing.get_pricing_manager()
            status = manager.get_status()
            self._log(f"✓ Pricing loaded: {status['ore_count']} ores")
            self._log(f"  Systems: {', '.join(status['systems'])}")
            self._update_pricing_status()
            
            # Apply saved refinery yield
            pricing.set_refinery_yield(self.yield_var.get())
        else:
            self._log(f"⚠ Pricing failed: {error}")
            self._update_pricing_status()
    
    def _check_for_updates(self):
        """Check for updates in background thread."""
        def check():
            update_available, latest_version, download_url = version_checker.check_for_updates()
            
            if update_available:
                # Schedule UI update on main thread
                self.root.after(0, lambda: self._show_update_notification(latest_version, download_url))
        
        # Run in background thread
        thread = threading.Thread(target=check, daemon=True)
        thread.start()
    
    def _show_update_notification(self, latest_version: str, download_url: str):
        """Show update available notification."""
        self._log(f"")
        self._log(f"🔔 UPDATE AVAILABLE: v{latest_version}")
        self._log(f"   Current: v{self.VERSION}")
        self._log(f"   Download from GitHub releases")
        self._log(f"")
        
        # Optional: Show dialog
        if messagebox.askyesno(
            "Update Available",
            f"A new version is available!\n\n"
            f"Current: v{self.VERSION}\n"
            f"Latest: v{latest_version}\n\n"
            f"Would you like to open the download page?"
        ):
            import webbrowser
            webbrowser.open(download_url)
    
    def _refresh_pricing(self):
        """Refresh pricing data from UEX API."""
        self._log("Refreshing pricing data...")
        
        success, error = pricing.refresh_pricing()
        
        if success:
            manager = pricing.get_pricing_manager()
            status = manager.get_status()
            self._log(f"✓ Pricing refreshed: {status['ore_count']} ores")
            self._update_pricing_status()
            messagebox.showinfo("Pricing", f"Successfully loaded {status['ore_count']} ore prices")
        else:
            self._log(f"⚠ Refresh failed: {error}")
            self._update_pricing_status()
            messagebox.showerror("Pricing Error", f"Failed to refresh pricing data:\n{error}")
    
    def _update_pricing_status(self):
        """Update the pricing status label."""
        try:
            manager = pricing.get_pricing_manager()
            status = manager.get_status()
            
            if status['prices_loaded']:
                age_min = int(status['cache_age_seconds'] / 60) if status['cache_age_seconds'] else 0
                self.pricing_status_label.configure(
                    text=f"{status['ore_count']} ores ({age_min}m ago)",
                    fg=RegolithTheme.COLORS['success']
                )
            else:
                self.pricing_status_label.configure(
                    text="Not loaded",
                    fg=RegolithTheme.COLORS['error']
                )
        except Exception:
            self.pricing_status_label.configure(
                text="Error",
                fg=RegolithTheme.COLORS['error']
            )
    
    def _log(self, message: str):
        """Add message to log display."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)
    
    def _load_config(self):
        """Load saved configuration."""
        cfg = self.config.load()
        if cfg:
            self.folder_var.set(cfg.get('screenshot_folder', ''))
            self.duration_var.set(cfg.get('popup_duration', 10))
            self.scale_var.set(cfg.get('popup_scale', 1.0))
            self.yield_var.set(cfg.get('refinery_yield', 0.5))
            self.debug_var.set(cfg.get('debug_mode', False))
            
            # Update scale display
            self.scale_display.configure(text=f"{self.scale_var.get():.0%}")
            
            # Update yield display
            self.yield_display.configure(text=f"{int(self.yield_var.get() * 100)}%")
            
            # Load position
            pos_x = cfg.get('popup_position_x')
            pos_y = cfg.get('popup_position_y')
            if pos_x is not None and pos_y is not None:
                self.overlay_position = (pos_x, pos_y)
            
            self._update_position_label()
            
            # Apply debug mode
            if self.scanner and self.debug_var.get():
                self.scanner.enable_debug(True)
            
            self._log("✓ Settings loaded")
    
    def _save_config(self, show_message: bool = True):
        """Save current configuration."""
        cfg = {
            'screenshot_folder': self.folder_var.get(),
            'popup_duration': self.duration_var.get(),
            'popup_scale': self.scale_var.get(),
            'refinery_yield': self.yield_var.get(),
            'debug_mode': self.debug_var.get(),
        }
        
        # Save position
        if self.overlay_position:
            cfg['popup_position_x'] = self.overlay_position[0]
            cfg['popup_position_y'] = self.overlay_position[1]
        
        # Apply refinery yield to pricing manager
        pricing.set_refinery_yield(self.yield_var.get())
        
        self.config.save(cfg)
        self._log("💾 Settings saved")
        if show_message:
            messagebox.showinfo("Settings", "Settings saved successfully")
    
    def run(self):
        """Run the application."""
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()
    
    def _on_close(self):
        """Handle window close."""
        self._stop_monitoring()
        self._save_config(show_message=False)  # Auto-save on close
        self.root.destroy()


def main():
    app = SCSignatureScannerApp()
    app.run()


if __name__ == "__main__":
    main()
