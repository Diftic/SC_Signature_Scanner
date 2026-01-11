#!/usr/bin/env python3
"""
Overlay popup for SC Signature Scanner.
Shows signature identification results on top of the game.
"""

import tkinter as tk
from typing import List, Dict, Any, Optional, Tuple, Callable


class OverlayPopup:
    """Always-on-top overlay popup for showing signature results."""
    
    # Colors - matching RegolithTheme
    BG_COLOR = "#0d1117"      # Dark background
    BG_LIGHT = "#161b22"      # Card background
    BORDER_COLOR = "#30363d"  # Border
    FG_COLOR = "#e6edf3"      # Primary text
    ACCENT_COLOR = "#f0883e"  # Orange accent
    HEADER_COLOR = "#ffa657"  # Header orange
    SHIP_COLOR = "#58a6ff"    # Cyan for ships
    MINING_COLOR = "#f0883e"  # Orange for mining
    SALVAGE_COLOR = "#a371f7" # Purple for salvage
    MUTED_COLOR = "#8b949e"   # Muted text
    
    def __init__(self, position: Tuple[int, int] = None, duration: int = 10, scale: float = 1.0):
        """
        Initialize overlay.
        
        Args:
            position: (x, y) tuple for top-left corner, or None for center
            duration: seconds to display
            scale: font/size scale factor (0.5 to 2.0)
        """
        self.position = position  # (x, y) tuple
        self.duration = duration
        self.scale = max(0.5, min(2.0, scale))  # Clamp to valid range
        self.window: Optional[tk.Toplevel] = None
        self._after_id = None
        
        # Create hidden root if needed
        self._root = tk.Tk()
        self._root.withdraw()
    
    def set_position(self, x: int, y: int):
        """Set the overlay position."""
        self.position = (x, y)
    
    def show(self, signature: int, matches: List[Dict[str, Any]]):
        """Show the overlay with signature results."""
        # Cancel any pending hide
        if self._after_id and self.window:
            try:
                self.window.after_cancel(self._after_id)
            except:
                pass
        
        # Destroy existing window
        if self.window:
            self.window.destroy()
        
        # Create new overlay window
        self.window = tk.Toplevel(self._root)
        self.window.overrideredirect(True)  # No window decorations
        self.window.attributes('-topmost', True)  # Always on top
        self.window.attributes('-alpha', 0.95)  # Slight transparency
        self.window.configure(bg=self.BG_COLOR)
        
        # Build content
        self._build_content(signature, matches)
        
        # Position window
        self.window.update_idletasks()
        self._position_window()
        
        # Schedule hide using Tkinter's after() - thread safe
        self._after_id = self.window.after(self.duration * 1000, self._hide)
    
    def _scaled_font(self, family: str, base_size: int, weight: str = "") -> tuple:
        """Return a font tuple scaled by the scale factor."""
        scaled_size = int(base_size * self.scale)
        if weight:
            return (family, scaled_size, weight)
        return (family, scaled_size)
    
    def _build_content(self, signature: int, matches: List[Dict[str, Any]]):
        """Build the popup content."""
        # Scaled padding (increased horizontal for wider popup)
        pad_x = int(20 * self.scale)  # 10% wider
        pad_y = int(12 * self.scale)
        pad_small = int(8 * self.scale)
        
        # Outer border frame
        border = tk.Frame(self.window, bg=self.BORDER_COLOR, padx=1, pady=1)
        border.pack(fill=tk.BOTH, expand=True)
        
        frame = tk.Frame(border, bg=self.BG_COLOR, padx=pad_x, pady=pad_y)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Header with signature value
        header = tk.Label(
            frame,
            text=f"SIGNATURE: {signature:,}",
            font=self._scaled_font("Consolas", 14, "bold"),
            fg=self.HEADER_COLOR,
            bg=self.BG_COLOR
        )
        header.pack(anchor=tk.W, pady=(0, pad_small))
        
        # Separator
        sep = tk.Frame(frame, height=int(2 * self.scale), bg=self.ACCENT_COLOR)
        sep.pack(fill=tk.X, pady=(0, int(10 * self.scale)))
        
        # Results
        if not matches:
            no_match = tk.Label(
                frame,
                text="No matches found",
                font=self._scaled_font("Segoe UI", 10),
                fg=self.MUTED_COLOR,
                bg=self.BG_COLOR
            )
            no_match.pack(anchor=tk.W)
        else:
            # Show first match with composition
            match = matches[0]
            self._add_match_with_composition(frame, match)
        
        # Close hint
        hint = tk.Label(
            frame,
            text=f"Auto-hide in {self.duration}s",
            font=self._scaled_font("Segoe UI", 8),
            fg=self.MUTED_COLOR,
            bg=self.BG_COLOR
        )
        hint.pack(anchor=tk.E, pady=(int(10 * self.scale), 0))
    
    def _format_value(self, value: int) -> str:
        """Format aUEC value with K/M suffix."""
        if value >= 1_000_000:
            return f"{value / 1_000_000:.1f}M"
        elif value >= 1_000:
            return f"{value / 1_000:.0f}K"
        return str(value)
    
    def _add_match_with_composition(self, parent: tk.Frame, match: Dict[str, Any]):
        """Add a match row with mineral composition breakdown."""
        # Main container
        container = tk.Frame(parent, bg=self.BG_COLOR)
        container.pack(fill=tk.X, pady=int(3 * self.scale))
        
        # Rock type name and icon
        match_type = match.get('type', 'unknown')
        category = match.get('category', '')
        
        if category == 'asteroid' or 'Asteroid' in match.get('name', ''):
            color = self.MINING_COLOR
            icon = "🪨"
        elif category == 'deposit' or 'Deposit' in match.get('name', ''):
            color = self.MINING_COLOR
            icon = "⛏️"
        elif match_type == 'fps_mining' or category == 'fps_mining':
            color = "#a371f7"  # Purple for hand mining
            icon = "💎"
        elif match_type == 'ground_vehicle' or category == 'ground_vehicle':
            color = "#a371f7"  # Purple for vehicle mining
            icon = "💎"
        else:
            color = self.FG_COLOR
            icon = "📡"
        
        # Header row: Icon + Name + Value
        header_row = tk.Frame(container, bg=self.BG_COLOR)
        header_row.pack(fill=tk.X, pady=(0, int(3 * self.scale)))
        
        name = match.get('name', 'Unknown')
        name_label = tk.Label(
            header_row,
            text=f"{icon} {name}",
            font=self._scaled_font("Segoe UI", 12, "bold"),
            fg=color,
            bg=self.BG_COLOR,
            anchor=tk.W
        )
        name_label.pack(side=tk.LEFT)
        
        # Estimated value
        est_value = match.get('est_value')
        if est_value:
            value_label = tk.Label(
                header_row,
                text=f"~{self._format_value(est_value)} aUEC",
                font=self._scaled_font("Consolas", 11, "bold"),
                fg="#3fb950",  # Green for money
                bg=self.BG_COLOR
            )
            value_label.pack(side=tk.RIGHT)
        
        # Mining method indicator
        if category == 'asteroid':
            mining_method = "🚀 Ship Mining (mixed composition)"
            method_color = self.SHIP_COLOR
        elif category == 'deposit':
            mining_method = "🚀 Ship Mining (mixed composition)"
            method_color = self.SHIP_COLOR
        elif match_type == 'fps_mining' or category == 'fps_mining':
            mining_method = "💎 Hand Mining (100% single mineral)"
            method_color = "#a371f7"  # Purple
        elif match_type == 'ground_vehicle' or category == 'ground_vehicle':
            mining_method = "🚗 ROC Mining (100% single mineral)"
            method_color = "#a371f7"  # Purple
        else:
            mining_method = None
            method_color = self.MUTED_COLOR
        
        if mining_method:
            method_row = tk.Frame(container, bg=self.BG_COLOR)
            method_row.pack(fill=tk.X, pady=(0, int(5 * self.scale)))
            
            method_label = tk.Label(
                method_row,
                text=mining_method,
                font=self._scaled_font("Segoe UI", 9),
                fg=method_color,
                bg=self.BG_COLOR,
                anchor=tk.W
            )
            method_label.pack(side=tk.LEFT)
        
        # Composition table (only for mixed composition deposits)
        composition = match.get('composition', [])
        single_mineral = match.get('single_mineral', False)
        
        if single_mineral:
            # Single mineral deposit - show simple info
            mineral_name = match.get('mineral_name', 'Unknown')
            info_row = tk.Frame(container, bg=self.BG_LIGHT)
            info_row.pack(fill=tk.X, pady=(int(5 * self.scale), 0))
            
            tk.Label(
                info_row,
                text=f"Contains 100% {mineral_name}",
                font=self._scaled_font("Consolas", 10),
                fg="#3fb950",
                bg=self.BG_LIGHT,
                padx=10,
                pady=5
            ).pack(anchor=tk.W)
            
        elif composition:
            # Table header
            table_header = tk.Frame(container, bg=self.BG_LIGHT)
            table_header.pack(fill=tk.X, pady=(int(5 * self.scale), 0))
            
            tk.Label(
                table_header,
                text="Mineral",
                font=self._scaled_font("Consolas", 9, "bold"),
                fg=self.MUTED_COLOR,
                bg=self.BG_LIGHT,
                width=14,
                anchor=tk.W
            ).pack(side=tk.LEFT, padx=(5, 0))
            
            tk.Label(
                table_header,
                text="Prob",
                font=self._scaled_font("Consolas", 9, "bold"),
                fg=self.MUTED_COLOR,
                bg=self.BG_LIGHT,
                width=6,
                anchor=tk.E
            ).pack(side=tk.LEFT)
            
            tk.Label(
                table_header,
                text="Med%",
                font=self._scaled_font("Consolas", 9, "bold"),
                fg=self.MUTED_COLOR,
                bg=self.BG_LIGHT,
                width=6,
                anchor=tk.E
            ).pack(side=tk.LEFT)
            
            tk.Label(
                table_header,
                text="Value",
                font=self._scaled_font("Consolas", 9, "bold"),
                fg=self.MUTED_COLOR,
                bg=self.BG_LIGHT,
                width=8,
                anchor=tk.E
            ).pack(side=tk.LEFT, padx=(0, 5))
            
            # Table rows (show ALL minerals)
            for i, ore in enumerate(composition):
                row_bg = self.BG_LIGHT if i % 2 == 0 else self.BG_COLOR
                row = tk.Frame(container, bg=row_bg)
                row.pack(fill=tk.X)
                
                # Color code by UEX price per SCU
                ore_price = ore.get('price', 0)
                ore_value = ore.get('value', 0)
                
                if ore_price >= 25000:
                    ore_color = "#3fb950"      # Green - premium
                elif ore_price >= 10000:
                    ore_color = "#f0883e"      # Orange - medium
                else:
                    ore_color = "#f85149"      # Red - low
                
                # Mineral name
                tk.Label(
                    row,
                    text=ore.get('name', '?'),
                    font=self._scaled_font("Consolas", 9),
                    fg=ore_color,
                    bg=row_bg,
                    width=14,
                    anchor=tk.W
                ).pack(side=tk.LEFT, padx=(5, 0))
                
                # Probability (grey)
                prob = ore.get('prob', 0)
                prob_text = f"{prob:.0%}" if prob <= 1 else f"{prob:.1f}x"
                tk.Label(
                    row,
                    text=prob_text,
                    font=self._scaled_font("Consolas", 9),
                    fg=self.MUTED_COLOR,
                    bg=row_bg,
                    width=6,
                    anchor=tk.E
                ).pack(side=tk.LEFT)
                
                # Median percentage (grey)
                med_pct = ore.get('medPct', 0)
                tk.Label(
                    row,
                    text=f"{med_pct:.0%}",
                    font=self._scaled_font("Consolas", 9),
                    fg=self.MUTED_COLOR,
                    bg=row_bg,
                    width=6,
                    anchor=tk.E
                ).pack(side=tk.LEFT)
                
                # Value
                value_text = self._format_value(ore_value) if ore_value > 0 else "-"
                tk.Label(
                    row,
                    text=value_text,
                    font=self._scaled_font("Consolas", 9),
                    fg="#3fb950" if ore_value > 0 else self.MUTED_COLOR,
                    bg=row_bg,
                    width=8,
                    anchor=tk.E
                ).pack(side=tk.LEFT, padx=(0, 5))
            
            # Helper text
            helper_frame = tk.Frame(container, bg=self.BG_COLOR)
            helper_frame.pack(anchor=tk.W, pady=(int(5 * self.scale), 0))
            
            tk.Label(
                helper_frame,
                text="Prob = Probability that mineral will spawn",
                font=self._scaled_font("Segoe UI", 8),
                fg=self.MUTED_COLOR,
                bg=self.BG_COLOR
            ).pack(anchor=tk.W)
            
            tk.Label(
                helper_frame,
                text="Med% = Median amount of mineral if spawned",
                font=self._scaled_font("Segoe UI", 8),
                fg=self.MUTED_COLOR,
                bg=self.BG_COLOR
            ).pack(anchor=tk.W)
            
            tk.Label(
                helper_frame,
                text="Value = Average value of mineral if spawned",
                font=self._scaled_font("Segoe UI", 8),
                fg=self.MUTED_COLOR,
                bg=self.BG_COLOR
            ).pack(anchor=tk.W)
    
    def _add_match_row(self, parent: tk.Frame, rank: int, match: Dict[str, Any]):
        """Add a single match row."""
        row = tk.Frame(parent, bg=self.BG_COLOR)
        row.pack(fill=tk.X, pady=int(3 * self.scale))
        
        # Determine color based on type
        match_type = match.get('type', 'unknown')
        if match_type == 'ship':
            color = self.SHIP_COLOR
            icon = "🚀"
        elif match_type in ('asteroid', 'deposit', 'fps_mining', 'ground_vehicle'):
            color = self.MINING_COLOR
            icon = "⛏️"
        elif match_type == 'salvage':
            color = self.SALVAGE_COLOR
            icon = "🔧"
        else:
            color = self.FG_COLOR
            icon = "❓"
        
        # Rank
        rank_label = tk.Label(
            row,
            text=f"{rank}.",
            font=self._scaled_font("Consolas", 10),
            fg=self.MUTED_COLOR,
            bg=self.BG_COLOR,
            width=3
        )
        rank_label.pack(side=tk.LEFT)
        
        # Icon and name
        name = match.get('name', 'Unknown')
        confidence = match.get('confidence', 0)
        
        name_text = f"{icon} {name}"
        if match_type == 'ship' and match.get('facing'):
            name_text += f" ({match['facing']})"
        
        name_label = tk.Label(
            row,
            text=name_text,
            font=self._scaled_font("Segoe UI", 10),
            fg=color,
            bg=self.BG_COLOR,
            anchor=tk.W
        )
        name_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Detail column (count/confidence)
        if match_type in ('asteroid', 'deposit', 'fps_mining', 'ground_vehicle'):
            count = match.get('count', 1)
            detail = f"×{count}"
        elif match_type == 'salvage':
            panels = match.get('panels', 1)
            detail = f"{panels} panels"
        else:
            detail = f"{confidence:.0%}" if confidence else ""
        
        # Estimated value (for resources, not salvage - panels vary in size)
        est_value = match.get('est_value')
        if est_value and match_type != 'salvage':
            value_label = tk.Label(
                row,
                text=f"Est value: {self._format_value(est_value)}",
                font=self._scaled_font("Consolas", 9),
                fg="#3fb950",  # Green for money
                bg=self.BG_COLOR
            )
            value_label.pack(side=tk.RIGHT, padx=(5, 0))
        
        if detail:
            detail_label = tk.Label(
                row,
                text=detail,
                font=self._scaled_font("Consolas", 9),
                fg=self.MUTED_COLOR,
                bg=self.BG_COLOR
            )
            detail_label.pack(side=tk.RIGHT)
    
    def _position_window(self):
        """Position the window based on settings."""
        if self.position:
            # Use saved position
            x, y = self.position
            self.window.geometry(f"+{x}+{y}")
        else:
            # Default to center
            screen_width = self.window.winfo_screenwidth()
            screen_height = self.window.winfo_screenheight()
            window_width = self.window.winfo_width()
            window_height = self.window.winfo_height()
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
            self.window.geometry(f"+{x}+{y}")
    
    def _hide(self):
        """Hide the overlay."""
        if self.window:
            try:
                self.window.destroy()
            except:
                pass
            self.window = None
    
    def destroy(self):
        """Cleanup resources."""
        if self._after_id and self.window:
            try:
                self.window.after_cancel(self._after_id)
            except:
                pass
        if self.window:
            try:
                self.window.destroy()
            except:
                pass
            self.window = None
        try:
            self._root.destroy()
        except:
            pass


class PositionAdjuster:
    """Draggable window for setting overlay position."""
    
    # Colors - matching RegolithTheme
    BG_COLOR = "#0d1117"
    BG_LIGHT = "#161b22"
    BORDER_COLOR = "#30363d"
    ACCENT_COLOR = "#f0883e"
    CYAN = "#58a6ff"
    TEXT_PRIMARY = "#e6edf3"
    TEXT_MUTED = "#8b949e"
    SUCCESS = "#3fb950"
    ERROR = "#f85149"
    
    def __init__(self, parent: tk.Tk, current_position: Tuple[int, int] = None, 
                 on_save: Callable[[int, int], None] = None):
        """
        Create position adjuster window.
        
        Args:
            parent: Parent Tk window
            current_position: Starting (x, y) position
            on_save: Callback with (x, y) when saved
        """
        self.parent = parent
        self.on_save = on_save
        self._drag_start_x = 0
        self._drag_start_y = 0
        
        # Create window as Toplevel (not new Tk root)
        self.window = tk.Toplevel(parent)
        self.window.title("Adjust Overlay Position")
        self.window.overrideredirect(True)
        self.window.attributes('-topmost', True)
        self.window.attributes('-alpha', 0.95)
        self.window.configure(bg=self.BG_COLOR)
        
        # Build content
        self._build_content()
        
        # Position window
        self.window.update_idletasks()
        if current_position:
            x, y = current_position
        else:
            # Center by default
            screen_width = self.window.winfo_screenwidth()
            screen_height = self.window.winfo_screenheight()
            window_width = self.window.winfo_width()
            window_height = self.window.winfo_height()
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
        
        self.window.geometry(f"+{x}+{y}")
        
        # Bind drag events
        self.window.bind('<Button-1>', self._start_drag)
        self.window.bind('<B1-Motion>', self._on_drag)
        
        # Handle window close (X button or escape)
        self.window.protocol("WM_DELETE_WINDOW", self._cancel)
    
    def _build_content(self):
        """Build the adjuster UI."""
        # Outer border
        border = tk.Frame(self.window, bg=self.BORDER_COLOR, padx=1, pady=1)
        border.pack(fill=tk.BOTH, expand=True)
        
        frame = tk.Frame(border, bg=self.BG_COLOR, padx=20, pady=15)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title = tk.Label(
            frame,
            text="📍 OVERLAY POSITION",
            font=("Segoe UI", 12, "bold"),
            fg=self.ACCENT_COLOR,
            bg=self.BG_COLOR
        )
        title.pack(pady=(0, 8))
        
        # Instructions
        instructions = tk.Label(
            frame,
            text="Drag this window to desired position",
            font=("Segoe UI", 10),
            fg=self.TEXT_MUTED,
            bg=self.BG_COLOR
        )
        instructions.pack(pady=(0, 15))
        
        # Separator
        sep = tk.Frame(frame, height=2, bg=self.ACCENT_COLOR)
        sep.pack(fill=tk.X, pady=(0, 15))
        
        # Sample content (to show approximate size)
        sample_border = tk.Frame(frame, bg=self.BORDER_COLOR)
        sample_border.pack(fill=tk.X, pady=(0, 15))
        
        sample_inner = tk.Frame(sample_border, bg=self.BG_LIGHT, padx=10, pady=8)
        sample_inner.pack(fill=tk.X, padx=1, pady=1)
        
        sample = tk.Label(
            sample_inner,
            text="SIGNATURE: 8,500\n──────────────\n1. 🚀 Gladius (front)\n2. ⛏️ C-type Asteroid ×5\n3. 🔧 Salvage Panels (4)",
            font=("Consolas", 10),
            fg=self.TEXT_MUTED,
            bg=self.BG_LIGHT,
            justify=tk.LEFT
        )
        sample.pack(anchor=tk.W)
        
        # Position display
        self.pos_label = tk.Label(
            frame,
            text="Position: (0, 0)",
            font=("Consolas", 10),
            fg=self.CYAN,
            bg=self.BG_COLOR
        )
        self.pos_label.pack(pady=(0, 15))
        
        # Buttons
        btn_frame = tk.Frame(frame, bg=self.BG_COLOR)
        btn_frame.pack(fill=tk.X)
        
        save_btn = tk.Button(
            btn_frame,
            text="✓ Save Position",
            font=("Segoe UI", 10, "bold"),
            bg=self.SUCCESS,
            fg=self.BG_COLOR,
            activebackground="#4cc764",
            activeforeground=self.BG_COLOR,
            relief=tk.FLAT,
            padx=15,
            pady=8,
            cursor="hand2",
            command=self._save
        )
        save_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        cancel_btn = tk.Button(
            btn_frame,
            text="✗ Cancel",
            font=("Segoe UI", 10),
            bg=self.ERROR,
            fg=self.TEXT_PRIMARY,
            activebackground="#f97583",
            activeforeground=self.TEXT_PRIMARY,
            relief=tk.FLAT,
            padx=15,
            pady=8,
            cursor="hand2",
            command=self._cancel
        )
        cancel_btn.pack(side=tk.LEFT)
    
    def _start_drag(self, event):
        """Start dragging."""
        self._drag_start_x = event.x
        self._drag_start_y = event.y
    
    def _on_drag(self, event):
        """Handle drag motion."""
        x = self.window.winfo_x() + event.x - self._drag_start_x
        y = self.window.winfo_y() + event.y - self._drag_start_y
        self.window.geometry(f"+{x}+{y}")
        self.pos_label.config(text=f"Position: ({x}, {y})")
    
    def _save(self):
        """Save position and close."""
        x = self.window.winfo_x()
        y = self.window.winfo_y()
        self.window.destroy()
        if self.on_save:
            self.on_save(x, y)
    
    def _cancel(self):
        """Cancel and close."""
        self.window.destroy()
    
    def run(self):
        """Run the adjuster (blocking until closed)."""
        # Make modal - wait for this window to close
        self.window.grab_set()
        self.parent.wait_window(self.window)

