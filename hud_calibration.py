#!/usr/bin/env python3
"""
HUD Calibration for SC Signature Scanner.
Simple config-based calibration - no overlay needed.
"""

import json
from pathlib import Path
from typing import Tuple, Optional


CONFIG_FILE = Path(__file__).parent / "hud_config.json"

# Default signature offset multipliers (relative to circle diameter)
DEFAULT_CONFIG = {
    'circle_x': None,          # Circle center X (screen pixels)
    'circle_y': None,          # Circle center Y (screen pixels)
    'circle_diameter': 50,     # Circle diameter in pixels
    'offset_x_mult': 5.0,      # Signature X offset multiplier
    'offset_y_mult': -3.5,     # Signature Y offset multiplier  
    'padding_mult': 1.5,       # Scan region padding multiplier
}


def load_config() -> dict:
    """Load HUD configuration."""
    config = DEFAULT_CONFIG.copy()
    
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                saved = json.load(f)
                config.update(saved)
        except (json.JSONDecodeError, IOError):
            pass
    
    return config


def save_config(config: dict):
    """Save HUD configuration."""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)
    print(f"Saved to {CONFIG_FILE}")


def is_configured() -> bool:
    """Check if HUD has been calibrated."""
    config = load_config()
    return config.get('circle_x') is not None and config.get('circle_y') is not None


def get_circle_position() -> Optional[Tuple[int, int, int]]:
    """Get calibrated circle position.
    
    Returns:
        Tuple of (center_x, center_y, diameter) or None if not configured.
    """
    config = load_config()
    
    if config.get('circle_x') is None or config.get('circle_y') is None:
        return None
    
    return (
        config['circle_x'],
        config['circle_y'],
        config['circle_diameter']
    )


def get_signature_region() -> Optional[Tuple[int, int, int, int]]:
    """Calculate signature scan region from calibration.
    
    Returns:
        Tuple of (x1, y1, x2, y2) or None if not configured.
    """
    config = load_config()
    
    if config.get('circle_x') is None:
        return None
    
    cx = config['circle_x']
    cy = config['circle_y']
    diameter = config['circle_diameter']
    
    # Signature center (offset from circle)
    sig_x = cx + int(diameter * config['offset_x_mult'])
    sig_y = cy + int(diameter * config['offset_y_mult'])
    
    # Padding
    padding = int(diameter * config['padding_mult'])
    
    return (
        sig_x - padding,
        sig_y - padding,
        sig_x + padding,
        sig_y + padding
    )


def calibrate_interactive():
    """Interactive calibration wizard."""
    print("=" * 50)
    print("HUD CALIBRATION")
    print("=" * 50)
    print()
    print("Instructions:")
    print("1. Take a screenshot of Star Citizen")
    print("2. Open it in an image viewer (Paint, IrfanView, etc.)")
    print("3. Find the targeting circle (round reticle)")
    print("4. Note the X,Y coordinates of its CENTER")
    print("5. Estimate its diameter in pixels")
    print()
    
    config = load_config()
    
    # Show current values
    if config.get('circle_x') is not None:
        print(f"Current config: ({config['circle_x']}, {config['circle_y']}), ⌀{config['circle_diameter']}px")
        print()
    
    # Get circle center X
    while True:
        try:
            current = config.get('circle_x', '')
            prompt = f"Circle center X [{current}]: " if current else "Circle center X: "
            inp = input(prompt).strip()
            
            if inp == '' and current:
                break
            
            config['circle_x'] = int(inp)
            break
        except ValueError:
            print("Please enter a number")
    
    # Get circle center Y
    while True:
        try:
            current = config.get('circle_y', '')
            prompt = f"Circle center Y [{current}]: " if current else "Circle center Y: "
            inp = input(prompt).strip()
            
            if inp == '' and current:
                break
            
            config['circle_y'] = int(inp)
            break
        except ValueError:
            print("Please enter a number")
    
    # Get diameter
    while True:
        try:
            current = config.get('circle_diameter', 50)
            inp = input(f"Circle diameter [{current}]: ").strip()
            
            if inp == '':
                break
            
            config['circle_diameter'] = int(inp)
            break
        except ValueError:
            print("Please enter a number")
    
    # Save
    save_config(config)
    
    # Show result
    print()
    print("Calibration saved!")
    print(f"  Circle: ({config['circle_x']}, {config['circle_y']})")
    print(f"  Diameter: {config['circle_diameter']}px")
    
    region = get_signature_region()
    if region:
        print(f"  Signature scan region: {region}")

