#!/usr/bin/env python3
"""
Signature scanner for SC Signature Scanner.
Detects signature values from Star Citizen screenshots using OCR.

Requires a scan region to be configured in Settings.

OCR Engine: EasyOCR (deep learning based)
- First run downloads ~115MB of model files
- Subsequent runs use cached models locally
- No external binary dependencies
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from PIL import Image
import numpy as np

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

# EasyOCR import - lazy initialization
HAS_EASYOCR = False
EASYOCR_ERROR = None

# Pillow 10.0.0+ removed ANTIALIAS, but EasyOCR still uses it
# Add compatibility shim before importing easyocr
import PIL.Image
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.Resampling.LANCZOS

try:
    import easyocr
    HAS_EASYOCR = True
except ImportError as e:
    EASYOCR_ERROR = str(e)
    print(f"Warning: EasyOCR not installed. OCR disabled. Error: {e}")


# Display name mapping for short rock type codes
ROCK_DISPLAY_NAMES = {
    # Space deposits (asteroids)
    'I': 'I-type Asteroid',
    'C': 'C-type Asteroid',
    'S': 'S-type Asteroid',
    'P': 'P-type Asteroid',
    'M': 'M-type Asteroid',
    'Q': 'Q-type Asteroid',
    'E': 'E-type Asteroid',
}


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
    """Scans screenshots for signature values using EasyOCR."""
    
    def __init__(self, db_path: Path, system: str = 'STANTON'):
        self.db = self._load_database(db_path)
        self.system = system.upper()  # Default system for pricing
        self._build_lookups()
        
        self.debug_mode = False
        self.debug_dir = paths.get_debug_path()
        self.last_debug_info = {}
        self._debug_prefix = ""  # Timestamp prefix for debug files
        
        # EasyOCR reader - lazily initialized on first use
        self._ocr_reader: Optional[easyocr.Reader] = None
        self._ocr_initialized = False
        self._ocr_init_error: Optional[str] = None
        
        # Callback for model download progress (set by UI)
        self.on_model_download_start: Optional[callable] = None
        self.on_model_download_complete: Optional[callable] = None
    
    def _get_ocr_reader(self) -> Optional[easyocr.Reader]:
        """Get or initialize the EasyOCR reader.
        
        Lazy initialization allows:
        1. Faster app startup
        2. Model download on first actual use
        3. UI can hook download progress callbacks
        
        Returns:
            EasyOCR Reader instance, or None if initialization failed
        """
        if self._ocr_initialized:
            return self._ocr_reader
        
        if not HAS_EASYOCR:
            self._ocr_init_error = EASYOCR_ERROR or "EasyOCR not installed"
            self._ocr_initialized = True
            return None
        
        try:
            # Notify UI that download may start
            if self.on_model_download_start:
                self.on_model_download_start()
            
            if self.debug_mode:
                print("[DEBUG] Initializing EasyOCR reader...")
            
            # Initialize reader
            # - gpu=False: Use CPU (works everywhere, GPU auto-detected if available)
            # - verbose=False: Suppress download progress to stdout
            self._ocr_reader = easyocr.Reader(
                ['en'],
                gpu=False,  # CPU mode - works universally
                verbose=self.debug_mode
            )
            
            if self.debug_mode:
                print("[DEBUG] EasyOCR reader initialized successfully")
            
            # Notify UI that download/init is complete
            if self.on_model_download_complete:
                self.on_model_download_complete()
            
        except Exception as e:
            self._ocr_init_error = str(e)
            self._ocr_reader = None
            if self.debug_mode:
                print(f"[DEBUG] EasyOCR initialization failed: {e}")
        
        self._ocr_initialized = True
        return self._ocr_reader
    
    def is_ocr_available(self) -> Tuple[bool, Optional[str]]:
        """Check if OCR is available.
        
        Returns:
            Tuple of (is_available, error_message)
        """
        if not HAS_EASYOCR:
            return False, EASYOCR_ERROR or "EasyOCR not installed"
        
        if self._ocr_initialized and self._ocr_init_error:
            return False, self._ocr_init_error
        
        return True, None
    
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
        # Check OCR availability
        available, error = self.is_ocr_available()
        if not available:
            return {'error': f'OCR not available: {error}'}
        
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
        
        # Enhance and OCR
        enhanced = self._enhance_for_ocr(sig_crop)
        
        if self.debug_mode:
            # Save enhanced version for debugging
            enhanced_pil = Image.fromarray(enhanced)
            enhanced_pil.save(self._debug_path("04_enhanced.png"))
            self.last_debug_info['debug_files'].append(f"{self._debug_prefix}04_enhanced.png")
        
        # Run OCR
        signatures, ocr_text, confidence = self._ocr_signature(enhanced)
        
        if self.debug_mode:
            print(f"[DEBUG] OCR: text='{ocr_text}' signatures={signatures} confidence={confidence:.2f}")
            with open(self._debug_path("99_summary.txt"), 'w') as f:
                f.write(f"Method: {method}\n")
                f.write(f"Region: ({x1}, {y1}) - ({x2}, {y2})\n")
                f.write(f"OCR engine: EasyOCR\n")
                f.write(f"OCR text: {ocr_text}\n")
                f.write(f"OCR confidence: {confidence:.2f}\n")
                f.write(f"Signatures found: {signatures}\n")
        
        if signatures:
            primary_sig = max(signatures)
            matches = self.match_signature(primary_sig)
            return {
                'signature': primary_sig,
                'all_signatures': list(set(signatures)),
                'matches': matches,
                'method': method,
                'ocr_confidence': confidence,
                'debug': self.last_debug_info if self.debug_mode else None
            }
        
        return None
    
    def _enhance_for_ocr(self, img: Image.Image) -> np.ndarray:
        """Enhance image for OCR.
        
        EasyOCR handles most preprocessing internally, but we still:
        1. Convert to RGB numpy array (EasyOCR's expected input)
        2. Optionally upscale for better small text detection
        
        Args:
            img: Cropped region containing signature
        
        Returns:
            Numpy array (RGB) ready for EasyOCR
        """
        # Ensure RGB
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Upscale small regions for better detection
        min_dimension = 64
        scale = 1
        if img.width < min_dimension or img.height < min_dimension:
            scale = max(min_dimension // min(img.width, img.height), 2)
            img = img.resize(
                (img.width * scale, img.height * scale),
                Image.Resampling.LANCZOS
            )
        
        return np.array(img)
    
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
    
    def _ocr_signature(self, img_array: np.ndarray) -> Tuple[List[int], str, float]:
        """OCR the image and extract signature numbers.
        
        Args:
            img_array: RGB numpy array to OCR
        
        Returns:
            Tuple of (list of signature values, raw OCR text, confidence)
        """
        reader = self._get_ocr_reader()
        if reader is None:
            return [], f"OCR ERROR: {self._ocr_init_error}", 0.0
        
        try:
            # EasyOCR with digit allowlist for maximum accuracy
            results = reader.readtext(
                img_array,
                allowlist='0123456789,.',
                paragraph=False,  # Don't merge into paragraphs
                detail=1,  # Return bounding boxes + confidence
            )
            
            if self.debug_mode:
                print(f"[DEBUG] EasyOCR raw results: {results}")
            
            # Extract text and confidence
            texts = []
            confidences = []
            
            for detection in results:
                # detection = (bbox, text, confidence)
                if len(detection) >= 3:
                    bbox, text, conf = detection[0], detection[1], detection[2]
                    texts.append(text)
                    confidences.append(conf)
            
            combined_text = ' '.join(texts)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            
            # Extract signature values
            signatures = self._extract_signatures(combined_text)
            
            return signatures, combined_text, avg_confidence
            
        except Exception as e:
            return [], f"OCR ERROR: {e}", 0.0
    
    def _extract_signatures(self, text: str) -> List[int]:
        """Extract valid signature values from OCR text.
        
        Args:
            text: Raw OCR text
            
        Returns:
            List of valid signature integers
        """
        signatures = []
        
        # Pattern 1: Numbers with comma separators (e.g., "1,850")
        for match in re.findall(r'(\d{1,3},\d{3})', text):
            try:
                value = int(match.replace(',', ''))
                if self._is_valid_signature(value):
                    signatures.append(value)
            except ValueError:
                pass
        
        # Pattern 2: Plain numbers (e.g., "1850")
        for match in re.findall(r'(\d{3,6})', text):
            try:
                value = int(match)
                if self._is_valid_signature(value) and value not in signatures:
                    signatures.append(value)
            except ValueError:
                pass
        
        return signatures
    
    def _is_valid_signature(self, value: int) -> bool:
        """Check if a value is in valid signature range.
        
        Args:
            value: Integer to validate
            
        Returns:
            True if value could be a valid signature
        """
        # Valid range: 100 (small ground deposit) to 200,000 (large salvage/asteroid field)
        return 100 <= value <= 200000
    
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
                    
                    # Get display name (expand short codes like "C" to "C-type Asteroid")
                    raw_name = info['name']
                    display_name = ROCK_DISPLAY_NAMES.get(raw_name, raw_name)
                    if count > 1:
                        display_name = f"{display_name} (x{count})"
                    
                    match_data = {
                        'type': info['category'],
                        'name': display_name,
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
    
    def _load_image(self, image_path: Path) -> Optional[Image.Image]:
        """Load an image."""
        return Image.open(image_path)
