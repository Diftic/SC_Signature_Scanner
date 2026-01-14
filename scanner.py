#!/usr/bin/env python3
"""
Signature scanner for SC Signature Scanner.
Detects signature values from Star Citizen screenshots using OCR.

Requires a scan region to be configured in Settings.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from PIL import Image, ImageOps
import numpy as np
import cv2

import paths

try:
    import pricing
    HAS_PRICING = True
except ImportError:
    HAS_PRICING = False

# Import region selector for scan region
try:
    import region_selector
    HAS_REGION_SELECTOR = True
except ImportError:
    HAS_REGION_SELECTOR = False

try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False
    print("Warning: pytesseract not installed. OCR disabled.")


# Signature to rock type mapping for pricing
# Space deposits (asteroids): Ship mining, mixed composition
# Surface deposits: Ship mining, mixed composition  
# Ground deposits: ROC/FPS mining, 100% single mineral (not in this map - handled separately)
SIGNATURE_TO_ROCK_TYPE = {
    # Space deposits (Asteroids)
    1660: ('ITYPE', 'space_deposit'),
    1700: ('CTYPE', 'space_deposit'),
    1720: ('STYPE', 'space_deposit'),
    1750: ('PTYPE', 'space_deposit'),
    1850: ('MTYPE', 'space_deposit'),
    1870: ('QTYPE', 'space_deposit'),
    1900: ('ETYPE', 'space_deposit'),
    # Surface deposits
    1730: ('SHALE', 'surface_deposit'),
    1770: ('FELSIC', 'surface_deposit'),
    1790: ('OBSIDIAN', 'surface_deposit'),
    1800: ('ATACAMITE', 'surface_deposit'),
    1820: ('QUARTZITE', 'surface_deposit'),
    1840: ('GNEISS', 'surface_deposit'),
    1920: ('GRANITE', 'surface_deposit'),
    1950: ('IGNEOUS', 'surface_deposit'),
}


class SignatureScanner:
    """Scans screenshots for signature values using HUD circle detection."""
    
    def __init__(self, db_path: Path, system: str = 'STANTON'):
        self.db = self._load_database(db_path)
        self.system = system.upper()  # Default system for pricing
        self._build_lookups()
        
        self.debug_mode = False
        self.debug_dir = paths.get_debug_path()
        self.last_debug_info = {}
        self._debug_prefix = ""  # Timestamp prefix for debug files
        
        # OCR mode: 'raw', 'adaptive', or 'hybrid'
        self.ocr_mode = 'hybrid'
    
    def _debug_path(self, filename: str) -> Path:
        """Generate debug file path with timestamp prefix.
        
        Args:
            filename: Base filename like "00_original.png"
            
        Returns:
            Full path like debug_output/20260112_143052_00_original.png
        """
        return self.debug_dir / f"{self._debug_prefix}{filename}"
    
    def scan_image(self, image_path: Path) -> Optional[Dict[str, Any]]:
        """Scan an image for signature values.
        
        Requires fixed scan region (configured in Settings).
        """
        if not HAS_TESSERACT:
            return {'error': 'Tesseract not installed'}
        
        self.last_debug_info = {
            'image_path': str(image_path),
            'debug_files': [],
            'method': None
        }
        
        # Generate timestamp prefix for this scan session
        self._debug_prefix = datetime.now().strftime("%Y%m%d_%H%M%S_")
        
        try:
            img = self._load_image(image_path)
            if img is None:
                return {'error': f'Failed to load image: {image_path.name}'}
            
            width, height = img.size
            self.last_debug_info['image_size'] = (width, height)
            
            if self.debug_mode:
                self.debug_dir.mkdir(exist_ok=True)
                img.save(self._debug_path("00_original.png"))
                self.last_debug_info['debug_files'].append(f"{self._debug_prefix}00_original.png")
            
            # Check for fixed region
            if HAS_REGION_SELECTOR and region_selector.is_configured():
                result = self._scan_with_fixed_region(img, width, height)
                if result:
                    self.last_debug_info['method'] = 'fixed_region'
                    return result
                if self.debug_mode:
                    print("[DEBUG] Fixed region scan failed - no signature found")
                return {'error': 'No signature detected in scan region'}
            
            # No scan region configured
            return {'error': 'Scan region not configured. Define it in Settings.'}
            
        except Exception as e:
            if self.debug_mode:
                import traceback
                with open(self._debug_path("99_error.txt"), 'w') as f:
                    f.write(traceback.format_exc())
            return {'error': str(e)}
    
    def _scan_with_fixed_region(self, img: Image.Image, width: int, height: int) -> Optional[Dict[str, Any]]:
        """Scan using pre-configured fixed region."""
        region = region_selector.load_region()
        if not region:
            return None
        
        x1, y1, x2, y2 = region
        
        # Validate region is within image bounds
        x1 = max(0, min(x1, width - 1))
        y1 = max(0, min(y1, height - 1))
        x2 = max(0, min(x2, width))
        y2 = max(0, min(y2, height))
        
        if x2 <= x1 or y2 <= y1:
            if self.debug_mode:
                print(f"[DEBUG] Invalid fixed region: ({x1}, {y1}) to ({x2}, {y2})")
            return None
        
        if self.debug_mode:
            print(f"[DEBUG] Using fixed region: ({x1}, {y1}) to ({x2}, {y2})")
        
        return self._scan_region(img, x1, y1, x2, y2, "fixed")
    
    def _scan_region(self, img: Image.Image, x1: int, y1: int, x2: int, y2: int, 
                     method: str) -> Optional[Dict[str, Any]]:
        """Scan a specific region for signature values."""
        if self.debug_mode:
            from PIL import ImageDraw
            debug_img = img.copy()
            draw = ImageDraw.Draw(debug_img)
            draw.rectangle([x1, y1, x2, y2], outline='#00FF00', width=3)
            debug_img.save(self._debug_path(f"02_{method}_region.png"))
            self.last_debug_info['debug_files'].append(f"{self._debug_prefix}02_{method}_region.png")
        
        # Crop region
        sig_crop = img.crop((x1, y1, x2, y2))
        
        if self.debug_mode:
            sig_crop.save(self._debug_path("03_sig_crop.png"))
            self.last_debug_info['debug_files'].append(f"{self._debug_prefix}03_sig_crop.png")
        
        # Determine OCR modes to try based on setting
        if self.ocr_mode == 'hybrid':
            modes_to_try = ['raw', 'adaptive']
        else:
            modes_to_try = [self.ocr_mode]
        
        signatures = []
        ocr_text = ""
        ocr_mode_used = ""
        
        for mode in modes_to_try:
            enhanced = self._enhance_for_ocr(sig_crop, mode=mode)
            
            if self.debug_mode:
                enhanced.save(self._debug_path(f"04_enhanced_{mode}.png"))
                self.last_debug_info['debug_files'].append(f"{self._debug_prefix}04_enhanced_{mode}.png")
            
            # OCR
            sigs, text = self._ocr_signature(enhanced, mode_label=mode)
            
            if self.debug_mode:
                print(f"[DEBUG] OCR ({mode}): text='{text}' signatures={sigs}")
            
            if sigs:
                signatures = sigs
                ocr_text = text
                ocr_mode_used = mode
                break  # Found signatures, stop trying
            
            # Keep last attempt's text for debug
            if not ocr_text:
                ocr_text = text
                ocr_mode_used = mode
        
        if self.debug_mode:
            with open(self._debug_path("99_summary.txt"), 'w') as f:
                f.write(f"Method: {method}\n")
                f.write(f"Region: ({x1}, {y1}) - ({x2}, {y2})\n")
                f.write(f"OCR mode: {self.ocr_mode} (used: {ocr_mode_used})\n")
                f.write(f"OCR text: {ocr_text}\n")
                f.write(f"Signatures found: {signatures}\n")
        
        if signatures:
            primary_sig = max(signatures)
            matches = self.match_signature(primary_sig)
            return {
                'signature': primary_sig,
                'all_signatures': list(set(signatures)),
                'matches': matches,
                'method': method,
                'ocr_mode': ocr_mode_used,
                'debug': self.last_debug_info if self.debug_mode else None
            }
        
        return None
    
    def _enhance_for_ocr(self, img: Image.Image, mode: str = 'raw') -> Image.Image:
        """Enhance image for OCR.
        
        Args:
            img: Cropped region containing signature
            mode: 'raw' (minimal processing) or 'adaptive' (adaptive threshold)
        
        Returns:
            Processed grayscale image ready for OCR
        """
        if mode == 'raw':
            # Minimal processing - just grayscale, preserve anti-aliasing
            return img.convert('L')
        
        elif mode == 'adaptive':
            # Adaptive thresholding - handles uneven backgrounds
            gray = np.array(img.convert('L'))
            
            # Adaptive threshold with Gaussian method
            # Block size 11, constant 2 - tuned for game text
            binary = cv2.adaptiveThreshold(
                gray,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                11,  # Block size (must be odd)
                2    # Constant subtracted from mean
            )
            
            return Image.fromarray(binary, mode='L')
        
        else:
            # Fallback to raw
            return img.convert('L')
    
    def _load_database(self, db_path: Path) -> Dict[str, Any]:
        """Load signature database."""
        if db_path.exists():
            with open(db_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def _build_lookups(self):
        """Build lookup tables for fast matching."""
        self.ship_lookup = {}
        for ship in self.db.get('ships', []):
            cs = ship.get('cross_section_m', {})
            for axis in ['x', 'y', 'z']:
                dim = cs.get(axis, 0)
                if dim > 0:
                    key = int(dim * 1000)
                    if key not in self.ship_lookup:
                        self.ship_lookup[key] = []
                    self.ship_lookup[key].append({
                        'name': ship['name'],
                        'manufacturer': ship.get('manufacturer', ''),
                        'dimension': dim,
                        'axis': axis,
                        'max_dimension': ship.get('max_dimension_m', 0)
                    })
        
        self.signature_lookup = {}
        for sig_str, desc in self.db.get('signature_lookup', {}).items():
            try:
                self.signature_lookup[int(sig_str)] = desc
            except ValueError:
                pass
        
        # Build minable signatures from space deposits (asteroids) and surface deposits
        self.minable_signatures = {}
        minables = self.db.get('minables', {})
        
        # Space deposits (asteroids) and surface deposits - ship mining
        for category in ['space_deposits', 'surface_deposits']:
            items = minables.get(category, {})
            for name, sig in items.items():
                if name.startswith('_'):  # Skip metadata fields
                    continue
                if isinstance(sig, (int, float)):
                    self.minable_signatures[int(sig)] = {'name': name, 'category': category}
        
        # Ground deposits - new unified structure with small/large variants
        ground = minables.get('ground_deposits', {})
        small_config = ground.get('small', {})
        large_config = ground.get('large', {})
        
        self.ground_deposit_small_base = small_config.get('_base_signature', 120)
        self.ground_deposit_large_base = large_config.get('_base_signature', 620)
        self.ground_deposit_minerals = ground.get('minerals', [])
    
    def _ocr_signature(self, mask: Image.Image, mode_label: str = '') -> Tuple[List[int], str]:
        """OCR the signature mask and extract numbers.
        
        Args:
            mask: Grayscale image to OCR
            mode_label: Label for debug files (e.g., 'raw', 'adaptive')
        
        Returns:
            Tuple of (list of signature values, raw OCR text)
        """
        # Upscale for better OCR
        scale = 4
        upscaled = mask.resize(
            (mask.width * scale, mask.height * scale),
            Image.Resampling.LANCZOS
        )
        
        # Invert (Tesseract prefers black on white)
        inverted = ImageOps.invert(upscaled)
        
        if self.debug_mode:
            suffix = f"_{mode_label}" if mode_label else ""
            inverted.save(self._debug_path(f"05_ocr_input{suffix}.png"))
            self.last_debug_info['debug_files'].append(f"{self._debug_prefix}05_ocr_input{suffix}.png")
        
        try:
            text = pytesseract.image_to_string(
                inverted,
                config='--psm 7 -c tessedit_char_whitelist=0123456789,'
            )
        except Exception as e:
            return [], f"OCR ERROR: {e}"
        
        # Extract numbers
        signatures = []
        for pattern in [r'(\d{1,3},\d{3})', r'(\d{3,6})']:
            for match in re.findall(pattern, text):
                try:
                    value = int(match.replace(',', ''))
                    if 500 <= value <= 200000:
                        signatures.append(value)
                except ValueError:
                    pass
        
        return signatures, text.strip()
    
    def match_signature(self, signature: int) -> List[Dict[str, Any]]:
        """Match a signature value to possible targets, including estimated values."""
        matches = []
        
        # Check for known signature (asteroid types, deposits)
        if signature in self.signature_lookup:
            match_data = {
                'type': 'known',
                'name': self.signature_lookup[signature],
                'signature': signature,
                'confidence': 1.0
            }
            
            # Add estimated value and composition if pricing available
            if HAS_PRICING and signature in SIGNATURE_TO_ROCK_TYPE:
                rock_type, category = SIGNATURE_TO_ROCK_TYPE[signature]
                match_data['rock_type'] = rock_type
                match_data['category'] = category
                
                # Get value and composition
                est_value, composition = self._get_rock_value_and_composition(rock_type)
                if est_value > 0:
                    match_data['est_value'] = int(est_value)
                if composition:
                    match_data['composition'] = composition
            
            matches.append(match_data)
        
        # Check for salvage (2000 per panel) - exact multiples only
        if signature >= 2000 and signature % 2000 == 0:
            panels = signature // 2000
            matches.append({
                'type': 'salvage',
                'name': f'Salvage ({panels} panels)',
                'panels': panels,
                'signature': signature,
                'confidence': 1.0  # Exact match - definitive
            })
        
        # Check for ground deposits (small=120, large=620)
        # These are 100% single mineral per cluster
        if self.ground_deposit_small_base > 0 and signature % self.ground_deposit_small_base == 0:
            count = signature // self.ground_deposit_small_base
            if 1 <= count <= 50:  # Reasonable cluster size
                # Higher confidence for smaller counts
                confidence = 0.9 if count <= 5 else max(0.6, 0.85 - count * 0.01)
                matches.append({
                    'type': 'ground_deposit',
                    'name': f'Small Ground Deposit ({count}x)',
                    'count': count,
                    'base_signature': self.ground_deposit_small_base,
                    'signature': signature,
                    'confidence': confidence,
                    'category': 'ground_deposits',
                    'variant': 'small',
                    'mining_method': 'FPS/Hand mining',
                    'single_mineral': True,
                    'possible_minerals': self.ground_deposit_minerals.copy()
                })
        
        if self.ground_deposit_large_base > 0 and signature % self.ground_deposit_large_base == 0:
            count = signature // self.ground_deposit_large_base
            if 1 <= count <= 30:  # Reasonable cluster size for large deposits
                # Higher confidence for smaller counts
                confidence = 0.9 if count <= 3 else max(0.6, 0.85 - count * 0.02)
                matches.append({
                    'type': 'ground_deposit',
                    'name': f'Large Ground Deposit ({count}x)',
                    'count': count,
                    'base_signature': self.ground_deposit_large_base,
                    'signature': signature,
                    'confidence': confidence,
                    'category': 'ground_deposits',
                    'variant': 'large',
                    'mining_method': 'ROC/Vehicle mining',
                    'single_mineral': True,
                    'possible_minerals': self.ground_deposit_minerals.copy()
                })
        
        # Check space deposits (asteroids) and surface deposits
        for base_sig, info in self.minable_signatures.items():
            if base_sig == 0:
                continue
            if signature % base_sig == 0:
                count = signature // base_sig
                if 1 <= count <= 100:
                    confidence = 0.9 if count == 1 else max(0.5, 0.85 - count * 0.01)
                    match_data = {
                        'type': info['category'],
                        'name': info['name'],
                        'count': count,
                        'base_signature': base_sig,
                        'signature': signature,
                        'confidence': confidence
                    }
                    
                    # Add estimated value and composition if pricing available
                    if HAS_PRICING and base_sig in SIGNATURE_TO_ROCK_TYPE:
                        rock_type, category = SIGNATURE_TO_ROCK_TYPE[base_sig]
                        match_data['rock_type'] = rock_type
                        match_data['category'] = category
                        
                        est_value, composition = self._get_rock_value_and_composition(rock_type)
                        if est_value > 0:
                            match_data['est_value'] = int(est_value * count)
                        if composition:
                            match_data['composition'] = composition
                    
                    matches.append(match_data)
        
        # Sort by confidence
        matches.sort(key=lambda x: x.get('confidence', 0), reverse=True)
        
        # Remove duplicates
        seen = set()
        unique = []
        for m in matches:
            key = (m.get('type'), m.get('name'))
            if key not in seen:
                seen.add(key)
                unique.append(m)
        
        return unique
    
    def _get_rock_value(self, rock_type: str) -> float:
        """Get estimated value for a rock type using pricing system."""
        if not HAS_PRICING:
            return 0
        
        try:
            manager = pricing.get_pricing_manager()
            value, _ = manager.calculate_rock_value(self.system, rock_type)
            return value
        except Exception:
            return 0
    
    def _get_rock_value_and_composition(self, rock_type: str) -> Tuple[float, List[Dict]]:
        """Get estimated value and mineral composition for a rock type.
        
        Returns:
            Tuple of (total_value, composition_list)
            composition_list contains dicts with: name, prob, medPct, value, price
            
        Note: Value is calculated assuming the mineral spawns (based on medPct only,
        not probability). This gives the user the value IF that mineral appears.
        """
        if not HAS_PRICING:
            return 0, []
        
        try:
            manager = pricing.get_pricing_manager()
            
            # Get rock data
            system_data = manager.rock_types.get(self.system, {})
            rock_data = system_data.get(rock_type)
            
            if not rock_data:
                return 0, []
            
            # Get mass and yield
            mass = rock_data.get('mass', {}).get('med', 0)
            yield_factor = manager.refinery_yield
            
            # Build composition list
            ores = rock_data.get('ores', {})
            composition = []
            total_value = 0
            
            for ore_name, ore_data in ores.items():
                if ore_name == 'INERTMATERIAL':
                    continue  # Skip inert
                
                prob = ore_data.get('prob', 0)
                med_pct = ore_data.get('medPct', 0)
                
                if prob > 0 and med_pct > 0:
                    # Get price and density for this ore
                    price_per_scu = manager.get_ore_price(ore_name)
                    density = pricing.MINERAL_DENSITY.get(ore_name.upper(), 100.0)
                    
                    # Calculate value IF mineral spawns (median only, no probability)
                    # mineral_mass = deposit_mass × medPct
                    # mineral_volume = mineral_mass / density
                    # value = mineral_volume × price × refinery_yield
                    if price_per_scu > 0 and density > 0:
                        mineral_mass = mass * med_pct
                        mineral_volume = mineral_mass / density
                        ore_value = mineral_volume * price_per_scu * yield_factor
                    else:
                        ore_value = 0
                    
                    composition.append({
                        'name': ore_name.capitalize(),
                        'prob': prob,
                        'medPct': med_pct,
                        'value': int(ore_value) if ore_value else 0,
                        'price': price_per_scu
                    })
                    
                    # For total, use probability-weighted value
                    total_value += ore_value * prob
            
            # Sort by price per SCU (highest value minerals first)
            composition.sort(key=lambda x: x.get('price', 0), reverse=True)
            
            return total_value, composition
            
        except Exception as e:
            if self.debug_mode:
                print(f"[DEBUG] Error getting composition: {e}")
            return 0, []
    
    def enable_debug(self, enable: bool = True, output_dir: Path = None):
        """Enable debug mode."""
        self.debug_mode = enable
        if output_dir:
            self.debug_dir = output_dir
    
    def set_ocr_mode(self, mode: str):
        """Set OCR processing mode.
        
        Args:
            mode: One of:
                - 'raw': Minimal processing, preserves anti-aliasing
                - 'adaptive': Adaptive thresholding for uneven backgrounds
                - 'hybrid': Try raw first, fall back to adaptive (default)
        """
        if mode in ('raw', 'adaptive', 'hybrid'):
            self.ocr_mode = mode
        else:
            raise ValueError(f"Invalid OCR mode: {mode}. Use 'raw', 'adaptive', or 'hybrid'.")
    
    def get_ocr_mode(self) -> str:
        """Get current OCR processing mode."""
        return self.ocr_mode
    
    def _load_image(self, image_path: Path) -> Optional[Image.Image]:
        """Load an image."""
        return Image.open(image_path)

