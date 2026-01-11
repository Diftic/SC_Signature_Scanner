#!/usr/bin/env python3
"""
Signature scanner for SC Signature Scanner.
Detects signature values from Star Citizen screenshots using HUD element detection.

Algorithm:
1. Find HUD anchor elements (circle reticle + two info squares)
2. Use circle center as primary anchor point
3. Use squares to determine HUD rotation (if tilted)
4. Calculate signature location from circle center (fixed offset)
5. OCR that specific region

Shape-based detection works for any HUD color without color-specific calibration.
"""

import json
import math
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Callable
from PIL import Image, ImageOps
import numpy as np

try:
    import pricing
    HAS_PRICING = True
except ImportError:
    HAS_PRICING = False

# Import region selector for fallback scan region
try:
    import region_selector
    HAS_REGION_SELECTOR = True
except ImportError:
    HAS_REGION_SELECTOR = False

# Import Tobii tracker for gaze-based scanning
try:
    import tobii_tracker
    HAS_TOBII = True
except ImportError:
    HAS_TOBII = False

# Import identifier window
try:
    import hud_calibration
    HAS_CALIBRATION = True
except ImportError:
    HAS_CALIBRATION = False

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
        self.debug_dir = Path(__file__).parent / "debug_output"
        self.last_debug_info = {}
        
        # Manual calibration mode
        self.use_calibration = HAS_CALIBRATION and hud_calibration.is_configured()
        
        # Tobii gaze tracking
        self.use_tobii = HAS_TOBII
        self.tobii_region_padding = 150  # Pixels around gaze point to scan
    
    def scan_image(self, image_path: Path) -> Optional[Dict[str, Any]]:
        """Scan an image for signature values.
        
        Tries detection methods in order:
        1. Tobii eye tracker (if connected)
        2. Fixed scan region (if configured)
        3. Auto-detection of HUD circle (fallback)
        """
        if not HAS_TESSERACT:
            return {'error': 'Tesseract not installed'}
        
        self.last_debug_info = {
            'image_path': str(image_path),
            'debug_files': [],
            'method': None
        }
        
        try:
            img = self._load_image(image_path)
            if img is None:
                return {'error': f'Failed to load image: {image_path.name}'}
            
            width, height = img.size
            self.last_debug_info['image_size'] = (width, height)
            
            if self.debug_mode:
                self.debug_dir.mkdir(exist_ok=True)
                img.save(self.debug_dir / "00_original.png")
                self.last_debug_info['debug_files'].append("00_original.png")
            
            # Try Tobii first
            if self.use_tobii and HAS_TOBII and tobii_tracker.is_available():
                result = self._scan_with_tobii(img, width, height)
                if result:
                    self.last_debug_info['method'] = 'tobii'
                    return result
                if self.debug_mode:
                    print("[DEBUG] Tobii scan failed, trying fallback")
            
            # Try fixed region
            if HAS_REGION_SELECTOR and region_selector.is_configured():
                result = self._scan_with_fixed_region(img, width, height)
                if result:
                    self.last_debug_info['method'] = 'fixed_region'
                    return result
                if self.debug_mode:
                    print("[DEBUG] Fixed region scan failed, trying auto-detection")
            
            # Fall back to auto-detection
            result = self._scan_with_auto_detection(img, width, height, image_path)
            if result:
                self.last_debug_info['method'] = 'auto_detection'
            return result
            
        except Exception as e:
            if self.debug_mode:
                import traceback
                with open(self.debug_dir / "99_error.txt", 'w') as f:
                    f.write(traceback.format_exc())
            return {'error': str(e)}
    
    def _scan_with_tobii(self, img: Image.Image, width: int, height: int) -> Optional[Dict[str, Any]]:
        """Scan using Tobii gaze point as center."""
        gaze = tobii_tracker.get_gaze_pixels(width, height)
        if not gaze:
            return None
        
        gaze_x, gaze_y = gaze
        
        if self.debug_mode:
            print(f"[DEBUG] Tobii gaze at ({gaze_x}, {gaze_y})")
        
        # Define square region around gaze point
        padding = self.tobii_region_padding
        
        x1 = max(0, gaze_x - padding)
        y1 = max(0, gaze_y - padding)
        x2 = min(width, gaze_x + padding)
        y2 = min(height, gaze_y + padding)
        
        return self._scan_region(img, x1, y1, x2, y2, "tobii")
    
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
            debug_img.save(self.debug_dir / f"02_{method}_region.png")
            self.last_debug_info['debug_files'].append(f"02_{method}_region.png")
        
        # Crop region
        sig_crop = img.crop((x1, y1, x2, y2))
        
        if self.debug_mode:
            sig_crop.save(self.debug_dir / "03_sig_crop.png")
            self.last_debug_info['debug_files'].append("03_sig_crop.png")
        
        # Extract text mask
        sig_mask = self._extract_signature_text(sig_crop)
        
        if self.debug_mode:
            sig_mask.save(self.debug_dir / "04_sig_mask.png")
            self.last_debug_info['debug_files'].append("04_sig_mask.png")
        
        # OCR
        signatures, ocr_text = self._ocr_signature(sig_mask)
        
        if self.debug_mode:
            print(f"[DEBUG] OCR text: {ocr_text}")
            print(f"[DEBUG] Signatures: {signatures}")
            
            with open(self.debug_dir / "99_summary.txt", 'w') as f:
                f.write(f"Method: {method}\n")
                f.write(f"Region: ({x1}, {y1}) - ({x2}, {y2})\n")
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
                'debug': self.last_debug_info if self.debug_mode else None
            }
        
        return None
    
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
    
    def _scan_with_auto_detection(self, img: Image.Image, width: int, height: int, 
                                    image_path: Path) -> Optional[Dict[str, Any]]:
        """Scan using auto-detection of HUD circle (original method).
        
        Uses either:
        1. Manual identifier calibration (if configured)
        2. Auto-detection of HUD circle (fallback)
        """
        # Get circle position - either from calibration or auto-detection
        if self.use_calibration and HAS_CALIBRATION and hud_calibration.is_configured():
            # Use manual calibration
            pos = hud_calibration.get_circle_position()
            if pos:
                center_x, center_y, diameter = pos
                cross_center = (center_x, center_y)
                cross_size = diameter
                angle = 0.0
                
                if self.debug_mode:
                    print(f"[DEBUG] Using calibration: center={cross_center}, diameter={cross_size}")
            else:
                cross_result = self._find_cross(img)
                if cross_result is None:
                    return None
                cross_center, cross_size, angle = cross_result
        else:
            # Auto-detect
            cross_result = self._find_cross(img)
            
            if cross_result is None:
                if self.debug_mode:
                    print("[DEBUG] HUD circle not found")
                    with open(self.debug_dir / "99_summary.txt", 'w') as f:
                        f.write(f"Image: {image_path.name}\n")
                        f.write(f"Size: {width}x{height}\n")
                        f.write(f"FAILED: No HUD circle detected\n")
                        f.write(f"TIP: Use identifier window (Settings) to manually calibrate\n")
                return None
            
            cross_center, cross_size, angle = cross_result
        
        if self.debug_mode:
            print(f"[DEBUG] Circle center: {cross_center}")
            print(f"[DEBUG] Circle diameter: {cross_size}")
            print(f"[DEBUG] Angle: {angle:.1f}°")
        
        # Rotate image if needed
        if abs(angle) > 1:
            img_rotated = img.rotate(angle, expand=False, center=cross_center, fillcolor=(0, 0, 0))
        else:
            img_rotated = img
        
        # Calculate signature position
        if self.use_calibration and HAS_CALIBRATION:
            # Use calibration's offset settings
            sig_region = hud_calibration.get_signature_region()
            if sig_region:
                x1, y1, x2, y2 = sig_region
                sig_x = (x1 + x2) // 2
                sig_y = (y1 + y2) // 2
            else:
                # Fallback to defaults
                unit = cross_size
                sig_x = cross_center[0] + int(unit * 5.0)
                sig_y = cross_center[1] - int(unit * 3.5)
                padding_x = int(unit * 1.5)
                padding_y = int(unit * 1.0)
                x1 = max(0, sig_x - padding_x)
                y1 = max(0, sig_y - padding_y)
                x2 = min(width, sig_x + padding_x)
                y2 = min(height, sig_y + padding_y)
        else:
            # Use default offsets
            unit = cross_size  # diameter
            sig_x = cross_center[0] + int(unit * 5.0)
            sig_y = cross_center[1] - int(unit * 3.5)
            
            padding_x = int(unit * 1.5)
            padding_y = int(unit * 1.0)
            
            x1 = max(0, sig_x - padding_x)
            y1 = max(0, sig_y - padding_y)
            x2 = min(width, sig_x + padding_x)
            y2 = min(height, sig_y + padding_y)
        
        if self.debug_mode:
            print(f"[DEBUG] Signature region: ({x1}, {y1}) - ({x2}, {y2})")
            
            from PIL import ImageDraw
            debug_img = img.copy()
            draw = ImageDraw.Draw(debug_img)
            
            r = 15
            draw.ellipse([cross_center[0]-r, cross_center[1]-r, 
                         cross_center[0]+r, cross_center[1]+r], 
                        outline='#FF0000', width=3)
            draw.rectangle([x1, y1, x2, y2], outline='#00FF00', width=3)
            draw.line([cross_center, (sig_x, sig_y)], fill='#FFFF00', width=2)
            
            debug_img.save(self.debug_dir / "02_detection.png")
            self.last_debug_info['debug_files'].append("02_detection.png")
        
        # Extract and OCR signature region
        sig_crop = img_rotated.crop((x1, y1, x2, y2))
        
        if self.debug_mode:
            sig_crop.save(self.debug_dir / "03_sig_crop.png")
            self.last_debug_info['debug_files'].append("03_sig_crop.png")
        
        sig_mask = self._extract_signature_text(sig_crop)
        
        if self.debug_mode:
            sig_mask.save(self.debug_dir / "04_sig_mask.png")
            self.last_debug_info['debug_files'].append("04_sig_mask.png")
        
        signatures, ocr_text = self._ocr_signature(sig_mask)
        
        if self.debug_mode:
            print(f"[DEBUG] OCR text: {ocr_text}")
            print(f"[DEBUG] Signatures: {signatures}")
            
            with open(self.debug_dir / "99_summary.txt", 'w') as f:
                f.write(f"Image: {image_path.name}\n")
                f.write(f"Size: {width}x{height}\n")
                f.write(f"Cross center: {cross_center}\n")
                f.write(f"Cross size: {cross_size}\n")
                f.write(f"Angle: {angle:.1f}°\n")
                f.write(f"Signature region: ({x1}, {y1}) - ({x2}, {y2})\n")
                f.write(f"OCR text: {ocr_text}\n")
                f.write(f"Signatures found: {signatures}\n")
        
        if signatures:
            primary_sig = max(signatures)
            matches = self.match_signature(primary_sig)
            return {
                'signature': primary_sig,
                'all_signatures': list(set(signatures)),
                'matches': matches,
                'method': 'auto_detection',
                'debug': self.last_debug_info if self.debug_mode else None
            }
        
        return None
    
    def _find_cross(self, img: Image.Image, color_filter: str = None) -> Optional[Tuple[Tuple[int, int], int, float]]:
        """Find HUD circle (targeting reticle).
        
        Detection strategy:
        1. Use R-B color difference to isolate warm-colored HUD
        2. Hough circle transform
        3. Verify ring shape (hollow center)
        
        Args:
            img: Image to search
            color_filter: Ignored (kept for API compatibility)
        
        Returns:
            Tuple of (center_xy, size, angle_degrees) or None if not found.
            center_xy is the circle center, size is circle diameter, angle is HUD rotation.
        """
        try:
            import cv2
        except ImportError:
            if self.debug_mode:
                print("[DEBUG] OpenCV not available")
            return None
        
        width, height = img.size
        arr = np.array(img)
        
        # Search region: adjust for ultrawide monitors
        # Standard 16:9 = 1.78, Ultrawide 32:9 = 3.56
        aspect_ratio = width / height
        
        if aspect_ratio > 2.5:  # Ultrawide (32:9 or similar)
            # HUD is centered on the middle monitor of triple-wide
            x_min = int(width * 0.35)  # Start at 35%
            x_max = int(width * 0.50)  # End at 50%
        else:  # Standard or 21:9
            x_min = int(width * 0.25)
            x_max = int(width * 0.50)
        
        y_min = int(height * 0.25)
        y_max = int(height * 0.75)
        
        if self.debug_mode:
            print(f"[DEBUG] Image: {width}x{height}, aspect: {aspect_ratio:.2f}")
            print(f"[DEBUG] Search region: X {x_min}-{x_max}, Y {y_min}-{y_max}")
        
        search = arr[y_min:y_max, x_min:x_max]
        
        # Use red channel or R-B difference to isolate warm-colored HUD
        # HUD is orange/yellow (high R), background is blue/gray (high B, low R)
        r = search[:,:,0].astype(np.int16)
        b = search[:,:,2].astype(np.int16)
        
        # R-B difference: positive for warm colors, negative for cool
        diff = r - b
        
        # Normalize to 0-255 range for Hough
        # Shift so that 0 difference = 128, then clip
        normalized = np.clip(diff + 128, 0, 255).astype(np.uint8)
        
        # Apply Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(normalized, (5, 5), 1.5)
        
        if self.debug_mode:
            mask_img = Image.fromarray(blurred, mode='L')
            mask_img.save(self.debug_dir / "01_rb_difference.png")
            self.last_debug_info['debug_files'].append("01_rb_difference.png")
        
        # Scale parameters based on resolution
        scale_factor = max(1.0, min(width, height) / 1080)
        min_radius = int(12 * scale_factor)
        max_radius = int(50 * scale_factor)
        min_dist = int(40 * scale_factor)
        
        if self.debug_mode:
            print(f"[DEBUG] Scale: {scale_factor:.2f}, radius range: {min_radius}-{max_radius}")
        
        # Hough circle detection on grayscale
        # param1 = Canny high threshold (low = param1/2)
        # param2 = accumulator threshold (lower = more circles detected)
        circles = cv2.HoughCircles(
            blurred,
            cv2.HOUGH_GRADIENT,
            dp=1,
            minDist=min_dist,
            param1=100,              # Canny high threshold
            param2=30,               # Accumulator threshold
            minRadius=min_radius,
            maxRadius=max_radius
        )
        
        if circles is None:
            if self.debug_mode:
                print("[DEBUG] No circles found")
            return None
        
        circles = np.uint16(np.around(circles))
        
        if self.debug_mode:
            print(f"[DEBUG] Found {len(circles[0])} circles")
            # Draw detected circles on debug image
            debug_img = cv2.cvtColor(search, cv2.COLOR_RGB2BGR)
            for c in circles[0]:
                cv2.circle(debug_img, (c[0], c[1]), c[2], (0, 255, 0), 2)
                cv2.circle(debug_img, (c[0], c[1]), 2, (0, 0, 255), 3)
            cv2.imwrite(str(self.debug_dir / "01b_circles_found.png"), debug_img)
            self.last_debug_info['debug_files'].append("01b_circles_found.png")
        
        # Find the best circle - prefer hollow rings (HUD) over filled circles (asteroids)
        search_center_x = normalized.shape[1] / 2
        search_center_y = normalized.shape[0] / 2
        
        best_circle = None
        best_score = -float('inf')
        
        for circle in circles[0]:
            cx, cy, radius = circle
            
            # Verify it's ring-shaped (hollow center)
            ring_score = self._verify_ring_shape_gray(normalized, cx, cy, radius)
            
            # Distance from center of search region
            dist = math.sqrt((cx - search_center_x)**2 + (cy - search_center_y)**2)
            dist_penalty = dist / max(normalized.shape)  # Normalize
            
            # Score: high ring score, close to center
            score = ring_score - dist_penalty * 0.5
            
            if self.debug_mode:
                print(f"[DEBUG]   Circle ({cx}, {cy}) r={radius}: ring={ring_score:.2f}, dist={dist:.0f}, score={score:.2f}")
            
            if score > best_score and ring_score > 0.2:
                best_score = score
                best_circle = (cx, cy, radius)
        
        if best_circle is None:
            if self.debug_mode:
                print("[DEBUG] No valid ring-shaped circle found")
            return None
        
        cx, cy, radius = best_circle
        
        # Convert to global coordinates
        global_cx = cx + x_min
        global_cy = cy + y_min
        
        if self.debug_mode:
            print(f"[DEBUG] Best circle: ({global_cx}, {global_cy}) r={radius}")
        
        # Return circle center, diameter as size, and rotation angle (0 for now)
        return ((global_cx, global_cy), radius * 2, 0.0)
    
    def _verify_ring_shape_gray(self, gray: np.ndarray, cx: int, cy: int, radius: int) -> float:
        """Verify circle is ring-shaped by comparing inner vs edge brightness.
        
        HUD circle: bright ring, dark center
        Asteroid: roughly uniform brightness
        
        Returns score 0.0-1.0 (higher = more ring-like)
        """
        h, w = gray.shape
        
        inner_pixels = []
        ring_pixels = []
        
        # Sample pixels at different distances from center
        for angle in range(0, 360, 15):  # Sample every 15 degrees
            rad = math.radians(angle)
            
            # Inner point (40% of radius)
            ix = int(cx + radius * 0.3 * math.cos(rad))
            iy = int(cy + radius * 0.3 * math.sin(rad))
            if 0 <= ix < w and 0 <= iy < h:
                inner_pixels.append(gray[iy, ix])
            
            # Ring point (90% of radius)
            rx = int(cx + radius * 0.9 * math.cos(rad))
            ry = int(cy + radius * 0.9 * math.sin(rad))
            if 0 <= rx < w and 0 <= ry < h:
                ring_pixels.append(gray[ry, rx])
        
        if len(inner_pixels) < 10 or len(ring_pixels) < 10:
            return 0.0
        
        inner_mean = np.mean(inner_pixels)
        ring_mean = np.mean(ring_pixels)
        
        # Ring should be brighter than center
        # Score based on contrast ratio
        if ring_mean <= inner_mean:
            return 0.0
        
        contrast = (ring_mean - inner_mean) / max(1, ring_mean)
        return min(1.0, contrast * 2)
    
    def _find_circle_hough(self, mask: np.ndarray, x_offset: int, y_offset: int, 
                            img_width: int, img_height: int) -> Optional[Tuple[Tuple[int, int], int, float]]:
        """Find circle using OpenCV Hough transform."""
        try:
            import cv2
        except ImportError:
            if self.debug_mode:
                print("[DEBUG] OpenCV not available, using fallback")
            return None
        
        # Convert mask to uint8 for OpenCV
        mask_uint8 = (mask * 255).astype(np.uint8)
        
        # Scale parameters based on resolution
        scale_factor = max(1.0, min(img_width, img_height) / 1080)
        min_radius = int(15 * scale_factor)
        max_radius = int(60 * scale_factor)
        min_dist = int(50 * scale_factor)
        
        # Detect circles with stricter parameters
        circles = cv2.HoughCircles(
            mask_uint8,
            cv2.HOUGH_GRADIENT,
            dp=1,
            minDist=min_dist,
            param1=50,
            param2=25,               # Increased from 20 - stricter detection
            minRadius=min_radius,
            maxRadius=max_radius
        )
        
        if circles is None:
            if self.debug_mode:
                print("[DEBUG] No circles found by Hough transform")
            return None
        
        circles = np.uint16(np.around(circles))
        
        if self.debug_mode:
            print(f"[DEBUG] Found {len(circles[0])} circles")
        
        # Find the best circle (prefer ones closer to center of search region)
        search_center_x = mask.shape[1] / 2
        search_center_y = mask.shape[0] / 2
        
        best_circle = None
        best_score = float('inf')
        
        for circle in circles[0]:
            cx, cy, radius = circle
            
            # Score by distance from center (lower is better)
            dist = math.sqrt((cx - search_center_x)**2 + (cy - search_center_y)**2)
            
            # Also verify it's actually ring-shaped (hollow center)
            ring_score = self._verify_ring_shape(mask, cx, cy, radius)
            
            if ring_score < 0.3:  # Not ring-shaped enough
                continue
            
            score = dist / ring_score  # Lower dist, higher ring_score = better
            
            if self.debug_mode:
                print(f"[DEBUG]   Circle at ({cx}, {cy}) r={radius}, ring={ring_score:.2f}, score={score:.1f}")
            
            if score < best_score:
                best_score = score
                best_circle = (cx, cy, radius)
        
        if best_circle is None:
            return None
        
        cx, cy, radius = best_circle
        
        # Sanity check: circle must be reasonably centered in search region
        if cx < mask.shape[1] * 0.1 or cx > mask.shape[1] * 0.9:
            if self.debug_mode:
                print(f"[DEBUG] Circle rejected: too far from center (x={cx})")
            return None
        
        # Convert to global coordinates
        global_cx = cx + x_offset
        global_cy = cy + y_offset
        
        # Now find the two squares to determine rotation
        angle = self._find_rotation_from_squares(mask, cx, cy, radius, x_offset, y_offset)
        
        if self.debug_mode:
            print(f"[DEBUG] Best circle: ({global_cx}, {global_cy}) r={radius}, angle={angle:.1f}°")
        
        # Return circle center, diameter as size, and rotation angle
        return ((global_cx, global_cy), radius * 2, angle)
    
    def _verify_ring_shape(self, mask: np.ndarray, cx: int, cy: int, radius: int) -> float:
        """Verify that a detected circle is actually ring-shaped (hollow center).
        
        Returns score 0.0-1.0 (higher = more ring-like)
        """
        h, w = mask.shape
        
        # Sample pixels at different distances from center
        inner_radius = radius * 0.4  # Should be empty
        ring_radius = radius * 0.85  # Should have pixels
        
        inner_pixels = 0
        inner_total = 0
        ring_pixels = 0
        ring_total = 0
        
        # Sample in a grid pattern
        for dy in range(-radius, radius + 1, max(1, radius // 10)):
            for dx in range(-radius, radius + 1, max(1, radius // 10)):
                dist = math.sqrt(dx*dx + dy*dy)
                py, px = int(cy + dy), int(cx + dx)
                
                if 0 <= py < h and 0 <= px < w:
                    if dist < inner_radius:
                        inner_total += 1
                        if mask[py, px]:
                            inner_pixels += 1
                    elif dist > radius * 0.6 and dist < radius * 1.1:
                        ring_total += 1
                        if mask[py, px]:
                            ring_pixels += 1
        
        if inner_total == 0 or ring_total == 0:
            return 0.0
        
        inner_density = inner_pixels / inner_total
        ring_density = ring_pixels / ring_total
        
        # Good ring: low inner density, moderate ring density
        # Score: high ring density, low inner density
        if ring_density < 0.1:
            return 0.0
        
        score = ring_density * (1.0 - inner_density)
        return min(1.0, score * 2)  # Scale up
    
    def _find_rotation_from_squares(self, mask: np.ndarray, circle_x: int, circle_y: int, 
                                     circle_radius: int, x_offset: int, y_offset: int) -> float:
        """Find HUD rotation by detecting the two square elements.
        
        Layout (when upright):
        - Top square (SCM/SCN): above-left of circle
        - Bottom square (ESP/CRLD): below-left of circle
        
        Returns rotation angle in degrees.
        """
        try:
            from scipy import ndimage
        except ImportError:
            return 0.0
        
        # Find connected components
        labeled, num_features = ndimage.label(mask)
        
        # Look for square-ish clusters that are not the circle
        squares = []
        
        for i in range(1, num_features + 1):
            cluster_mask = labeled == i
            size = np.sum(cluster_mask)
            
            if size < 50:  # Too small
                continue
            
            coords = np.where(cluster_mask)
            y_coords, x_coords = coords
            
            min_x, max_x = x_coords.min(), x_coords.max()
            min_y, max_y = y_coords.min(), y_coords.max()
            cluster_w = max_x - min_x
            cluster_h = max_y - min_y
            
            if cluster_w < 10 or cluster_h < 10:
                continue
            
            # Check if it's roughly square
            aspect = max(cluster_w, cluster_h) / max(1, min(cluster_w, cluster_h))
            if aspect > 2.0:  # Too elongated
                continue
            
            center_x = (min_x + max_x) / 2
            center_y = (min_y + max_y) / 2
            
            # Skip if it's the circle (close to circle center)
            dist_to_circle = math.sqrt((center_x - circle_x)**2 + (center_y - circle_y)**2)
            if dist_to_circle < circle_radius * 2:
                continue
            
            # Calculate fill ratio (squares should be more filled than circle)
            fill_ratio = size / max(1, cluster_w * cluster_h)
            
            squares.append({
                'center_x': center_x,
                'center_y': center_y,
                'size': size,
                'width': cluster_w,
                'height': cluster_h,
                'fill': fill_ratio,
                'dist_to_circle': dist_to_circle
            })
        
        if self.debug_mode:
            print(f"[DEBUG] Found {len(squares)} potential squares")
        
        if len(squares) < 2:
            return 0.0  # Can't determine rotation without both squares
        
        # Sort by distance to circle, take two closest
        squares.sort(key=lambda s: s['dist_to_circle'])
        sq1, sq2 = squares[0], squares[1]
        
        # The line from circle to midpoint of squares gives us orientation
        mid_x = (sq1['center_x'] + sq2['center_x']) / 2
        mid_y = (sq1['center_y'] + sq2['center_y']) / 2
        
        # Angle from circle to midpoint (should be roughly left/up-left when upright)
        dx = mid_x - circle_x
        dy = mid_y - circle_y
        
        # Base angle: squares are to the left of circle, so expected angle ~180° (pointing left)
        angle_rad = math.atan2(dy, dx)
        angle_deg = math.degrees(angle_rad)
        
        # Normalize: when upright, angle should be ~180° (left) or ~135° (up-left)
        # We want to return how much it's rotated from upright
        # For now, return 0 as rotation - we can refine this
        
        if self.debug_mode:
            print(f"[DEBUG] Squares midpoint angle from circle: {angle_deg:.1f}°")
        
        return 0.0  # TODO: Calculate actual rotation offset
    
    def _find_hud_elements_clusters(self, mask: np.ndarray, x_offset: int, y_offset: int,
                                     img_width: int, img_height: int) -> Optional[Tuple[Tuple[int, int], int, float]]:
        """Fallback: find HUD elements using cluster analysis when Hough fails."""
        try:
            from scipy import ndimage
        except ImportError:
            if self.debug_mode:
                print("[DEBUG] scipy not available")
            return None
        
        labeled, num_features = ndimage.label(mask)
        
        if self.debug_mode:
            print(f"[DEBUG] Cluster fallback: {num_features} components")
        
        # Find clusters and classify them
        circles = []
        squares = []
        
        scale_factor = max(1.0, min(img_width, img_height) / 1080)
        min_size = int(100 * scale_factor)
        
        for i in range(1, num_features + 1):
            cluster_mask = labeled == i
            size = np.sum(cluster_mask)
            
            if size < min_size:
                continue
            
            coords = np.where(cluster_mask)
            y_coords, x_coords = coords
            
            min_x, max_x = x_coords.min(), x_coords.max()
            min_y, max_y = y_coords.min(), y_coords.max()
            cluster_w = max_x - min_x
            cluster_h = max_y - min_y
            
            if cluster_w < 10 or cluster_h < 10:
                continue
            
            center_x = (min_x + max_x) / 2
            center_y = (min_y + max_y) / 2
            
            # Calculate properties
            aspect = max(cluster_w, cluster_h) / max(1, min(cluster_w, cluster_h))
            fill_ratio = size / max(1, cluster_w * cluster_h)
            
            # Classify: circles have lower fill ratio (hollow), squares higher
            cluster_info = {
                'center_x': center_x,
                'center_y': center_y,
                'width': cluster_w,
                'height': cluster_h,
                'size': size,
                'aspect': aspect,
                'fill': fill_ratio
            }
            
            if aspect < 1.5 and fill_ratio < 0.4:  # Likely circle (hollow)
                circles.append(cluster_info)
            elif aspect < 2.0 and fill_ratio > 0.2:  # Likely square
                squares.append(cluster_info)
        
        if self.debug_mode:
            print(f"[DEBUG] Classified: {len(circles)} circles, {len(squares)} squares")
        
        if not circles:
            return None
        
        # Take the best circle candidate (largest with good aspect)
        circles.sort(key=lambda c: c['size'], reverse=True)
        best_circle = circles[0]
        
        cx = int(best_circle['center_x']) + x_offset
        cy = int(best_circle['center_y']) + y_offset
        diameter = max(best_circle['width'], best_circle['height'])
        
        if self.debug_mode:
            print(f"[DEBUG] Best circle: ({cx}, {cy}) d={diameter}")
        
        return ((cx, cy), diameter, 0.0)
    
    def _analyze_cross_pixels(self, coords: Tuple[np.ndarray, np.ndarray], x_offset: int, y_offset: int) -> Optional[Tuple[Tuple[int, int], int, float]]:
        """Analyze cross pixels to extract center, size, and angle."""
        y_coords, x_coords = coords
        
        if len(y_coords) < 10:
            if self.debug_mode:
                print(f"[DEBUG] Too few cross pixels: {len(y_coords)}")
            return None
        
        # Calculate center (centroid)
        center_y_local = np.mean(y_coords)
        center_x_local = np.mean(x_coords)
        
        center_y = int(center_y_local) + y_offset
        center_x = int(center_x_local) + x_offset
        
        # Calculate size
        y_extent = y_coords.max() - y_coords.min()
        x_extent = x_coords.max() - x_coords.min()
        cross_size = max(y_extent, x_extent)
        
        if cross_size < 10:
            if self.debug_mode:
                print(f"[DEBUG] Cross too small: {cross_size}")
            return None
        
        # Calculate angle from topmost point
        # The topmost pixel of the cross indicates "up" direction
        top_idx = np.argmin(y_coords)
        top_y = y_coords[top_idx] - center_y_local
        top_x = x_coords[top_idx] - center_x_local
        
        # Angle from vertical: atan2(x, -y)
        # When top arm points straight up: x=0, y<0 → angle=0
        # When tilted right: x>0 → positive angle
        if abs(top_y) < 1 and abs(top_x) < 1:
            angle = 0.0
        else:
            angle = math.degrees(math.atan2(top_x, -top_y))
        
        if self.debug_mode:
            print(f"[DEBUG] Cross pixels: {len(y_coords)}")
            print(f"[DEBUG] Extent: x={x_extent}, y={y_extent}")
            print(f"[DEBUG] Center (local): ({center_x_local:.1f}, {center_y_local:.1f})")
            print(f"[DEBUG] Top arm at relative ({top_x:.1f}, {top_y:.1f})")
            print(f"[DEBUG] Calculated angle: {angle:.1f}°")
        
        return ((center_x, center_y), cross_size, angle)
    
    def _extract_signature_text(self, img: Image.Image) -> Image.Image:
        """Extract signature text pixels from cropped region."""
        arr = np.array(img.convert('RGB'))
        r, g, b = arr[:,:,0], arr[:,:,1], arr[:,:,2]
        
        # Signature text is cream/white colored
        text_mask = (
            (r > 180) & (g > 180) & (b > 140) &
            ((r.astype(int) + g.astype(int) + b.astype(int)) > 500)
        )
        
        result = np.zeros_like(r, dtype=np.uint8)
        result[text_mask] = 255
        
        return Image.fromarray(result, mode='L')
    
    def _ocr_signature(self, mask: Image.Image) -> Tuple[List[int], str]:
        """OCR the signature mask and extract numbers."""
        # Upscale for better OCR
        scale = 4
        upscaled = mask.resize(
            (mask.width * scale, mask.height * scale),
            Image.Resampling.LANCZOS
        )
        
        # Invert (Tesseract prefers black on white)
        inverted = ImageOps.invert(upscaled)
        
        if self.debug_mode:
            inverted.save(self.debug_dir / "05_ocr_input.png")
            self.last_debug_info['debug_files'].append("05_ocr_input.png")
        
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
    
    def open_identifier(self):
        """Run interactive HUD calibration."""
        if not HAS_CALIBRATION:
            print("Calibration module not available")
            return
        
        hud_calibration.calibrate_interactive()
        
        # Enable calibration mode after configuration
        if hud_calibration.is_configured():
            self.use_calibration = True
    
    def toggle_identifier(self, enable: Optional[bool] = None):
        """Toggle or set calibration mode.
        
        Args:
            enable: True to enable, False to disable, None to toggle
        """
        if enable is None:
            self.use_calibration = not self.use_calibration
        else:
            self.use_calibration = enable
        
        return self.use_calibration
    
    def is_identifier_configured(self) -> bool:
        """Check if HUD has been calibrated."""
        if HAS_CALIBRATION:
            return hud_calibration.is_configured()
        return False
    
    def _load_image(self, image_path: Path) -> Optional[Image.Image]:
        """Load an image."""
        return Image.open(image_path)

