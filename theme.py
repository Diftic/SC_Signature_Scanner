#!/usr/bin/env python3
"""
UI Theme for SC Signature Scanner
Inspired by Regolith.Rocks and Star Citizen UI aesthetic
"""

import tkinter as tk
from tkinter import ttk


class RegolithTheme:
    """Dark sci-fi theme inspired by Regolith.Rocks"""
    
    # Color palette
    COLORS = {
        # Backgrounds
        'bg_dark': '#0d1117',       # Deepest background
        'bg_main': '#161b22',       # Main background
        'bg_light': '#21262d',      # Elevated surfaces
        'bg_hover': '#30363d',      # Hover state
        
        # Accent colors (orange/amber - Regolith signature)
        'accent_primary': '#f0883e',    # Primary orange
        'accent_secondary': '#ffa657',  # Lighter orange
        'accent_glow': '#ff6a00',       # Bright orange for emphasis
        
        # Secondary accent (cyan - Star Citizen feel)
        'cyan': '#58a6ff',
        'cyan_dim': '#388bfd',
        
        # Text
        'text_primary': '#e6edf3',   # Primary text
        'text_secondary': '#8b949e', # Secondary text
        'text_muted': '#6e7681',     # Muted text
        
        # Status colors
        'success': '#3fb950',
        'warning': '#d29922',
        'error': '#f85149',
        
        # Borders
        'border': '#30363d',
        'border_light': '#484f58',
    }
    
    # Fonts
    FONTS = {
        'heading': ('Segoe UI', 14, 'bold'),
        'subheading': ('Segoe UI', 11, 'bold'),
        'body': ('Segoe UI', 10),
        'small': ('Segoe UI', 9),
        'mono': ('Consolas', 10),
        'mono_small': ('Consolas', 9),
        'title': ('Segoe UI', 18, 'bold'),
    }
    
    @classmethod
    def apply(cls, root: tk.Tk):
        """Apply theme to root window and configure ttk styles."""
        # Configure root
        root.configure(bg=cls.COLORS['bg_main'])
        
        # Create ttk style
        style = ttk.Style()
        style.theme_use('clam')  # Base theme that allows customization
        
        # === Frame styles ===
        style.configure(
            'TFrame',
            background=cls.COLORS['bg_main']
        )
        
        style.configure(
            'Card.TFrame',
            background=cls.COLORS['bg_light'],
            relief='flat'
        )
        
        # === Label styles ===
        style.configure(
            'TLabel',
            background=cls.COLORS['bg_main'],
            foreground=cls.COLORS['text_primary'],
            font=cls.FONTS['body']
        )
        
        style.configure(
            'Heading.TLabel',
            background=cls.COLORS['bg_main'],
            foreground=cls.COLORS['accent_primary'],
            font=cls.FONTS['heading']
        )
        
        style.configure(
            'Title.TLabel',
            background=cls.COLORS['bg_main'],
            foreground=cls.COLORS['accent_primary'],
            font=cls.FONTS['title']
        )
        
        style.configure(
            'Muted.TLabel',
            background=cls.COLORS['bg_main'],
            foreground=cls.COLORS['text_muted'],
            font=cls.FONTS['small']
        )
        
        style.configure(
            'Warning.TLabel',
            background=cls.COLORS['bg_main'],
            foreground=cls.COLORS['warning'],
            font=cls.FONTS['body']
        )
        
        style.configure(
            'Success.TLabel',
            background=cls.COLORS['bg_main'],
            foreground=cls.COLORS['success'],
            font=cls.FONTS['body']
        )
        
        style.configure(
            'Card.TLabel',
            background=cls.COLORS['bg_light'],
            foreground=cls.COLORS['text_primary'],
            font=cls.FONTS['body']
        )
        
        # === Button styles ===
        style.configure(
            'TButton',
            background=cls.COLORS['bg_light'],
            foreground=cls.COLORS['text_primary'],
            font=cls.FONTS['body'],
            padding=(15, 8),
            borderwidth=1,
            relief='flat'
        )
        
        style.map(
            'TButton',
            background=[
                ('active', cls.COLORS['bg_hover']),
                ('pressed', cls.COLORS['accent_primary'])
            ],
            foreground=[
                ('pressed', cls.COLORS['bg_dark'])
            ]
        )
        
        style.configure(
            'Accent.TButton',
            background=cls.COLORS['accent_primary'],
            foreground=cls.COLORS['bg_dark'],
            font=('Segoe UI', 10, 'bold'),
            padding=(15, 8)
        )
        
        style.map(
            'Accent.TButton',
            background=[
                ('active', cls.COLORS['accent_secondary']),
                ('pressed', cls.COLORS['accent_glow'])
            ]
        )
        
        style.configure(
            'Success.TButton',
            background=cls.COLORS['success'],
            foreground=cls.COLORS['bg_dark'],
            font=('Segoe UI', 10, 'bold'),
            padding=(15, 8)
        )
        
        style.map(
            'Success.TButton',
            background=[
                ('active', '#4cc764'),
                ('pressed', '#2ea043')
            ]
        )
        
        # === Entry styles ===
        style.configure(
            'TEntry',
            fieldbackground=cls.COLORS['bg_dark'],
            foreground=cls.COLORS['text_primary'],
            insertcolor=cls.COLORS['accent_primary'],
            padding=8
        )
        
        # === LabelFrame styles ===
        style.configure(
            'TLabelframe',
            background=cls.COLORS['bg_main'],
            foreground=cls.COLORS['text_primary'],
            bordercolor=cls.COLORS['border'],
            relief='flat'
        )
        
        style.configure(
            'TLabelframe.Label',
            background=cls.COLORS['bg_main'],
            foreground=cls.COLORS['accent_primary'],
            font=cls.FONTS['subheading']
        )
        
        # === Notebook (tabs) styles ===
        style.configure(
            'TNotebook',
            background=cls.COLORS['bg_dark'],
            borderwidth=0,
            tabmargins=[0, 0, 0, 0]
        )
        
        style.configure(
            'TNotebook.Tab',
            background=cls.COLORS['bg_light'],
            foreground=cls.COLORS['text_secondary'],
            padding=[20, 10],
            font=cls.FONTS['body']
        )
        
        style.map(
            'TNotebook.Tab',
            background=[
                ('selected', cls.COLORS['bg_main']),
                ('active', cls.COLORS['bg_hover'])
            ],
            foreground=[
                ('selected', cls.COLORS['accent_primary']),
                ('active', cls.COLORS['text_primary'])
            ]
        )
        
        # === Spinbox styles ===
        style.configure(
            'TSpinbox',
            fieldbackground=cls.COLORS['bg_dark'],
            foreground=cls.COLORS['text_primary'],
            arrowcolor=cls.COLORS['accent_primary'],
            padding=5
        )
        
        # === Scrollbar styles ===
        style.configure(
            'TScrollbar',
            background=cls.COLORS['bg_light'],
            troughcolor=cls.COLORS['bg_dark'],
            arrowcolor=cls.COLORS['text_muted']
        )
        
        style.map(
            'TScrollbar',
            background=[('active', cls.COLORS['bg_hover'])]
        )
        
        # === Combobox styles ===
        style.configure(
            'TCombobox',
            fieldbackground=cls.COLORS['bg_dark'],
            background=cls.COLORS['bg_light'],
            foreground=cls.COLORS['text_primary'],
            arrowcolor=cls.COLORS['accent_primary'],
            padding=5
        )
        
        style.map(
            'TCombobox',
            fieldbackground=[('readonly', cls.COLORS['bg_dark'])],
            selectbackground=[('readonly', cls.COLORS['accent_primary'])]
        )
        
        # Configure combobox dropdown
        root.option_add('*TCombobox*Listbox.background', cls.COLORS['bg_dark'])
        root.option_add('*TCombobox*Listbox.foreground', cls.COLORS['text_primary'])
        root.option_add('*TCombobox*Listbox.selectBackground', cls.COLORS['accent_primary'])
        root.option_add('*TCombobox*Listbox.selectForeground', cls.COLORS['bg_dark'])
        
        return style
    
    @classmethod
    def create_styled_text(cls, parent, **kwargs) -> tk.Text:
        """Create a styled Text widget."""
        defaults = {
            'bg': cls.COLORS['bg_dark'],
            'fg': cls.COLORS['text_primary'],
            'insertbackground': cls.COLORS['accent_primary'],
            'selectbackground': cls.COLORS['accent_primary'],
            'selectforeground': cls.COLORS['bg_dark'],
            'font': cls.FONTS['mono_small'],
            'relief': 'flat',
            'borderwidth': 0,
            'padx': 10,
            'pady': 10
        }
        defaults.update(kwargs)
        return tk.Text(parent, **defaults)
    
    @classmethod
    def create_separator(cls, parent, horizontal=True) -> tk.Frame:
        """Create a styled separator line."""
        sep = tk.Frame(
            parent,
            bg=cls.COLORS['border'],
            height=1 if horizontal else None,
            width=None if horizontal else 1
        )
        return sep
    
    @classmethod
    def create_accent_separator(cls, parent) -> tk.Frame:
        """Create an accent-colored separator line."""
        sep = tk.Frame(
            parent,
            bg=cls.COLORS['accent_primary'],
            height=2
        )
        return sep
    
    @classmethod
    def create_card(cls, parent, **kwargs) -> tk.Frame:
        """Create a card-style container."""
        defaults = {
            'bg': cls.COLORS['bg_light'],
            'padx': 15,
            'pady': 15
        }
        defaults.update(kwargs)
        
        # Outer frame for border effect
        outer = tk.Frame(parent, bg=cls.COLORS['border'])
        inner = tk.Frame(outer, **defaults)
        inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        
        return inner, outer


# Banner widget
class WarningBanner(tk.Frame):
    """Stylized warning banner."""
    
    def __init__(self, parent, text: str, **kwargs):
        super().__init__(parent, bg=RegolithTheme.COLORS['bg_dark'], **kwargs)
        
        # Warning icon and text
        inner = tk.Frame(self, bg='#3d2a00', padx=15, pady=8)
        inner.pack(fill=tk.X, padx=1, pady=1)
        
        # Add border effect
        self.configure(bg='#664400')
        
        label = tk.Label(
            inner,
            text=f"⚠️  {text}",
            bg='#3d2a00',
            fg='#ffa657',
            font=RegolithTheme.FONTS['body']
        )
        label.pack()


# Status indicator
class StatusIndicator(tk.Frame):
    """Status indicator with icon."""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=RegolithTheme.COLORS['bg_main'], **kwargs)
        
        self.icon = tk.Label(
            self,
            text="⏹",
            bg=RegolithTheme.COLORS['bg_main'],
            fg=RegolithTheme.COLORS['text_muted'],
            font=('Segoe UI', 14)
        )
        self.icon.pack(side=tk.LEFT, padx=(0, 8))
        
        self.label = tk.Label(
            self,
            text="Ready",
            bg=RegolithTheme.COLORS['bg_main'],
            fg=RegolithTheme.COLORS['text_secondary'],
            font=RegolithTheme.FONTS['body']
        )
        self.label.pack(side=tk.LEFT)
    
    def set_active(self):
        """Set status to active/monitoring."""
        self.icon.configure(text="●", fg=RegolithTheme.COLORS['success'])
        self.label.configure(
            text="Monitoring Active",
            fg=RegolithTheme.COLORS['success']
        )
    
    def set_inactive(self):
        """Set status to inactive/stopped."""
        self.icon.configure(text="⏹", fg=RegolithTheme.COLORS['text_muted'])
        self.label.configure(
            text="Stopped",
            fg=RegolithTheme.COLORS['text_secondary']
        )
    
    def set_ready(self):
        """Set status to ready."""
        self.icon.configure(text="○", fg=RegolithTheme.COLORS['cyan'])
        self.label.configure(
            text="Ready",
            fg=RegolithTheme.COLORS['text_secondary']
        )
