#!/usr/bin/env python3
"""
Screenshot folder monitoring for SC Signature Scanner.
Uses watchdog to detect new screenshots.
"""

import time
import threading
from pathlib import Path
from typing import Callable, Set, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent


class ScreenshotHandler(FileSystemEventHandler):
    """Handler for new screenshot files."""
    
    VALID_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.bmp'}
    
    def __init__(self, callback: Callable[[Path], None], ignore_files: Set[Path] = None):
        super().__init__()
        self.callback = callback
        self.ignore_files = ignore_files or set()
        self._processing = set()  # Prevent duplicate processing
    
    def on_created(self, event: FileCreatedEvent):
        """Called when a new file is created."""
        if event.is_directory:
            return
        
        filepath = Path(event.src_path)
        
        # Check extension
        if filepath.suffix.lower() not in self.VALID_EXTENSIONS:
            return
        
        # Check if should ignore
        if filepath in self.ignore_files:
            return
        
        # Prevent duplicate processing
        if filepath in self._processing:
            return
        self._processing.add(filepath)
        
        # Wait for file to be fully written
        self._wait_for_file(filepath)
        
        # Process
        try:
            self.callback(filepath)
        finally:
            self._processing.discard(filepath)
    
    def _wait_for_file(self, filepath: Path, timeout: float = 5.0):
        """Wait for file to be fully written."""
        start = time.time()
        last_size = -1
        
        while time.time() - start < timeout:
            try:
                current_size = filepath.stat().st_size
                if current_size == last_size and current_size > 0:
                    # Size stable, file is ready
                    time.sleep(0.1)  # Small extra delay
                    return
                last_size = current_size
            except (OSError, FileNotFoundError):
                pass
            time.sleep(0.2)


class ScreenshotMonitor:
    """Monitors a folder for new screenshots."""
    
    def __init__(self, folder: str, callback: Callable[[Path], None], ignore_existing: Set[Path] = None):
        self.folder = Path(folder)
        self.callback = callback
        self.ignore_existing = ignore_existing or set()
        
        self.observer: Optional[Observer] = None
        self._running = False
    
    def start(self):
        """Start monitoring the folder."""
        if self._running:
            return
        
        handler = ScreenshotHandler(
            callback=self.callback,
            ignore_files=self.ignore_existing
        )
        
        self.observer = Observer()
        self.observer.schedule(handler, str(self.folder), recursive=False)
        self.observer.start()
        self._running = True
    
    def stop(self):
        """Stop monitoring."""
        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=2)
            self.observer = None
        self._running = False
    
    @property
    def is_running(self) -> bool:
        return self._running
