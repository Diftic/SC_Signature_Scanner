#!/usr/bin/env python3
"""
Signature scanner for SC Signature Scanner.
Handles OCR detection and signature matching.
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from PIL import Image

# OCR imports - will use pytesseract
try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False
    print("Warning: pytesseract not installed. OCR disabled.")


class SignatureScanner:
    """Scans screenshots for signature values and matches to database."""
    
    def __init__(self, db_path: Path):
        self.db = self._load_database(db_path)
        
        # OCR configuration - will be refined after screenshot analysis
        self.ocr_config = {
            'region': None,  # (x, y, width, height) - None = full image
            'scale': 2,  # Upscale for better OCR
            'threshold': 180,  # Binarization threshold
        }
        
        # Build lookup tables
        self._build_lookups()
    
    def _load_database(self, db_path: Path) -> Dict[str, Any]:
        """Load signature database."""
        if db_path.exists():
            with open(db_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def _build_lookups(self):
        """Build lookup tables for fast matching."""
        self.ship_lookup = {}  # dimension -> ship info
        self.minable_lookup = {}  # signature -> type info
        
        # Ships - indexed by max dimension
        for ship in self.db.get('ships', []):
            key = ship.get('max_dimension_m', 0)
            if key not in self.ship_lookup:
                self.ship_lookup[key] = []
            self.ship_lookup[key].append(ship)
        
        # Minables - indexed by base signature
        for category, types in self.db.get('minables', {}).items():
            for name, sig in types.items():
                if sig not in self.minable_lookup:
                    self.minable_lookup[sig] = []
                self.minable_lookup[sig].append({
                    'name': name,
                    'category': category,
                    'signature': sig
                })
    
    def scan_image(self, image_path: Path) -> Optional[Dict[str, Any]]:
        """Scan an image for signature values."""
        if not HAS_TESSERACT:
            return None
        
        try:
            # Load image
            img = Image.open(image_path)
            
            # Preprocess for OCR
            processed = self._preprocess_image(img)
            
            # Extract text
            text = pytesseract.image_to_string(
                processed,
                config='--psm 6 -c tessedit_char_whitelist=0123456789SIGsig:'
            )
            
            # Find signature value
            signature = self._extract_signature(text)
            
            if signature:
                matches = self.match_signature(signature)
                return {
                    'signature': signature,
                    'matches': matches,
                    'raw_text': text
                }
            
            return None
            
        except Exception as e:
            print(f"Error scanning image: {e}")
            return None
    
    def _preprocess_image(self, img: Image.Image) -> Image.Image:
        """Preprocess image for better OCR."""
        # Crop to region if configured
        if self.ocr_config['region']:
            x, y, w, h = self.ocr_config['region']
            img = img.crop((x, y, x + w, y + h))
        
        # Convert to grayscale
        img = img.convert('L')
        
        # Upscale
        scale = self.ocr_config['scale']
        if scale > 1:
            new_size = (img.width * scale, img.height * scale)
            img = img.resize(new_size, Image.Resampling.LANCZOS)
        
        # Binarize
        threshold = self.ocr_config['threshold']
        img = img.point(lambda p: 255 if p > threshold else 0)
        
        return img
    
    def _extract_signature(self, text: str) -> Optional[int]:
        """Extract signature value from OCR text."""
        # Common patterns for signature display
        patterns = [
            r'SIG[:\s]*(\d+)',  # "SIG: 1700" or "SIG 1700"
            r'SIGNATURE[:\s]*(\d+)',  # "SIGNATURE: 1700"
            r'(\d{3,6})',  # Just a number (3-6 digits)
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    value = int(match.group(1))
                    # Sanity check - signatures typically 600-100000
                    if 100 <= value <= 200000:
                        return value
                except ValueError:
                    continue
        
        return None
    
    def match_signature(self, signature: int) -> List[Dict[str, Any]]:
        """Match a signature value to possible targets."""
        matches = []
        
        # Check salvage panels (exact multiple of 2000)
        if signature % 2000 == 0 and signature >= 2000:
            panels = signature // 2000
            matches.append({
                'type': 'salvage',
                'name': 'Salvage Panels',
                'panels': panels,
                'confidence': 1.0
            })
        
        # Check mining signatures
        for base_sig, types in self.minable_lookup.items():
            if base_sig == 0:
                continue
            
            # Check if signature is a multiple of this base
            if signature % base_sig == 0:
                count = signature // base_sig
                if 1 <= count <= 50:  # Reasonable rock count
                    for t in types:
                        matches.append({
                            'type': t['category'],
                            'name': f"{t['name']}",
                            'count': count,
                            'base_signature': base_sig,
                            'confidence': 0.9 if count == 1 else 0.8
                        })
        
        # Check ship signatures (cross-section matching)
        ship_matches = self._match_ships(signature)
        matches.extend(ship_matches)
        
        # Sort by confidence
        matches.sort(key=lambda x: x.get('confidence', 0), reverse=True)
        
        return matches
    
    def _match_ships(self, signature: int) -> List[Dict[str, Any]]:
        """Match signature to ships based on cross-section."""
        matches = []
        
        # TODO: Ship signature matching logic
        # This will depend on how ship signatures appear in-game
        # For now, return empty - will implement after screenshot analysis
        
        return matches
    
    def set_ocr_region(self, x: int, y: int, width: int, height: int):
        """Set the OCR region to scan."""
        self.ocr_config['region'] = (x, y, width, height)
    
    def clear_ocr_region(self):
        """Clear OCR region (scan full image)."""
        self.ocr_config['region'] = None


# Test
if __name__ == "__main__":
    # Test signature matching
    scanner = SignatureScanner(Path("data/combat_analyst_db.json"))
    
    test_sigs = [1700, 3400, 5100, 1870, 2000, 10000, 1920, 8500]
    
    for sig in test_sigs:
        print(f"\nSignature: {sig}")
        matches = scanner.match_signature(sig)
        for m in matches[:5]:
            print(f"  - {m}")
