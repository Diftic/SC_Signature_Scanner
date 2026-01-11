#!/usr/bin/env python3
"""
Signature scanner for SC Signature Scanner.
Detects signature values from Star Citizen screenshots using cross detection.

Algorithm:
1. Find the cross (velocity/aim indicator) - pink/magenta colored
2. Calculate cross orientation → determines image rotation
3. Rotate image to normalize (cross arms should be horizontal/vertical)
4. Use cross size/position to calculate signature location (fixed offset above)
5. OCR that specific region
"""

import json
import math
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from PIL import Image, ImageOps
import numpy as np

# Import pricing module
try:
    import pricing
    HAS_PRICING = True
except ImportError:
    HAS_PRICING = False

try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False
    print("Warning: pytesseract not installed. OCR disabled.")


# Signature to rock type mapping for pricing
SIGNATURE_TO_ROCK_TYPE = {
    # Asteroids
    1660: ('ITYPE', 'asteroid'),
    1700: ('CTYPE', 'asteroid'),
    1720: ('STYPE', 'asteroid'),
    1750: ('PTYPE', 'asteroid'),
    1850: ('MTYPE', 'asteroid'),
    1870: ('QTYPE', 'asteroid'),
    1900: ('ETYPE', 'asteroid'),
    # Surface deposits
    1730: ('SHALE', 'deposit'),
    1770: ('FELSIC', 'deposit'),
    1790: ('OBSIDIAN', 'deposit'),
    1800: ('ATACAMITE', 'deposit'),
    1820: ('QUARTZITE', 'deposit'),
    1840: ('GNEISS', 'deposit'),
    1920: ('GRANITE', 'deposit'),
    1950: ('IGNEOUS', 'deposit'),
}


class SignatureScanner:
    """Scans screenshots for signature values using red cross detection."""
    
    def __init__(self, db_path: Path, system: str = 'STANTON'):
        self.db = self._load_database(db_path)
        self.system = system.upper()  # Default system for pricing
        self._build_lookups()
        
        self.debug_mode = False
        self.debug_dir = Path(__file__).parent / "debug_output"
        self.last_debug_info = {}
        
        # JXR conversion
        self._jxr_tool_checked = False
        self._jxr_tool_available = None
        self._jxr_tool_path = None
    
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
        
        self.minable_signatures = {}
        for category, items in self.db.get('minables', {}).items():
            for name, sig in items.items():
                self.minable_signatures[sig] = {'name': name, 'category': category}
    
    def scan_image(self, image_path: Path) -> Optional[Dict[str, Any]]:
        """Scan an image for signature values."""
        if not HAS_TESSERACT:
            return {'error': 'Tesseract not installed'}
        
        self.last_debug_info = {
            'image_path': str(image_path),
            'debug_files': []
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
            
            # STEP 1: Find the cross (pink/magenta)
            cross_result = self._find_cross(img)
            
            if cross_result is None:
                if self.debug_mode:
                    print("[DEBUG] Cross not found")
                    with open(self.debug_dir / "99_summary.txt", 'w') as f:
                        f.write(f"Image: {image_path.name}\n")
                        f.write(f"Size: {width}x{height}\n")
                        f.write(f"FAILED: Cross not detected\n")
                return None
            
            cross_center, cross_size, angle = cross_result
            
            if self.debug_mode:
                print(f"[DEBUG] Cross center: {cross_center}")
                print(f"[DEBUG] Cross size: {cross_size}")
                print(f"[DEBUG] Angle: {angle:.1f}°")
            
            # STEP 2: Rotate image if needed
            if abs(angle) > 1:
                img_rotated = img.rotate(angle, expand=False, center=cross_center, fillcolor=(0, 0, 0))
            else:
                img_rotated = img
            
            # STEP 3: Calculate signature position
            # Cross size = 1 unit. Signature is offset from cross center:
            # X = +6.3 units (to the right)
            # Y = -3.2 units (up, negative in screen coords)
            unit = cross_size  # 1 unit = cross width/height
            
            sig_x = cross_center[0] + int(unit * 6.3)
            sig_y = cross_center[1] - int(unit * 3.2)
            
            # Search region around signature (generous padding)
            padding_x = int(unit * 1.5)
            padding_y = int(unit * 1.0)
            
            x1 = max(0, sig_x - padding_x)
            y1 = max(0, sig_y - padding_y)
            x2 = min(width, sig_x + padding_x)
            y2 = min(height, sig_y + padding_y)
            
            if self.debug_mode:
                print(f"[DEBUG] Signature region: ({x1}, {y1}) - ({x2}, {y2})")
                
                # Draw detection overlay
                from PIL import ImageDraw
                debug_img = img.copy()
                draw = ImageDraw.Draw(debug_img)
                
                # Draw cross center
                r = 15
                draw.ellipse([cross_center[0]-r, cross_center[1]-r, 
                             cross_center[0]+r, cross_center[1]+r], 
                            outline='#FF0000', width=3)
                
                # Draw signature region
                draw.rectangle([x1, y1, x2, y2], outline='#00FF00', width=3)
                
                # Draw line from cross to signature
                draw.line([cross_center, (sig_x, sig_y)], fill='#FFFF00', width=2)
                
                debug_img.save(self.debug_dir / "02_detection.png")
                self.last_debug_info['debug_files'].append("02_detection.png")
            
            # STEP 4: Extract and OCR signature region
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
                    'debug': self.last_debug_info if self.debug_mode else None
                }
            
            return None
            
        except Exception as e:
            if self.debug_mode:
                import traceback
                with open(self.debug_dir / "99_error.txt", 'w') as f:
                    f.write(traceback.format_exc())
            return {'error': str(e)}
    
    def _find_cross(self, img: Image.Image) -> Optional[Tuple[Tuple[int, int], int, float]]:
        """Find the cross (velocity/aim indicator).
        
        The cross is PINK/MAGENTA colored with 4 chevron arms pointing outward.
        The chevrons may be separate connected components, so we:
        1. Find all pink/magenta clusters
        2. Group nearby clusters that could form a cross
        3. Find the group with cross-like geometry (roughly square bounding box)
        4. Calculate angle from the topmost point
        
        Returns:
            Tuple of (center_xy, size, angle_degrees) or None if not found.
            Angle is rotation from vertical (positive = clockwise).
        """
        width, height = img.size
        arr = np.array(img)
        
        # Search in center region of screen
        x_min, x_max = int(width * 0.25), int(width * 0.75)
        y_min, y_max = int(height * 0.25), int(height * 0.75)
        
        search = arr[y_min:y_max, x_min:x_max]
        r, g, b = search[:,:,0], search[:,:,1], search[:,:,2]
        
        # Pink/magenta cross detection: high R, high B, lower G
        cross_mask = (
            (r > 170) &           # High red
            (b > 170) &           # High blue
            (r > g) &             # More red than green
            (b > g) &             # More blue than green  
            (g < 215)             # Green not too high (not white)
        )
        
        if self.debug_mode:
            mask_img = Image.fromarray((cross_mask * 255).astype(np.uint8), mode='L')
            mask_img.save(self.debug_dir / "01_cross_mask.png")
            self.last_debug_info['debug_files'].append("01_cross_mask.png")
        
        if not cross_mask.any():
            if self.debug_mode:
                print("[DEBUG] No pink/magenta pixels found")
            return None
        
        # Find connected components
        try:
            from scipy import ndimage
            labeled, num_features = ndimage.label(cross_mask)
        except ImportError:
            # Fallback: use all pink pixels as one cluster
            cross_coords = np.where(cross_mask)
            if len(cross_coords[0]) < 10:
                return None
            return self._analyze_cross_pixels(cross_coords, x_min, y_min)
        
        # Collect all clusters
        clusters = []
        for i in range(1, num_features + 1):
            cluster_mask = labeled == i
            size = np.sum(cluster_mask)
            
            if size < 3:  # Noise
                continue
            
            coords = np.where(cluster_mask)
            y_coords, x_coords = coords
            
            clusters.append({
                'id': i,
                'size': size,
                'center_x': np.mean(x_coords),
                'center_y': np.mean(y_coords),
                'min_x': x_coords.min(),
                'max_x': x_coords.max(),
                'min_y': y_coords.min(),
                'max_y': y_coords.max(),
                'y_coords': y_coords,
                'x_coords': x_coords
            })
        
        if self.debug_mode:
            print(f"[DEBUG] Found {len(clusters)} clusters")
            for c in clusters:
                ext_x = c['max_x'] - c['min_x']
                ext_y = c['max_y'] - c['min_y']
                print(f"[DEBUG]   Cluster {c['id']}: size={c['size']}, center=({c['center_x']:.0f}, {c['center_y']:.0f}), extent=({ext_x}, {ext_y})")
        
        if not clusters:
            if self.debug_mode:
                print("[DEBUG] No valid clusters found")
            return None
        
        # Strategy: Group nearby clusters and find cross-shaped groups
        # A cross should have roughly equal width and height (aspect ~1)
        # The gradient bar is very elongated (aspect >> 1)
        
        best_group = None
        best_score = 0
        
        # Try each cluster as a potential cross center
        for anchor in clusters:
            # Find clusters within grouping distance (100 pixels)
            group_dist = 100
            group = [anchor]
            
            for other in clusters:
                if other['id'] == anchor['id']:
                    continue
                dist = math.sqrt(
                    (anchor['center_x'] - other['center_x'])**2 +
                    (anchor['center_y'] - other['center_y'])**2
                )
                if dist < group_dist:
                    group.append(other)
            
            if len(group) < 2:  # Need at least 2 components
                continue
            
            # Calculate bounding box of group
            all_min_x = min(c['min_x'] for c in group)
            all_max_x = max(c['max_x'] for c in group)
            all_min_y = min(c['min_y'] for c in group)
            all_max_y = max(c['max_y'] for c in group)
            
            group_width = all_max_x - all_min_x
            group_height = all_max_y - all_min_y
            
            if group_width < 10 or group_height < 10:
                continue
            
            # Aspect ratio should be close to 1 for a cross
            aspect = max(group_width, group_height) / max(1, min(group_width, group_height))
            
            # Total pixels in group
            total_size = sum(c['size'] for c in group)
            
            # Score: prefer larger groups with square aspect
            # Heavily penalize elongated shapes (gradient bar)
            if aspect > 3:
                continue  # Too elongated, skip
            
            score = total_size / (aspect ** 2)  # Square penalty for elongation
            
            if self.debug_mode:
                print(f"[DEBUG]   Group around {anchor['id']}: {len(group)} clusters, size={total_size}, bbox=({group_width}x{group_height}), aspect={aspect:.2f}, score={score:.0f}")
            
            if score > best_score:
                best_score = score
                best_group = group
        
        if best_group is None:
            if self.debug_mode:
                print("[DEBUG] No valid cross group found")
            return None
        
        if self.debug_mode:
            print(f"[DEBUG] Selected group with {len(best_group)} clusters, score={best_score:.0f}")
        
        # Combine all pixels from the group
        all_y = np.concatenate([c['y_coords'] for c in best_group])
        all_x = np.concatenate([c['x_coords'] for c in best_group])
        
        return self._analyze_cross_pixels((all_y, all_x), x_min, y_min)
    
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
        
        # Check minables (asteroids, deposits, fps gems)
        for base_sig, info in self.minable_signatures.items():
            if base_sig == 0:
                continue
            # Skip FPS mining and ground vehicle - only asteroids and deposits
            if info['category'] in ('fps_mining', 'ground_vehicle'):
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
        
        # Ships removed per user request
        
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
    
    def _check_jxr_support(self) -> bool:
        """Check if JXR conversion is available."""
        if self._jxr_tool_checked:
            return self._jxr_tool_available
        
        self._jxr_tool_checked = True
        
        import platform
        if platform.system() == 'Windows':
            self._jxr_tool_available = True
            self._jxr_tool_path = 'wic'
            return True
        
        try:
            result = subprocess.run(['magick', '--version'], capture_output=True, timeout=5)
            if result.returncode == 0:
                self._jxr_tool_available = True
                self._jxr_tool_path = 'magick'
                return True
        except:
            pass
        
        self._jxr_tool_available = False
        return False
    
    def _convert_jxr_to_png(self, jxr_path: Path) -> Optional[Path]:
        """Convert JXR to PNG."""
        if not self._check_jxr_support():
            return None
        
        temp_dir = Path(tempfile.gettempdir()) / "sc_signature_scanner"
        temp_dir.mkdir(exist_ok=True)
        output_path = temp_dir / f"{jxr_path.stem}.png"
        
        try:
            if self._jxr_tool_path == 'wic':
                ps_script = f'''
Add-Type -AssemblyName PresentationCore
try {{
    $stream = [System.IO.File]::OpenRead("{jxr_path}")
    $decoder = New-Object System.Windows.Media.Imaging.WmpBitmapDecoder(
        $stream, [System.Windows.Media.Imaging.BitmapCreateOptions]::None,
        [System.Windows.Media.Imaging.BitmapCacheOption]::OnLoad)
    $frame = $decoder.Frames[0]
    $converted = New-Object System.Windows.Media.Imaging.FormatConvertedBitmap
    $converted.BeginInit()
    $converted.Source = $frame
    $converted.DestinationFormat = [System.Windows.Media.PixelFormats]::Rgb24
    $converted.EndInit()
    $encoder = New-Object System.Windows.Media.Imaging.PngBitmapEncoder
    $encoder.Frames.Add([System.Windows.Media.Imaging.BitmapFrame]::Create($converted))
    $outStream = [System.IO.File]::Create("{output_path}")
    $encoder.Save($outStream)
    $outStream.Close()
    $stream.Close()
    Write-Output "SUCCESS"
}} catch {{ Write-Error $_.Exception.Message; exit 1 }}
'''
                result = subprocess.run(
                    ['powershell', '-ExecutionPolicy', 'Bypass', '-Command', ps_script],
                    capture_output=True, text=True, timeout=60
                )
                if 'SUCCESS' not in result.stdout:
                    return None
            elif self._jxr_tool_path == 'magick':
                result = subprocess.run(
                    ['magick', str(jxr_path), str(output_path)],
                    capture_output=True, timeout=30
                )
                if result.returncode != 0:
                    return None
            
            return output_path if output_path.exists() else None
        except:
            return None
    
    def _load_image(self, image_path: Path) -> Optional[Image.Image]:
        """Load an image, converting JXR if needed."""
        suffix = image_path.suffix.lower()
        
        if suffix in ['.jxr', '.hdp', '.wdp']:
            png_path = self._convert_jxr_to_png(image_path)
            if png_path:
                return Image.open(png_path)
            return None
        
        return Image.open(image_path)


def main():
    """Test the scanner."""
    db_path = Path(__file__).parent / "data" / "combat_analyst_db.json"
    scanner = SignatureScanner(db_path)
    
    test_sigs = [1850, 1700, 3400, 13424, 2000, 6000]
    
    print("Testing signature matching:\n")
    for sig in test_sigs:
        print(f"Signature: {sig:,}")
        matches = scanner.match_signature(sig)
        for m in matches[:3]:
            print(f"  [{m.get('confidence', 0)*100:.0f}%] {m.get('type')}: {m.get('name')}")
        print()


if __name__ == "__main__":
    main()
