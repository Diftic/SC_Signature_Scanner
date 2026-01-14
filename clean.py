#!/usr/bin/env python3
"""Clean up Python cache files and debug output."""

import json
import shutil
from pathlib import Path


def clean():
    """Remove cache files, debug output, user config, and API credentials.
    
    Cleans:
    - __pycache__ directories and .pyc/.pyo files
    - Debug output folders (SignatureScannerBugreport, debug_output)
    - scan_region.json (user-defined scan region)
    - config.json (settings + Regolith API key)
    - regolith_cache.json (cached Regolith.rocks data)
    - jxr_converter.py (deprecated)
    """
    root = Path(__file__).parent
    removed = 0
    
    # Remove __pycache__ directories
    for cache_dir in root.rglob("__pycache__"):
        shutil.rmtree(cache_dir)
        print(f"Removed: {cache_dir}")
        removed += 1
    
    # Remove .pyc and .pyo files
    for pattern in ("*.pyc", "*.pyo"):
        for file in root.rglob(pattern):
            file.unlink()
            print(f"Removed: {file}")
            removed += 1
    
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
        print(f"Removed: {default_debug_dir} ({file_count} files)")
        removed += 1
    
    # Also check for old debug_output folder (legacy)
    old_debug_dir = root / "debug_output"
    if old_debug_dir.exists():
        file_count = sum(1 for _ in old_debug_dir.iterdir())
        shutil.rmtree(old_debug_dir)
        print(f"Removed: {old_debug_dir} ({file_count} files)")
        removed += 1
    
    # Remove custom debug folder contents (if different from defaults)
    if custom_debug_folder:
        custom_path = Path(custom_debug_folder)
        if custom_path.exists() and custom_path != default_debug_dir and custom_path != old_debug_dir:
            file_count = sum(1 for _ in custom_path.iterdir())
            if file_count > 0:
                # Only remove contents, not the folder itself (user chose this location)
                for item in custom_path.iterdir():
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item)
                print(f"Cleared: {custom_path} ({file_count} items)")
                removed += 1
    
    # Remove scan_region.json
    scan_region_file = root / "scan_region.json"
    if scan_region_file.exists():
        scan_region_file.unlink()
        print(f"Removed: {scan_region_file}")
        removed += 1
    
    # Remove config.json
    if config_file.exists():
        config_file.unlink()
        print(f"Removed: {config_file}")
        removed += 1
    
    # Remove regolith_cache.json
    cache_file = root / "regolith_cache.json"
    if cache_file.exists():
        cache_file.unlink()
        print(f"Removed: {cache_file}")
        removed += 1
    
    # Remove jxr_converter.py (deprecated)
    jxr_file = root / "jxr_converter.py"
    if jxr_file.exists():
        jxr_file.unlink()
        print(f"Removed: {jxr_file}")
        removed += 1
    
    print(f"\nCleaned {removed} items.")


if __name__ == "__main__":
    clean()
