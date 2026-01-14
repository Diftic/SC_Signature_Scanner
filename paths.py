#!/usr/bin/env python3
"""
Path utilities for SC Signature Scanner.
Handles paths correctly for both development and PyInstaller frozen builds.
"""

import sys
from pathlib import Path


def get_base_path() -> Path:
    """Get the base path for the application.
    
    When running as a PyInstaller bundle, this returns the temp folder
    where files are extracted. When running normally, returns the
    directory containing this file.
    """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # Running as PyInstaller bundle
        return Path(sys._MEIPASS)
    else:
        # Running as normal Python script
        return Path(__file__).parent


def get_data_path() -> Path:
    """Get the path to the data directory."""
    return get_base_path() / "data"


def get_user_data_path() -> Path:
    """Get the path for user data (configs, cache, etc).
    
    This is always the directory containing the executable or script,
    so user data persists between runs.
    """
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller bundle - use exe directory
        return Path(sys.executable).parent
    else:
        # Running as normal Python script
        return Path(__file__).parent


def get_asset_path(asset_name: str) -> Path:
    """Get the path to an asset file."""
    return get_base_path() / "assets" / asset_name


def get_debug_path() -> Path:
    """Get the path for debug output.
    
    Returns a folder next to the executable (or script) for bug reports.
    """
    return get_user_data_path() / "SignatureScannerBugreport"
