#!/usr/bin/env python3
"""Clean up Python cache files."""

import shutil
from pathlib import Path


def clean():
    """Remove __pycache__ directories and .pyc/.pyo files."""
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
    
    print(f"\nCleaned {removed} items.")


if __name__ == "__main__":
    clean()
