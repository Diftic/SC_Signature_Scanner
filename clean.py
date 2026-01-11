#!/usr/bin/env python3
"""Clean up Python cache files."""

import shutil
from pathlib import Path


def clean():
    """Remove __pycache__ directories, .pyc/.pyo files, and config.json."""
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
    
    # Remove config.json
    config_file = root / "config.json"
    if config_file.exists():
        config_file.unlink()
        print(f"Removed: {config_file}")
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
