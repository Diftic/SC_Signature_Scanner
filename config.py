#!/usr/bin/env python3
"""
Configuration management for SC Signature Scanner.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional


class Config:
    """Handles loading and saving configuration."""
    
    def __init__(self, config_path: Path = None):
        if config_path is None:
            config_path = Path(__file__).parent / "config.json"
        self.config_path = config_path
    
    def load(self) -> Optional[Dict[str, Any]]:
        """Load configuration from file."""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading config: {e}")
        return None
    
    def save(self, config: Dict[str, Any]) -> bool:
        """Save configuration to file."""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a single config value."""
        cfg = self.load()
        if cfg:
            return cfg.get(key, default)
        return default
    
    def set(self, key: str, value: Any) -> bool:
        """Set a single config value."""
        cfg = self.load() or {}
        cfg[key] = value
        return self.save(cfg)
