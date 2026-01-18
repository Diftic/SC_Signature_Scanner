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

import sys

# Show splash screen immediately (before heavy imports)
# splash.py only uses tkinter - no heavy dependencies
from splash import show_splash
_splash = show_splash()

# Now do the heavy imports with status updates
_splash.set_status("Loading core modules...")
import json
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

# Path utilities (must be first for frozen exe support)
import paths
_splash.pump(10)

_splash.set_status("Loading OCR engine...")

# Load OCR in background thread to keep animation running
_scanner_module = None
_scanner_error = None

def _load_scanner():
    global _scanner_module, _scanner_error
    try:
        import scanner as _mod
        _scanner_module = _mod
    except Exception as e:
        _scanner_error = e

_loader_thread = threading.Thread(target=_load_scanner)
_loader_thread.start()

# Keep animation running while loading
while _loader_thread.is_alive():
    _splash.pump(5)
_loader_thread.join()

if _scanner_error:
    raise _scanner_error
SignatureScanner = _scanner_module.SignatureScanner
_splash.pump(10)

_splash.set_status("Loading UI components...")
from overlay import OverlayPopup, PositionAdjuster
_splash.pump(5)
from monitor import ScreenshotMonitor
_splash.pump(5)
from config import Config
from theme import RegolithTheme, WarningBanner, UpdateBanner, StatusIndicator
_splash.pump(10)

_splash.set_status("Loading pricing data...")
import pricing
_splash.pump(5)
import version_checker
import region_selector
import regolith_api
_splash.pump(10)


class SCSignatureScannerApp:
    """Main application class."""
    
    VERSION = version_checker.CURRENT_VERSION
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"SC Signature Scanner")
        self.root.resizable(False, False)
        
        # Apply theme
        RegolithTheme.apply(self.root)
        
        # Center window on screen - wider layout
        window_width = 850
        window_height = 850
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
        self.regolith_user: Optional[str] = None
        
        # Build UI (must be first - needed for dialogs)
        self._create_ui()
        
        # Check for updates (background, non-blocking)
        self._check_for_updates()
    
    def _create_ui(self):
        """Create the main UI."""
        colors = RegolithTheme.COLORS
        fonts = RegolithTheme.FONTS
        
        # Main container
        main_container = tk.Frame(self.root, bg=colors['bg_main'])
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # === Header ===
        header = tk.Frame(main_container, bg=colors['bg_dark'], pady=12)
        header.pack(fill=tk.X)
        
        # Title with icon
        title_frame = tk.Frame(header, bg=colors['bg_dark'])
        title_frame.pack()
        
        title_icon = tk.Label(
            title_frame,
            text="📡",
            bg=colors['bg_dark'],
            font=('Segoe UI', 22)
        )
        title_icon.pack(side=tk.LEFT, padx=(0, 10))
        
        title_text = tk.Frame(title_frame, bg=colors['bg_dark'])
        title_text.pack(side=tk.LEFT)
        
        title = tk.Label(
            title_text,
            text="SIGNATURE SCANNER",
            bg=colors['bg_dark'],
            fg=colors['accent_primary'],
            font=('Segoe UI', 16, 'bold')
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
        accent_line.pack(fill=tk.X, pady=(12, 0))
        
        # Warning banner
        self.warning_banner = WarningBanner(main_container, "Requires Windowed or Borderless Windowed mode")
        self.warning_banner.pack(fill=tk.X, padx=15, pady=10)

        # Update banner (created dynamically when update available)
        self.update_banner_container = main_container
        self.update_banner = None

        # === Notebook (Tabs) ===
        notebook = ttk.Notebook(main_container)
        notebook.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))
        
        # === Scanner Tab ===
        scanner_tab = tk.Frame(notebook, bg=colors['bg_main'])
        notebook.add(scanner_tab, text="  Scanner  ")
        
        scanner_content = tk.Frame(scanner_tab, bg=colors['bg_main'], padx=5, pady=10)
        scanner_content.pack(fill=tk.BOTH, expand=True)
        
        # Screenshot folder section
        folder_section = tk.Frame(scanner_content, bg=colors['bg_main'])
        folder_section.pack(fill=tk.X, pady=(0, 10))
        
        folder_label = tk.Label(
            folder_section,
            text="SCREENSHOT FOLDER",
            bg=colors['bg_main'],
            fg=colors['accent_primary'],
            font=fonts['subheading']
        )
        folder_label.pack(anchor=tk.W, pady=(0, 5))
        
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
        folder_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8, pady=6)
        
        browse_btn = tk.Button(
            folder_inner,
            text="Browse",
            bg=colors['bg_light'],
            fg=colors['text_primary'],
            font=fonts['body'],
            relief='flat',
            padx=15,
            pady=3,
            cursor='hand2',
            command=self._browse_folder
        )
        browse_btn.pack(side=tk.RIGHT, padx=(0, 4), pady=4)
        
        # Status and controls row
        control_row = tk.Frame(scanner_content, bg=colors['bg_main'])
        control_row.pack(fill=tk.X, pady=(0, 10))
        
        # Status section (left side)
        status_border = tk.Frame(control_row, bg=colors['border'])
        status_border.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        status_inner = tk.Frame(status_border, bg=colors['bg_light'], padx=12, pady=8)
        status_inner.pack(fill=tk.X, padx=1, pady=1)
        
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
        
        # Control buttons (right side)
        btn_frame = tk.Frame(control_row, bg=colors['bg_main'])
        btn_frame.pack(side=tk.RIGHT)
        
        self.start_btn = tk.Button(
            btn_frame,
            text="▶  START MONITORING",
            bg=colors['accent_primary'],
            fg=colors['bg_dark'],
            font=('Segoe UI', 10, 'bold'),
            relief='flat',
            padx=15,
            pady=8,
            cursor='hand2',
            command=self._toggle_monitoring
        )
        self.start_btn.pack(side=tk.LEFT, padx=(0, 8))
        
        test_btn = tk.Button(
            btn_frame,
            text="🧪  Test",
            bg=colors['bg_light'],
            fg=colors['text_primary'],
            font=fonts['body'],
            relief='flat',
            padx=12,
            pady=8,
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
        log_label.pack(anchor=tk.W, pady=(0, 5))
        
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
            pady=8,
            height=12,
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
        
        # === Row 1: Scan Region + Popup Position (side by side) ===
        row1 = tk.Frame(settings_content, bg=colors['bg_main'])
        row1.pack(fill=tk.X, pady=(0, 10))
        
        # Left: Scan Region
        region_frame = tk.Frame(row1, bg=colors['bg_main'])
        region_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        region_label = tk.Label(
            region_frame,
            text="SCAN REGION",
            bg=colors['bg_main'],
            fg=colors['accent_primary'],
            font=fonts['subheading']
        )
        region_label.pack(anchor=tk.W, pady=(0, 5))
        
        region_border = tk.Frame(region_frame, bg=colors['border'])
        region_border.pack(fill=tk.BOTH, expand=True)
        
        region_inner = tk.Frame(region_border, bg=colors['bg_light'], padx=12, pady=10)
        region_inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        
        region_desc = tk.Label(
            region_inner,
            text="Define where signatures appear on screen",
            bg=colors['bg_light'],
            fg=colors['text_muted'],
            font=fonts['small']
        )
        region_desc.pack(anchor=tk.W, pady=(0, 6))
        
        region_row = tk.Frame(region_inner, bg=colors['bg_light'])
        region_row.pack(fill=tk.X, pady=(0, 8))
        
        self.region_label = tk.Label(
            region_row,
            text="Not configured",
            bg=colors['bg_light'],
            fg=colors['text_muted'],
            font=fonts['mono']
        )
        self.region_label.pack(side=tk.LEFT)
        
        region_btn_frame = tk.Frame(region_inner, bg=colors['bg_light'])
        region_btn_frame.pack(fill=tk.X)
        
        define_region_btn = tk.Button(
            region_btn_frame,
            text="📐  Define",
            bg=colors['cyan'],
            fg=colors['bg_dark'],
            font=('Segoe UI', 9, 'bold'),
            relief='flat',
            padx=10,
            pady=4,
            cursor='hand2',
            command=self._define_scan_region
        )
        define_region_btn.pack(side=tk.LEFT, padx=(0, 8))
        
        clear_region_btn = tk.Button(
            region_btn_frame,
            text="✕  Clear",
            bg=colors['bg_hover'],
            fg=colors['text_primary'],
            font=fonts['body'],
            relief='flat',
            padx=10,
            pady=4,
            cursor='hand2',
            command=self._clear_scan_region
        )
        clear_region_btn.pack(side=tk.LEFT)
        
        # Right: Popup Position
        pos_frame = tk.Frame(row1, bg=colors['bg_main'])
        pos_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        pos_label = tk.Label(
            pos_frame,
            text="POPUP POSITION",
            bg=colors['bg_main'],
            fg=colors['accent_primary'],
            font=fonts['subheading']
        )
        pos_label.pack(anchor=tk.W, pady=(0, 5))
        
        pos_border = tk.Frame(pos_frame, bg=colors['border'])
        pos_border.pack(fill=tk.BOTH, expand=True)
        
        pos_inner = tk.Frame(pos_border, bg=colors['bg_light'], padx=12, pady=10)
        pos_inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        
        pos_desc = tk.Label(
            pos_inner,
            text="Where results overlay appears",
            bg=colors['bg_light'],
            fg=colors['text_muted'],
            font=fonts['small']
        )
        pos_desc.pack(anchor=tk.W, pady=(0, 6))
        
        pos_row = tk.Frame(pos_inner, bg=colors['bg_light'])
        pos_row.pack(fill=tk.X, pady=(0, 8))
        
        self.position_label = tk.Label(
            pos_row,
            text="Not set (centered)",
            bg=colors['bg_light'],
            fg=colors['text_muted'],
            font=fonts['mono']
        )
        self.position_label.pack(side=tk.LEFT)
        
        pos_btn_frame = tk.Frame(pos_inner, bg=colors['bg_light'])
        pos_btn_frame.pack(fill=tk.X)
        
        adjust_btn = tk.Button(
            pos_btn_frame,
            text="📍  Adjust",
            bg=colors['cyan'],
            fg=colors['bg_dark'],
            font=('Segoe UI', 9, 'bold'),
            relief='flat',
            padx=10,
            pady=4,
            cursor='hand2',
            command=self._adjust_position
        )
        adjust_btn.pack(side=tk.LEFT, padx=(0, 8))
        
        reset_btn = tk.Button(
            pos_btn_frame,
            text="↺  Reset",
            bg=colors['bg_hover'],
            fg=colors['text_primary'],
            font=fonts['body'],
            relief='flat',
            padx=10,
            pady=4,
            cursor='hand2',
            command=self._reset_position
        )
        reset_btn.pack(side=tk.LEFT)
        
        # Update labels on startup
        self._update_region_label()
        
        # === Row 2: Popup Duration + Popup Scale (side by side) ===
        row2 = tk.Frame(settings_content, bg=colors['bg_main'])
        row2.pack(fill=tk.X, pady=(0, 10))
        
        # Left: Popup Duration
        dur_frame = tk.Frame(row2, bg=colors['bg_main'])
        dur_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        dur_label = tk.Label(
            dur_frame,
            text="POPUP DURATION",
            bg=colors['bg_main'],
            fg=colors['accent_primary'],
            font=fonts['subheading']
        )
        dur_label.pack(anchor=tk.W, pady=(0, 5))
        
        dur_border = tk.Frame(dur_frame, bg=colors['border'])
        dur_border.pack(fill=tk.BOTH, expand=True)
        
        dur_inner = tk.Frame(dur_border, bg=colors['bg_light'], padx=12, pady=10)
        dur_inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        
        dur_row = tk.Frame(dur_inner, bg=colors['bg_light'])
        dur_row.pack(fill=tk.X, pady=(5, 0))
        
        self.duration_var = tk.IntVar(value=10)
        dur_spin = tk.Spinbox(
            dur_row,
            from_=1,
            to=30,
            textvariable=self.duration_var,
            width=5,
            bg=colors['bg_dark'],
            fg=colors['text_primary'],
            font=fonts['mono'],
            relief='flat',
            buttonbackground=colors['bg_light']
        )
        dur_spin.pack(side=tk.LEFT)
        
        dur_text = tk.Label(
            dur_row,
            text="seconds",
            bg=colors['bg_light'],
            fg=colors['text_secondary'],
            font=fonts['body']
        )
        dur_text.pack(side=tk.LEFT, padx=(8, 0))
        
        # Right: Popup Scale
        scale_frame = tk.Frame(row2, bg=colors['bg_main'])
        scale_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        scale_label = tk.Label(
            scale_frame,
            text="POPUP SCALE",
            bg=colors['bg_main'],
            fg=colors['accent_primary'],
            font=fonts['subheading']
        )
        scale_label.pack(anchor=tk.W, pady=(0, 5))
        
        scale_border = tk.Frame(scale_frame, bg=colors['border'])
        scale_border.pack(fill=tk.BOTH, expand=True)
        
        scale_inner = tk.Frame(scale_border, bg=colors['bg_light'], padx=12, pady=10)
        scale_inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        
        scale_row = tk.Frame(scale_inner, bg=colors['bg_light'])
        scale_row.pack(fill=tk.X, pady=(5, 0))
        
        self.scale_var = tk.DoubleVar(value=1.0)
        
        scale_label_min = tk.Label(
            scale_row,
            text="50%",
            bg=colors['bg_light'],
            fg=colors['text_muted'],
            font=fonts['small']
        )
        scale_label_min.pack(side=tk.LEFT)
        
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
            length=150,
            showvalue=False,
            command=update_scale_label
        )
        scale_slider.pack(side=tk.LEFT, padx=(5, 5))
        
        scale_label_max = tk.Label(
            scale_row,
            text="200%",
            bg=colors['bg_light'],
            fg=colors['text_muted'],
            font=fonts['small']
        )
        scale_label_max.pack(side=tk.LEFT)
        
        self.scale_display = tk.Label(
            scale_row,
            text="100%",
            bg=colors['bg_light'],
            fg=colors['cyan'],
            font=fonts['mono']
        )
        self.scale_display.pack(side=tk.LEFT, padx=(10, 0))
        
        # === Row 3: Refinery Method + Data Sources (side by side) ===
        row3 = tk.Frame(settings_content, bg=colors['bg_main'])
        row3.pack(fill=tk.X, pady=(0, 10))
        
        # Left: Refinery Method
        method_frame = tk.Frame(row3, bg=colors['bg_main'])
        method_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        method_label = tk.Label(
            method_frame,
            text="REFINERY METHOD",
            bg=colors['bg_main'],
            fg=colors['accent_primary'],
            font=fonts['subheading']
        )
        method_label.pack(anchor=tk.W, pady=(0, 5))
        
        method_border = tk.Frame(method_frame, bg=colors['border'])
        method_border.pack(fill=tk.BOTH, expand=True)
        
        method_inner = tk.Frame(method_border, bg=colors['bg_light'], padx=12, pady=10)
        method_inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        
        method_desc = tk.Label(
            method_inner,
            text="Affects value estimates",
            bg=colors['bg_light'],
            fg=colors['text_muted'],
            font=fonts['small']
        )
        method_desc.pack(anchor=tk.W, pady=(0, 6))
        
        # Refinery methods with yields
        self.refinery_methods = {
            'Dinyx Solventation (52.93%)': 0.5293,
            'Ferron Exchange (52.93%)': 0.5293,
            'Pyrometric Chromalysis (52.93%)': 0.5293,
            'Electrostarolysis (45%)': 0.45,
            'Gaskin Process (45%)': 0.45,
            'Thermonatic Deposition (45%)': 0.45,
            'Cormack (37.05%)': 0.3705,
            'Kazen Winnowing (37.05%)': 0.3705,
            'XCR Reaction (37.05%)': 0.3705,
        }
        
        method_row = tk.Frame(method_inner, bg=colors['bg_light'])
        method_row.pack(fill=tk.X)
        
        self.method_var = tk.StringVar(value='Dinyx Solventation (52.93%)')
        method_combo = ttk.Combobox(
            method_row,
            textvariable=self.method_var,
            values=list(self.refinery_methods.keys()),
            state='readonly',
            width=28,
            font=fonts['body']
        )
        method_combo.pack(side=tk.LEFT)
        method_combo.bind('<<ComboboxSelected>>', self._on_method_changed)
        
        # Right: Data Sources
        data_frame = tk.Frame(row3, bg=colors['bg_main'])
        data_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        data_label = tk.Label(
            data_frame,
            text="DATA SOURCES",
            bg=colors['bg_main'],
            fg=colors['accent_primary'],
            font=fonts['subheading']
        )
        data_label.pack(anchor=tk.W, pady=(0, 5))
        
        data_border = tk.Frame(data_frame, bg=colors['border'])
        data_border.pack(fill=tk.BOTH, expand=True)
        
        data_inner = tk.Frame(data_border, bg=colors['bg_light'], padx=12, pady=10)
        data_inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        
        # Regolith status row
        data_row1 = tk.Frame(data_inner, bg=colors['bg_light'])
        data_row1.pack(fill=tk.X, pady=(0, 4))
        
        regolith_text = tk.Label(
            data_row1,
            text="🔑 Regolith:",
            bg=colors['bg_light'],
            fg=colors['text_secondary'],
            font=fonts['small']
        )
        regolith_text.pack(side=tk.LEFT)
        
        self.api_status_label = tk.Label(
            data_row1,
            text="--",
            bg=colors['bg_light'],
            fg=colors['text_muted'],
            font=fonts['small']
        )
        self.api_status_label.pack(side=tk.LEFT, padx=(5, 10))
        
        self.regolith_cache_label = tk.Label(
            data_row1,
            text="",
            bg=colors['bg_light'],
            fg=colors['text_muted'],
            font=fonts['small']
        )
        self.regolith_cache_label.pack(side=tk.LEFT)
        
        # UEX status row
        data_row2 = tk.Frame(data_inner, bg=colors['bg_light'])
        data_row2.pack(fill=tk.X, pady=(0, 6))
        
        uex_text = tk.Label(
            data_row2,
            text="💰 UEX:",
            bg=colors['bg_light'],
            fg=colors['text_secondary'],
            font=fonts['small']
        )
        uex_text.pack(side=tk.LEFT)
        
        self.pricing_status_label = tk.Label(
            data_row2,
            text="--",
            bg=colors['bg_light'],
            fg=colors['text_muted'],
            font=fonts['small']
        )
        self.pricing_status_label.pack(side=tk.LEFT, padx=(5, 0))
        
        # Buttons row
        data_row3 = tk.Frame(data_inner, bg=colors['bg_light'])
        data_row3.pack(fill=tk.X)
        
        change_key_btn = tk.Button(
            data_row3,
            text="🔑 Key",
            bg=colors['bg_hover'],
            fg=colors['text_primary'],
            font=fonts['small'],
            relief='flat',
            padx=6,
            pady=2,
            cursor='hand2',
            command=self._change_api_key
        )
        change_key_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        refresh_all_btn = tk.Button(
            data_row3,
            text="🔄 Refresh",
            bg=colors['cyan'],
            fg=colors['bg_dark'],
            font=('Segoe UI', 8, 'bold'),
            relief='flat',
            padx=6,
            pady=2,
            cursor='hand2',
            command=self._refresh_all_data
        )
        refresh_all_btn.pack(side=tk.LEFT)
        
        # === Row 5: Debug Output Folder (full width) ===
        row5 = tk.Frame(settings_content, bg=colors['bg_main'])
        row5.pack(fill=tk.X, pady=(0, 10))
        
        debug_folder_label = tk.Label(
            row5,
            text="DEBUG OUTPUT FOLDER",
            bg=colors['bg_main'],
            fg=colors['accent_primary'],
            font=fonts['subheading']
        )
        debug_folder_label.pack(anchor=tk.W, pady=(0, 5))
        
        debug_folder_border = tk.Frame(row5, bg=colors['border'])
        debug_folder_border.pack(fill=tk.X)
        
        debug_folder_inner = tk.Frame(debug_folder_border, bg=colors['bg_light'], padx=12, pady=10)
        debug_folder_inner.pack(fill=tk.X, padx=1, pady=1)
        
        debug_folder_desc = tk.Label(
            debug_folder_inner,
            text="Where debug images are saved (for testing/troubleshooting)",
            bg=colors['bg_light'],
            fg=colors['text_muted'],
            font=fonts['small']
        )
        debug_folder_desc.pack(anchor=tk.W, pady=(0, 6))
        
        debug_folder_row = tk.Frame(debug_folder_inner, bg=colors['bg_light'])
        debug_folder_row.pack(fill=tk.X)
        
        self.debug_folder_var = tk.StringVar()
        debug_folder_entry = tk.Entry(
            debug_folder_row,
            textvariable=self.debug_folder_var,
            bg=colors['bg_dark'],
            fg=colors['text_primary'],
            font=fonts['mono_small'],
            relief='flat',
            insertbackground=colors['accent_primary']
        )
        debug_folder_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8), pady=2)
        
        browse_debug_btn = tk.Button(
            debug_folder_row,
            text="📁  Browse",
            bg=colors['cyan'],
            fg=colors['bg_dark'],
            font=('Segoe UI', 9, 'bold'),
            relief='flat',
            padx=10,
            pady=4,
            cursor='hand2',
            command=self._browse_debug_folder
        )
        browse_debug_btn.pack(side=tk.LEFT, padx=(0, 8))
        
        reset_debug_folder_btn = tk.Button(
            debug_folder_row,
            text="↺  Reset",
            bg=colors['bg_hover'],
            fg=colors['text_primary'],
            font=fonts['body'],
            relief='flat',
            padx=10,
            pady=4,
            cursor='hand2',
            command=self._reset_debug_folder
        )
        reset_debug_folder_btn.pack(side=tk.LEFT)
        
        # === Row 6: Debug Mode + Action Buttons ===
        row6 = tk.Frame(settings_content, bg=colors['bg_main'])
        row6.pack(fill=tk.X, pady=(0, 10))
        
        # Left: Debug Mode
        debug_frame = tk.Frame(row6, bg=colors['bg_main'])
        debug_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        debug_label = tk.Label(
            debug_frame,
            text="DEBUG MODE",
            bg=colors['bg_main'],
            fg=colors['accent_primary'],
            font=fonts['subheading']
        )
        debug_label.pack(anchor=tk.W, pady=(0, 5))
        
        debug_border = tk.Frame(debug_frame, bg=colors['border'])
        debug_border.pack(fill=tk.BOTH, expand=True)
        
        debug_inner = tk.Frame(debug_border, bg=colors['bg_light'], padx=12, pady=10)
        debug_inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        
        debug_row = tk.Frame(debug_inner, bg=colors['bg_light'])
        debug_row.pack(fill=tk.X, pady=(5, 0))
        
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
            text="📂  Open",
            bg=colors['bg_hover'],
            fg=colors['text_primary'],
            font=fonts['body'],
            relief='flat',
            padx=10,
            pady=3,
            cursor='hand2',
            command=self._open_debug_folder
        )
        open_debug_btn.pack(side=tk.RIGHT)
        
        # Right: Action Buttons
        action_frame = tk.Frame(row6, bg=colors['bg_main'])
        action_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        action_label = tk.Label(
            action_frame,
            text="ACTIONS",
            bg=colors['bg_main'],
            fg=colors['accent_primary'],
            font=fonts['subheading']
        )
        action_label.pack(anchor=tk.W, pady=(0, 5))
        
        action_border = tk.Frame(action_frame, bg=colors['border'])
        action_border.pack(fill=tk.BOTH, expand=True)
        
        action_inner = tk.Frame(action_border, bg=colors['bg_light'], padx=12, pady=10)
        action_inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        
        action_row = tk.Frame(action_inner, bg=colors['bg_light'])
        action_row.pack(fill=tk.X, pady=(5, 0))
        
        test_popup_btn = tk.Button(
            action_row,
            text="🔔  Test Popup",
            bg=colors['bg_hover'],
            fg=colors['text_primary'],
            font=fonts['body'],
            relief='flat',
            padx=12,
            pady=4,
            cursor='hand2',
            command=self._test_popup
        )
        test_popup_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        save_btn = tk.Button(
            action_row,
            text="💾  Save Settings",
            bg=colors['success'],
            fg=colors['bg_dark'],
            font=('Segoe UI', 9, 'bold'),
            relief='flat',
            padx=12,
            pady=4,
            cursor='hand2',
            command=self._save_config
        )
        save_btn.pack(side=tk.LEFT)
        
        # === About Tab ===
        about_tab = tk.Frame(notebook, bg=colors['bg_main'])
        notebook.add(about_tab, text="  About  ")
        
        about_content = tk.Frame(about_tab, bg=colors['bg_main'], padx=5, pady=10)
        about_content.pack(fill=tk.BOTH, expand=True)
        
        # Two-column layout for About
        about_cols = tk.Frame(about_content, bg=colors['bg_main'])
        about_cols.pack(fill=tk.BOTH, expand=True)
        
        # Left column: Info + How to use
        left_col = tk.Frame(about_cols, bg=colors['bg_main'])
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # Logo/Title
        about_header = tk.Frame(left_col, bg=colors['bg_main'])
        about_header.pack(fill=tk.X, pady=(0, 15))
        
        about_title = tk.Label(
            about_header,
            text="📡 SC SIGNATURE SCANNER",
            bg=colors['bg_main'],
            fg=colors['accent_primary'],
            font=('Segoe UI', 14, 'bold')
        )
        about_title.pack(anchor=tk.W)
        
        about_ver = tk.Label(
            about_header,
            text=f"Version {self.VERSION}",
            bg=colors['bg_main'],
            fg=colors['text_muted'],
            font=fonts['small']
        )
        about_ver.pack(anchor=tk.W)
        
        desc_label = tk.Label(
            left_col,
            text="Monitors Star Citizen screenshots for signature\nvalues and identifies potential targets in real-time.\n\nMade by Mallachi, for Regolith.Rocks\nJanuary 2026",
            bg=colors['bg_main'],
            fg=colors['text_secondary'],
            font=fonts['body'],
            justify=tk.LEFT
        )
        desc_label.pack(anchor=tk.W, pady=(0, 15))
        
        # How to use
        howto_label = tk.Label(
            left_col,
            text="HOW TO USE",
            bg=colors['bg_main'],
            fg=colors['accent_primary'],
            font=fonts['subheading']
        )
        howto_label.pack(anchor=tk.W, pady=(0, 5))
        
        howto_border = tk.Frame(left_col, bg=colors['border'])
        howto_border.pack(fill=tk.X)
        
        howto_inner = tk.Frame(howto_border, bg=colors['bg_light'], padx=12, pady=10)
        howto_inner.pack(fill=tk.X, padx=1, pady=1)
        
        steps = [
            ("1.", "Set SC to Windowed or Borderless"),
            ("2.", "Define the scan region in Settings"),
            ("3.", "Select your screenshot folder"),
            ("4.", "Click Start Monitoring"),
            ("5.", "In-game: PrintScreen on signature"),
            ("6.", "Overlay shows identification"),
        ]
        
        for num, text in steps:
            step_row = tk.Frame(howto_inner, bg=colors['bg_light'])
            step_row.pack(fill=tk.X, pady=1)
            
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
                font=fonts['small'],
                anchor=tk.W
            )
            text_label.pack(side=tk.LEFT, fill=tk.X)
        
        # Thanks to section
        thanks_label = tk.Label(
            left_col,
            text="THANKS TO",
            bg=colors['bg_main'],
            fg=colors['accent_primary'],
            font=fonts['subheading']
        )
        thanks_label.pack(anchor=tk.W, pady=(15, 5))
        
        thanks_border = tk.Frame(left_col, bg=colors['border'])
        thanks_border.pack(fill=tk.X)
        
        thanks_inner = tk.Frame(thanks_border, bg=colors['bg_light'], padx=12, pady=10)
        thanks_inner.pack(fill=tk.X, padx=1, pady=1)
        
        thanks_text = tk.Label(
            thanks_inner,
            text="Thank you to those who participated\n in the building and testing process\n  - Raychaser - Regolith.Rocks\n  - iambass - Test crew\n  - Mavyre  - Test crew",
            bg=colors['bg_light'],
            fg=colors['text_secondary'],
            font=fonts['small'],
            justify=tk.LEFT
        )
        thanks_text.pack(anchor=tk.W)
        
        # Right column: Signature types
        right_col = tk.Frame(about_cols, bg=colors['bg_main'])
        right_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0))
        
        sig_label = tk.Label(
            right_col,
            text="SIGNATURE TYPES",
            bg=colors['bg_main'],
            fg=colors['accent_primary'],
            font=fonts['subheading']
        )
        sig_label.pack(anchor=tk.W, pady=(0, 5))
        
        sig_border = tk.Frame(right_col, bg=colors['border'])
        sig_border.pack(fill=tk.X)
        
        sig_inner = tk.Frame(sig_border, bg=colors['bg_light'], padx=12, pady=10)
        sig_inner.pack(fill=tk.X, padx=1, pady=1)
        
        sig_types = [
            ("🚀", "Space", "Asteroids - Ship mining only"),
            (None, None, "I, C, S, P, M, Q, E types"),
            ("", "", ""),
            ("⛏️", "Surface", "Surface deposits - Ship mining"),
            (None, None, "Shale, Felsic, Obsidian, Atacamite"),
            (None, None, "Quartzite, Gneiss, Granite, Igneous"),
            ("", "", ""),
            ("💎", "Ground", "Ground deposits - ROC or FPS"),
            (None, None, "Small (120) = FPS/Hand mining"),
            (None, None, "Large (620) = ROC/Vehicle"),
            (None, None, "100% single mineral per cluster"),
            ("", "", ""),
            ("🔧", "Salvage", "2000 sig per hull panel"),
        ]
        
        for icon, name, desc in sig_types:
            sig_row = tk.Frame(sig_inner, bg=colors['bg_light'])
            sig_row.pack(fill=tk.X, pady=2)
            
            if icon is not None:
                # Normal row with icon and name
                icon_label = tk.Label(
                    sig_row,
                    text=icon,
                    bg=colors['bg_light'],
                    font=('Segoe UI', 11),
                    width=2
                )
                icon_label.pack(side=tk.LEFT)
                
                name_label = tk.Label(
                    sig_row,
                    text=name,
                    bg=colors['bg_light'],
                    fg=colors['text_primary'],
                    font=('Segoe UI', 10, 'bold'),
                    width=8,
                    anchor=tk.W
                )
                name_label.pack(side=tk.LEFT)
            else:
                # Continuation row - indent to align with description
                spacer = tk.Label(
                    sig_row,
                    text="",
                    bg=colors['bg_light'],
                    width=10
                )
                spacer.pack(side=tk.LEFT)
            
            desc_label = tk.Label(
                sig_row,
                text=desc,
                bg=colors['bg_light'],
                fg=colors['text_muted'],
                font=fonts['small'],
                anchor=tk.W
            )
            desc_label.pack(side=tk.LEFT, fill=tk.X)
        
        # Buy Me a Coffee section (below Signature Types in right column)
        coffee_section = tk.Frame(right_col, bg=colors['bg_main'])
        coffee_section.pack(fill=tk.X, pady=(15, 0))
        
        coffee_text = tk.Label(
            coffee_section,
            text="This is a free piece of software intended to make the life of miners a\nlittle bit easier. If you like it and appreciate the work put into it,\nplease consider buying me a cup of coffee to feed my addiction.",
            bg=colors['bg_main'],
            fg=colors['text_muted'],
            font=fonts['small'],
            justify=tk.LEFT
        )
        coffee_text.pack(anchor=tk.W, pady=(0, 10), padx=(40, 0))
        
        def open_coffee():
            import webbrowser
            webbrowser.open("https://buymeacoffee.com/Mallachi")
        
        coffee_btn = tk.Button(
            coffee_section,
            text="\u2615  Buy Me a Coffee",
            bg='#FFDD00',
            fg='#000000',
            font=('Segoe UI', 12, 'bold'),
            relief='flat',
            padx=25,
            pady=10,
            cursor='hand2',
            command=open_coffee
        )
        coffee_btn.pack(anchor=tk.W, pady=(0, 8), padx=(100, 0))
        
        coffee_thanks = tk.Label(
            coffee_section,
            text="Thank you for your support.     -Mallachi",
            bg=colors['bg_main'],
            fg=colors['text_muted'],
            font=fonts['small']
        )
        coffee_thanks.pack(anchor=tk.W, padx=(100, 0))
    
    def _browse_folder(self):
        """Open folder browser dialog."""
        folder = filedialog.askdirectory(title="Select Star Citizen Screenshots Folder")
        if folder:
            self.folder_var.set(folder)
            self._log(f"📁 Screenshot folder: {folder}")
            self._save_config(show_message=False)
    
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
        
        # Check if scan region is configured
        if not region_selector.is_configured():
            result = messagebox.askyesno(
                "No Scan Region",
                "No scan region is configured.\n\n"
                "The scanner will search the entire image which may be slower and less accurate.\n\n"
                "Would you like to define a scan region first?"
            )
            if result:
                self._define_scan_region()
                return
        
        # Mark existing files to ignore
        self.processed_files = set(Path(folder).glob("*.png"))
        self.processed_files.update(Path(folder).glob("*.jpg"))
        self.processed_files.update(Path(folder).glob("*.jpeg"))
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
                
                # Show overlay (must schedule on main thread - watchdog runs in background thread)
                if matches:
                    self.root.after(0, lambda s=sig, m=matches: self._show_overlay(s, m))
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
    
    def _show_overlay(self, sig: int, matches: list):
        """Show the overlay popup (must be called from main thread)."""
        if not self.overlay:
            self.overlay = OverlayPopup(
                position=self.overlay_position,
                duration=self.duration_var.get(),
                scale=self.scale_var.get()
            )
        self.overlay.show(sig, matches)
    
    def _test_screenshot(self):
        """Test with a manually selected screenshot."""
        filepath = filedialog.askopenfilename(
            title="Select Screenshot to Test",
            filetypes=[
                ("Image files", "*.png *.jpg *.jpeg"),
                ("PNG files", "*.png"),
                ("JPEG files", "*.jpg *.jpeg"),
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
            self._save_config(show_message=False)
            
            if self.overlay:
                self.overlay.set_position(x, y)
        
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
        self._save_config(show_message=False)
        
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
        if hasattr(self, '_test_overlay') and self._test_overlay:
            self._test_overlay.destroy()
        
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
        db_path = paths.get_data_path() / "combat_analyst_db.json"
        
        if db_path.exists():
            self.scanner = SignatureScanner(db_path)
            self._log(f"✓ Signature database loaded")
        else:
            self._log("⚠ Signature database not found!")
            self._log(f"  Expected: {db_path}")
    
    def _toggle_debug(self):
        """Toggle debug mode on/off."""
        enabled = self.debug_var.get()
        if self.scanner:
            # Apply current debug folder setting
            debug_folder = self.debug_folder_var.get()
            if debug_folder:
                self.scanner.debug_dir = Path(debug_folder)
            
            self.scanner.enable_debug(enabled)
            if enabled:
                self._log("🔧 Debug mode ENABLED")
                self._log(f"   Output: {self.scanner.debug_dir}")
            else:
                self._log("🔧 Debug mode disabled")
        self._save_config(show_message=False)
    
    def _open_debug_folder(self):
        """Open the debug output folder in file explorer."""
        if self.scanner:
            debug_dir = self.scanner.debug_dir
            debug_dir.mkdir(exist_ok=True)
            
            import os
            import platform
            
            if platform.system() == 'Windows':
                os.startfile(debug_dir)
            elif platform.system() == 'Darwin':
                os.system(f'open "{debug_dir}"')
            else:
                os.system(f'xdg-open "{debug_dir}"')
            
            self._log(f"📂 Opened: {debug_dir}")
    
    def _browse_debug_folder(self):
        """Browse for debug output folder."""
        folder = filedialog.askdirectory(title="Select Debug Output Folder")
        if folder:
            self.debug_folder_var.set(folder)
            if self.scanner:
                self.scanner.debug_dir = Path(folder)
            self._log(f"📁 Debug folder: {folder}")
            self._save_config(show_message=False)
    
    def _reset_debug_folder(self):
        """Reset debug folder to default."""
        default_dir = paths.get_debug_path()
        self.debug_folder_var.set(str(default_dir))
        if self.scanner:
            self.scanner.debug_dir = default_dir
        self._log(f"📁 Debug folder reset to default")
        self._save_config(show_message=False)
    
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
            
            # Set yield from selected refinery method
            yield_value = self._get_current_yield()
            pricing.set_refinery_yield(yield_value)
        else:
            self._log(f"⚠ Pricing failed: {error}")
            self._update_pricing_status()
    
    def _on_method_changed(self, event=None):
        """Handle refinery method selection change."""
        method = self.method_var.get()
        yield_value = self.refinery_methods.get(method, 0.5293)
        pricing.set_refinery_yield(yield_value)
        self._log(f"⚙ Refinery method: {method.split(' (')[0]} ({yield_value:.2%})")
        self._save_config(show_message=False)
    
    def _get_current_yield(self) -> float:
        """Get the yield value for the currently selected refinery method."""
        method = self.method_var.get()
        return self.refinery_methods.get(method, 0.5293)
    
    def _check_for_updates(self):
        """Check for updates in background thread."""
        self._update_check_result = None
        self._update_check_done = False

        def check():
            try:
                self._update_check_result = version_checker.check_for_updates()
            except Exception as e:
                self._update_check_result = (False, None, None, str(e))
            self._update_check_done = True

        threading.Thread(target=check, daemon=True).start()

        # Poll for result from main thread
        self.root.after(500, self._poll_update_result)

    def _poll_update_result(self):
        """Poll for update check result from main thread."""
        if not self._update_check_done:
            # Keep polling
            self.root.after(200, self._poll_update_result)
            return

        result = self._update_check_result
        if result is None:
            self._log("⚠ Version check: no result")
            return

        # Check if error (4-tuple)
        if len(result) == 4:
            self._log(f"⚠ Version check failed: {result[3]}")
            return

        update_available, latest_version, download_url = result

        if update_available:
            self._show_update_notification(latest_version, download_url)
        elif latest_version:
            self._log(f"✓ Version check: up to date (v{self.VERSION})")
        else:
            self._log("⚠ Version check: could not reach GitHub")
    
    def _show_update_notification(self, latest_version: str, download_url: str):
        """Show update available dialog with options."""
        self._log(f"")
        self._log(f"🔔 UPDATE AVAILABLE: v{latest_version}")
        self._log(f"   Current: v{self.VERSION}")
        self._log(f"")

        # Create custom dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Update Available")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)

        # Center on parent
        dialog.geometry("400x180")
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 400) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 180) // 2
        dialog.geometry(f"+{x}+{y}")

        colors = RegolithTheme.COLORS
        dialog.configure(bg=colors['bg_main'])

        # Content
        content = tk.Frame(dialog, bg=colors['bg_main'], padx=20, pady=20)
        content.pack(fill=tk.BOTH, expand=True)

        # Icon and message
        tk.Label(
            content,
            text="🔔",
            bg=colors['bg_main'],
            font=('Segoe UI', 24)
        ).pack()

        tk.Label(
            content,
            text=f"A new version is available!",
            bg=colors['bg_main'],
            fg=colors['text_primary'],
            font=('Segoe UI', 12, 'bold')
        ).pack(pady=(5, 2))

        tk.Label(
            content,
            text=f"Current: v{self.VERSION}  →  Latest: v{latest_version}",
            bg=colors['bg_main'],
            fg=colors['text_muted'],
            font=('Segoe UI', 10)
        ).pack(pady=(0, 15))

        # Buttons
        btn_frame = tk.Frame(content, bg=colors['bg_main'])
        btn_frame.pack()

        def exit_and_download():
            import webbrowser
            import os
            webbrowser.open(download_url)
            dialog.destroy()
            try:
                self.root.destroy()
            except:
                pass
            os._exit(0)  # Force exit without cleanup to avoid tkinter errors

        def continue_old():
            dialog.destroy()
            self._show_update_banner(latest_version, download_url)

        tk.Button(
            btn_frame,
            text="Exit and Download",
            bg=colors['accent_primary'],
            fg='#000000',
            font=('Segoe UI', 10, 'bold'),
            relief='flat',
            padx=15,
            pady=5,
            cursor='hand2',
            command=exit_and_download
        ).pack(side=tk.LEFT, padx=(0, 10))

        tk.Button(
            btn_frame,
            text="Continue on old version",
            bg=colors['bg_light'],
            fg=colors['text_primary'],
            font=('Segoe UI', 10),
            relief='flat',
            padx=15,
            pady=5,
            cursor='hand2',
            command=continue_old
        ).pack(side=tk.LEFT)

        # Handle window close as "continue"
        dialog.protocol("WM_DELETE_WINDOW", continue_old)

    def _show_update_banner(self, version: str, download_url: str):
        """Show the update banner in the UI."""
        if self.update_banner is None:
            self.update_banner = UpdateBanner(
                self.update_banner_container,
                version,
                download_url
            )
            # Pack after warning banner
            self.update_banner.pack(fill=tk.X, padx=15, pady=(0, 10), after=self.warning_banner)
    
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
    
    def _change_api_key(self):
        """Allow user to change their API key."""
        cfg = self.config.load() or {}
        current_key = cfg.get('regolith_api_key', '')
        
        new_key = self._show_api_key_dialog(current_key)
        
        if new_key and new_key != current_key:
            # Validate the new key
            api = regolith_api.get_api(new_key)
            valid, message = api.validate_key()
            
            if valid:
                cfg['regolith_api_key'] = new_key
                self.config.save(cfg)
                self.regolith_user = message
                self._log(f"✓ API key updated: {message}")
                self._update_api_status()
                messagebox.showinfo("API Key", f"API key validated successfully!\n\nLogged in as: {message}")
            else:
                self._log(f"⚠ API key invalid: {message}")
                messagebox.showerror("Invalid Key", f"API key validation failed:\n{message}")
    
    def _refresh_all_data(self):
        """Refresh both UEX pricing and Regolith survey data."""
        self._log("Refreshing all data...")
        
        errors = []
        
        # Refresh Regolith data
        cfg = self.config.load() or {}
        api_key = cfg.get('regolith_api_key', '')
        
        if api_key:
            api = regolith_api.get_api(api_key)
            success, message = api.refresh_cache()
            if success:
                self._log(f"✓ Regolith data refreshed")
            else:
                self._log(f"⚠ Regolith refresh failed: {message}")
                errors.append(f"Regolith: {message}")
        else:
            errors.append("Regolith: No API key configured")
        
        # Refresh UEX pricing
        success, error = pricing.refresh_pricing()
        if success:
            manager = pricing.get_pricing_manager()
            status = manager.get_status()
            self._log(f"✓ UEX pricing refreshed: {status['ore_count']} ores")
        else:
            self._log(f"⚠ UEX refresh failed: {error}")
            errors.append(f"UEX: {error}")
        
        # Update UI
        self._update_pricing_status()
        self._update_api_status()
        
        if errors:
            messagebox.showwarning(
                "Partial Refresh",
                f"Some data sources failed to refresh:\n\n" + "\n".join(errors)
            )
        else:
            messagebox.showinfo("Data Refreshed", "All data sources refreshed successfully!")
    
    def _update_api_status(self):
        """Update the API status labels."""
        colors = RegolithTheme.COLORS
        
        # Check if we have a valid user
        if hasattr(self, 'regolith_user') and self.regolith_user:
            self.api_status_label.configure(
                text=self.regolith_user,
                fg=colors['success']
            )
        else:
            self.api_status_label.configure(
                text="Not validated",
                fg=colors['text_muted']
            )
        
        # Update cache age
        cfg = self.config.load() or {}
        api_key = cfg.get('regolith_api_key', '')
        
        if api_key:
            api = regolith_api.get_api(api_key)
            cache_age = api.get_cache_age_str()
            self.regolith_cache_label.configure(
                text=f"Cache: {cache_age}",
                fg=colors['text_secondary'] if api.is_cache_valid() else colors['warning']
            )
        else:
            self.regolith_cache_label.configure(
                text="Cache: --",
                fg=colors['text_muted']
            )
    
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
    
    def _define_scan_region(self):
        """Open region selector to define scan area."""
        def on_save(x1, y1, x2, y2):
            self._update_region_label()
            self._log(f"📐 Scan region set: ({x1}, {y1}) to ({x2}, {y2})")
        
        selector = region_selector.RegionSelector(
            parent=self.root,
            on_save=on_save
        )
        selector.open()
    
    def _clear_scan_region(self):
        """Clear the saved scan region."""
        if region_selector.is_configured():
            region_selector.clear_region()
            self._update_region_label()
            self._log("📐 Scan region cleared")
            messagebox.showinfo("Region Cleared", "Scan region has been cleared.")
        else:
            messagebox.showinfo("No Region", "No scan region is currently configured.")
    
    def _update_region_label(self):
        """Update the region display label."""
        region = region_selector.load_region()
        if region:
            x1, y1, x2, y2 = region
            w = x2 - x1
            h = y2 - y1
            self.region_label.configure(
                text=f"({x1},{y1})→({x2},{y2}) [{w}×{h}]",
                fg=RegolithTheme.COLORS['success']
            )
        else:
            self.region_label.configure(
                text="Not configured",
                fg=RegolithTheme.COLORS['text_muted']
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
        
        # Set default debug folder
        default_debug_dir = paths.get_debug_path()
        self.debug_folder_var.set(str(default_debug_dir))
        
        if cfg:
            self.folder_var.set(cfg.get('screenshot_folder', ''))
            self.duration_var.set(cfg.get('popup_duration', 10))
            self.scale_var.set(cfg.get('popup_scale', 1.0))
            self.debug_var.set(cfg.get('debug_mode', False))
            
            # Load refinery method
            saved_method = cfg.get('refinery_method', 'Dinyx Solventation (52.93%)')
            if saved_method in self.refinery_methods:
                self.method_var.set(saved_method)
            
            # Load debug folder
            debug_folder = cfg.get('debug_folder', '')
            if debug_folder and Path(debug_folder).exists():
                self.debug_folder_var.set(debug_folder)
                if self.scanner:
                    self.scanner.debug_dir = Path(debug_folder)
            
            self.scale_display.configure(text=f"{self.scale_var.get():.0%}")
            
            pos_x = cfg.get('popup_position_x')
            pos_y = cfg.get('popup_position_y')
            if pos_x is not None and pos_y is not None:
                self.overlay_position = (pos_x, pos_y)
            
            self._update_position_label()
            
            if self.scanner and self.debug_var.get():
                self.scanner.enable_debug(True)
            
            self._log("✓ Settings loaded")
    
    def _save_config(self, show_message: bool = True):
        """Save current configuration."""
        # Load existing config to preserve API key and other settings
        cfg = self.config.load() or {}
        
        # Update with current UI values
        cfg.update({
            'screenshot_folder': self.folder_var.get(),
            'popup_duration': self.duration_var.get(),
            'popup_scale': self.scale_var.get(),
            'refinery_method': self.method_var.get(),
            'debug_mode': self.debug_var.get(),
            'debug_folder': self.debug_folder_var.get(),
        })
        
        if self.overlay_position:
            cfg['popup_position_x'] = self.overlay_position[0]
            cfg['popup_position_y'] = self.overlay_position[1]
        else:
            # Clear position if reset
            cfg.pop('popup_position_x', None)
            cfg.pop('popup_position_y', None)
        
        # Update pricing yield from current method
        pricing.set_refinery_yield(self._get_current_yield())
        
        self.config.save(cfg)
        self._log("💾 Settings saved")
        if show_message:
            messagebox.showinfo("Settings", "Settings saved successfully")
    
    def run(self):
        """Run the application."""
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        
        # Step 1: Validate API key first (required for Regolith data)
        if not self._validate_api_key_startup():
            self.root.destroy()
            return
        
        # Step 2: Initialize scanner with signature database
        self._init_scanner()
        
        # Step 3: Load user config (after scanner exists so debug mode can be applied)
        self._load_config()
        
        # Step 4: Initialize pricing system (UEX)
        self._init_pricing()
        
        self.root.mainloop()
    
    def _validate_api_key_startup(self) -> bool:
        """Validate API key on startup. Returns True if valid, False to exit."""
        cfg = self.config.load() or {}
        api_key = cfg.get('regolith_api_key', '')
        error_message = None
        
        while True:
            if api_key:
                # Try to validate existing key (with retry)
                valid, message = self._validate_key_with_retry(api_key)
                
                if valid:
                    self._log(f"✓ API key valid: {message}")
                    self.regolith_user = message
                    
                    # Check/update cache
                    api = regolith_api.get_api(api_key)
                    self._check_regolith_cache(api)
                    
                    # Update UI status
                    self._update_api_status()
                    return True
                else:
                    self._log(f"⚠ API key invalid: {message}")
                    error_message = message
            
            # Show API key dialog
            result = self._show_api_key_dialog(api_key, error_message)
            
            if result is None:
                # User cancelled
                return False
            
            api_key = result
            
            # Save the new key
            cfg['regolith_api_key'] = api_key
            self.config.save(cfg)
    
    def _validate_key_with_retry(self, api_key: str) -> tuple:
        """Validate API key with one retry after 3 seconds on failure.
        
        Returns:
            Tuple of (is_valid, message)
        """
        self._log("Validating Regolith.rocks API key...")
        api = regolith_api.get_api(api_key)
        
        # First attempt
        valid, message = api.validate_key()
        
        if valid:
            return True, message
        
        # Check if it's a server/connection error (worth retrying)
        retry_errors = ["server error", "timed out", "connect", "connection"]
        should_retry = any(err in message.lower() for err in retry_errors)
        
        if not should_retry:
            # Don't retry for auth errors like "Invalid API key"
            return False, message
        
        # Wait and retry
        self._log(f"Connection issue: {message}")
        self._log("Retrying in 3 seconds...")
        time.sleep(3)
        
        # Second attempt
        valid, message = api.validate_key()
        
        if valid:
            self._log("Retry successful")
            return True, message
        else:
            return False, f"{message} (after retry)"
    
    def _check_regolith_cache(self, api: regolith_api.RegolithAPI):
        """Check Regolith cache and refresh if needed."""
        if api.is_cache_valid():
            age = api.get_cache_age_str()
            self._log(f"✓ Regolith cache valid ({age})")
        else:
            self._log("Regolith cache expired, refreshing...")
            success, message = api.refresh_cache()
            if success:
                self._log(f"✓ {message}")
            else:
                self._log(f"⚠ Cache refresh failed: {message}")
    
    def _show_api_key_dialog(self, current_key: str = "", error_msg: str = None) -> str:
        """Show dialog to enter API key. Returns key or None if cancelled."""
        colors = RegolithTheme.COLORS
        fonts = RegolithTheme.FONTS
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Regolith.rocks API Key Required")
        dialog.configure(bg=colors['bg_main'])
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Center on screen
        dialog_width = 500
        dialog_height = 420
        x = (dialog.winfo_screenwidth() - dialog_width) // 2
        y = (dialog.winfo_screenheight() - dialog_height) // 2
        dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
        dialog.resizable(False, False)
        
        result = {'key': None}
        
        # Content
        content = tk.Frame(dialog, bg=colors['bg_main'], padx=25, pady=20)
        content.pack(fill=tk.BOTH, expand=True)
        
        # Icon and title
        header = tk.Frame(content, bg=colors['bg_main'])
        header.pack(fill=tk.X, pady=(0, 15))
        
        icon = tk.Label(
            header,
            text="🔑",
            bg=colors['bg_main'],
            font=('Segoe UI', 28)
        )
        icon.pack(side=tk.LEFT, padx=(0, 15))
        
        title_frame = tk.Frame(header, bg=colors['bg_main'])
        title_frame.pack(side=tk.LEFT, fill=tk.X)
        
        title = tk.Label(
            title_frame,
            text="API Key Required",
            bg=colors['bg_main'],
            fg=colors['accent_primary'],
            font=('Segoe UI', 14, 'bold')
        )
        title.pack(anchor=tk.W)
        
        subtitle = tk.Label(
            title_frame,
            text="Connect to Regolith.rocks for mining data",
            bg=colors['bg_main'],
            fg=colors['text_muted'],
            font=fonts['small']
        )
        subtitle.pack(anchor=tk.W)
        
        # Error message (if any)
        if error_msg:
            error_frame = tk.Frame(content, bg=colors['error'], padx=10, pady=8)
            error_frame.pack(fill=tk.X, pady=(0, 10))
            
            error_label = tk.Label(
                error_frame,
                text=f"⚠ {error_msg}",
                bg=colors['error'],
                fg='#ffffff',
                font=fonts['body']
            )
            error_label.pack(anchor=tk.W)
        
        # Instructions
        instructions = tk.Label(
            content,
            text="Enter your Regolith.rocks API key below.\nYou can get your key from your profile settings.",
            bg=colors['bg_main'],
            fg=colors['text_secondary'],
            font=fonts['body'],
            justify=tk.LEFT
        )
        instructions.pack(anchor=tk.W, pady=(0, 10))
        
        # API Key entry
        key_frame = tk.Frame(content, bg=colors['border'])
        key_frame.pack(fill=tk.X, pady=(0, 10))
        
        key_inner = tk.Frame(key_frame, bg=colors['bg_dark'], padx=2, pady=2)
        key_inner.pack(fill=tk.X, padx=1, pady=1)
        
        key_var = tk.StringVar(value=current_key)
        key_entry = tk.Entry(
            key_inner,
            textvariable=key_var,
            bg=colors['bg_dark'],
            fg=colors['text_primary'],
            font=fonts['mono'],
            relief='flat',
            insertbackground=colors['accent_primary'],
            show='•'
        )
        key_entry.pack(fill=tk.X, padx=8, pady=8)
        key_entry.focus_set()
        
        # Show/hide toggle
        show_var = tk.BooleanVar(value=False)
        
        def toggle_show():
            key_entry.configure(show='' if show_var.get() else '•')
        
        show_check = tk.Checkbutton(
            content,
            text="Show key",
            variable=show_var,
            bg=colors['bg_main'],
            fg=colors['text_muted'],
            font=fonts['small'],
            selectcolor=colors['bg_dark'],
            activebackground=colors['bg_main'],
            activeforeground=colors['text_muted'],
            command=toggle_show
        )
        show_check.pack(anchor=tk.W, pady=(0, 10))
        
        # Get API key link
        def open_api_page():
            import webbrowser
            webbrowser.open("https://regolith.rocks/profile/api")
        
        link = tk.Label(
            content,
            text="→ Get your API key at regolith.rocks/profile/api",
            bg=colors['bg_main'],
            fg=colors['cyan'],
            font=fonts['body'],
            cursor='hand2'
        )
        link.pack(anchor=tk.W, pady=(0, 15))
        link.bind('<Button-1>', lambda e: open_api_page())
        
        # Buttons
        btn_frame = tk.Frame(content, bg=colors['bg_main'])
        btn_frame.pack(fill=tk.X)
        
        def on_submit():
            key = key_var.get().strip()
            if key:
                result['key'] = key
                dialog.destroy()
            else:
                messagebox.showwarning("No Key", "Please enter an API key.", parent=dialog)
        
        def on_cancel():
            result['key'] = None
            dialog.destroy()
        
        submit_btn = tk.Button(
            btn_frame,
            text="✓  Validate & Continue",
            bg=colors['accent_primary'],
            fg=colors['bg_dark'],
            font=('Segoe UI', 10, 'bold'),
            relief='flat',
            padx=20,
            pady=8,
            cursor='hand2',
            command=on_submit
        )
        submit_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        cancel_btn = tk.Button(
            btn_frame,
            text="Exit",
            bg=colors['bg_light'],
            fg=colors['text_primary'],
            font=fonts['body'],
            relief='flat',
            padx=20,
            pady=8,
            cursor='hand2',
            command=on_cancel
        )
        cancel_btn.pack(side=tk.LEFT)
        
        # Bind Enter key
        dialog.bind('<Return>', lambda e: on_submit())
        dialog.bind('<Escape>', lambda e: on_cancel())
        
        # Wait for dialog
        dialog.wait_window()
        
        return result['key']
    
    def _on_close(self):
        """Handle window close."""
        self._stop_monitoring()
        self._save_config(show_message=False)
        self.root.destroy()


def main():
    _splash.set_status("Starting application...")
    _splash.close()  # Close splash before creating app (only one Tk root allowed)
    app = SCSignatureScannerApp()
    app.run()


if __name__ == "__main__":
    main()
