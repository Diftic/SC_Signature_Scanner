#!/usr/bin/env python3
"""
Clean up utility for SC Signature Scanner.
Removes cache files, debug output, user config, API credentials, and deprecated files.

Author: Mallachi
"""

import json
import shutil
from pathlib import Path


def clean():
    """Remove cache files, debug output, user config, API credentials, and deprecated files.
    
    Cleans:
    - __pycache__ directories and .pyc/.pyo files
    - Debug output folders (SignatureScannerBugreport, debug_output)
    - scan_region.json (user-defined scan region)
    - config.json (settings + Regolith API key)
    - regolith_cache.json (cached Regolith.rocks data)
    - Deprecated config files (hud_config.json, identifier_config.json)
    - Deprecated source files (hud_calibration.py, identifier_window.py, jxr_converter.py)
    """
    root = Path(__file__).parent
    removed = 0
    
    print("SC Signature Scanner - Cleanup Utility")
    print("=" * 50)
    print()
    
    # ===== Python Cache =====
    print("[Cache Files]")
    
    # Remove __pycache__ directories
    for cache_dir in root.rglob("__pycache__"):
        shutil.rmtree(cache_dir)
        print(f"  Removed: {cache_dir.relative_to(root)}")
        removed += 1
    
    # Remove .pyc and .pyo files
    for pattern in ("*.pyc", "*.pyo"):
        for file in root.rglob(pattern):
            file.unlink()
            print(f"  Removed: {file.relative_to(root)}")
            removed += 1
    
    # ===== Debug Output =====
    print("\n[Debug Output]")
    
    # Get custom debug folder from config (if exists)
    config_file = root / "config.json"
    custom_debug_folder = None
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                cfg = json.load(f)
                custom_debug_folder = cfg.get('debug_folder', '')
        except (json.JSONDecodeError, IOError):
            pass
    
    # Remove default SignatureScannerBugreport folder
    default_debug_dir = root / "SignatureScannerBugreport"
    if default_debug_dir.exists():
        file_count = sum(1 for _ in default_debug_dir.iterdir())
        shutil.rmtree(default_debug_dir)
        print(f"  Removed: SignatureScannerBugreport/ ({file_count} files)")
        removed += 1
    
    # Also check for old debug_output folder (legacy)
    old_debug_dir = root / "debug_output"
    if old_debug_dir.exists():
        file_count = sum(1 for _ in old_debug_dir.iterdir())
        shutil.rmtree(old_debug_dir)
        print(f"  Removed: debug_output/ ({file_count} files)")
        removed += 1
    
    # Remove custom debug folder contents (if different from defaults)
    if custom_debug_folder:
        custom_path = Path(custom_debug_folder)
        if custom_path.exists() and custom_path != default_debug_dir and custom_path != old_debug_dir:
            file_count = sum(1 for _ in custom_path.iterdir())
            if file_count > 0:
                for item in custom_path.iterdir():
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item)
                print(f"  Cleared: {custom_path} ({file_count} items)")
                removed += 1
    
    # ===== User Config Files =====
    print("\n[User Config]")
    
    config_files = [
        ("scan_region.json", "Scan region config"),
        ("config.json", "Settings + API key"),
        ("regolith_cache.json", "Regolith.rocks cache"),
    ]
    
    for filename, description in config_files:
        filepath = root / filename
        if filepath.exists():
            filepath.unlink()
            print(f"  Removed: {filename} ({description})")
            removed += 1
    
    # ===== Deprecated Config Files =====
    print("\n[Deprecated Config]")
    
    deprecated_configs = [
        ("hud_config.json", "Old HUD calibration config"),
        ("identifier_config.json", "Old identifier window config"),
    ]
    
    for filename, description in deprecated_configs:
        filepath = root / filename
        if filepath.exists():
            filepath.unlink()
            print(f"  Removed: {filename} ({description})")
            removed += 1
    
    # ===== Deprecated Source Files =====
    print("\n[Deprecated Source Files]")
    
    deprecated_files = [
        ("hud_calibration.py", "Old circle-based calibration"),
        ("identifier_window.py", "Old overlay calibration window"),
        ("jxr_converter.py", "JXR to PNG converter (unused)"),
        ("tobii_tracker.py", "Tobii integration (deferred)"),
    ]
    
    for filename, description in deprecated_files:
        filepath = root / filename
        if filepath.exists():
            filepath.unlink()
            print(f"  Removed: {filename} ({description})")
            removed += 1
    
    # ===== Summary =====
    print()
    print("=" * 50)
    print(f"Cleaned {removed} items.")
    print()
    print("Note: Run this before building for distribution.")


if __name__ == "__main__":
    clean()
