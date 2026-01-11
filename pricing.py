"""
UEX Corp pricing integration for SC Signature Scanner.
Fetches ore prices from UEX API and calculates rock values using Regolith data.
"""

import json
import time
import urllib.request
import urllib.error
from typing import Dict, Optional, Tuple, List
from pathlib import Path


# Constants
UEX_API_BASE = "https://api.uexcorp.uk/2.0"
CACHE_TTL = 1800  # 30 minutes in seconds
DEFAULT_REFINERY_YIELD = 0.5  # 50% - volume conversion factor for refined material

# Mineral densities (kg per SCU) - from Lazarr Bandara's research paper
# These are tested and confirmed values for Star Citizen 4.2+
MINERAL_DENSITY = {
    'AGRICIUM': 239.71,
    'ALUMINUM': 89.88,
    'BERYL': 91.41,
    'BEXALITE': 230.03,
    'BORASE': 149.60,
    'COPPER': 298.37,
    'CORUNDUM': 133.85,
    'GOLD': 643.57,
    'HEPHAESTANITE': 106.54,
    'ICE': 33.19,
    'INERTMATERIAL': 33.21,
    'IRON': 262.42,
    'LARANITE': 383.09,
    'QUANTANIUM': 681.26,
    'QUARTZ': 88.30,
    'RICCITE': 53.28,
    'SILICON': 77.82,
    'STILERON': 158.20,
    'TARANITE': 339.67,
    'TIN': 192.04,
    'TITANIUM': 149.61,
    'TUNGSTEN': 642.94,
    # NYX minerals (densities TBD - using estimates)
    'LINDINIUM': 200.00,  # Placeholder
    'TORITE': 200.00,     # Placeholder
}


class PricingManager:
    """Manages ore pricing data from UEX and rock composition from Regolith."""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.cache_file = self.data_dir / "uex_prices.json"
        self.rock_types_file = self.data_dir / "rock_types.json"
        
        # Data stores
        self.ore_prices: Dict[str, float] = {}  # ORE_NAME -> price per SCU
        self.rock_types: Dict = {}  # System -> RockType -> data
        self.commodities: Dict[int, dict] = {}  # id -> commodity data
        
        # Status
        self.last_fetch: float = 0
        self.fetch_error: Optional[str] = None
        self.prices_loaded: bool = False
        self.rock_types_loaded: bool = False
        
        # Refinery yield factor (adjustable by user)
        self.refinery_yield: float = DEFAULT_REFINERY_YIELD
        
    def initialize(self) -> bool:
        """Load rock types and fetch/load prices. Returns True if successful."""
        # Load Regolith rock types
        self._load_rock_types()
        
        # Load cached prices or fetch new
        if not self._load_cached_prices():
            self.refresh_prices()
            
        return self.prices_loaded
        
    def _load_rock_types(self) -> bool:
        """Load rock types from Regolith JSON."""
        try:
            with open(self.rock_types_file, 'r', encoding='utf-8') as f:
                self.rock_types = json.load(f)
            self.rock_types_loaded = True
            self.fetch_error = None
            return True
        except FileNotFoundError:
            self.fetch_error = f"Rock types file not found: {self.rock_types_file}"
            self.rock_types_loaded = False
            return False
        except json.JSONDecodeError as e:
            self.fetch_error = f"Invalid rock types JSON: {e}"
            self.rock_types_loaded = False
            return False
            
    def _load_cached_prices(self) -> bool:
        """Load prices from cache if valid."""
        try:
            if not self.cache_file.exists():
                return False
                
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cache = json.load(f)
                
            # Check cache age
            cached_time = cache.get('timestamp', 0)
            if time.time() - cached_time > CACHE_TTL:
                return False  # Cache expired
                
            self.ore_prices = cache.get('ore_prices', {})
            self.commodities = {int(k): v for k, v in cache.get('commodities', {}).items()}
            self.refinery_yield = cache.get('refinery_yield', DEFAULT_REFINERY_YIELD)
            self.last_fetch = cached_time
            self.prices_loaded = bool(self.ore_prices)
            return self.prices_loaded
            
        except (json.JSONDecodeError, KeyError, ValueError):
            return False
            
    def _save_cache(self):
        """Save prices to cache file."""
        cache = {
            'timestamp': self.last_fetch,
            'ore_prices': self.ore_prices,
            'commodities': {str(k): v for k, v in self.commodities.items()},
            'refinery_yield': self.refinery_yield
        }
        self.data_dir.mkdir(exist_ok=True)
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(cache, f, indent=2)
            
    def get_refinery_yield(self) -> float:
        """Get current refinery yield factor (0.0 to 1.0)."""
        return self.refinery_yield
        
    def set_refinery_yield(self, yield_factor: float):
        """
        Set refinery yield factor.
        
        Args:
            yield_factor: Value between 0.0 and 1.0 (e.g., 0.5 = 50%)
        """
        self.refinery_yield = max(0.0, min(1.0, yield_factor))
        self._save_cache()  # Persist the setting
            
    def refresh_prices(self) -> bool:
        """Fetch fresh prices from UEX API."""
        self.fetch_error = None
        
        try:
            # Fetch commodities list
            url = f"{UEX_API_BASE}/commodities"
            req = urllib.request.Request(
                url, 
                headers={
                    'User-Agent': 'SC-Signature-Scanner/1.0',
                    'Accept': 'application/json'
                }
            )
            
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.loads(response.read().decode('utf-8'))
                
            if data.get('status') != 'ok':
                self.fetch_error = f"UEX API error: {data.get('status')}"
                return False
                
            # Process commodities - extract ore prices
            self.ore_prices = {}
            self.commodities = {}
            
            for commodity in data.get('data', []):
                cid = commodity['id']
                self.commodities[cid] = commodity
                
                # Normalize name - strip suffixes and uppercase
                name = commodity['name'].upper()
                for suffix in [' (ORE)', ' (RAW)']:
                    if name.endswith(suffix):
                        name = name[:-len(suffix)]
                        break
                
                # Map to Regolith naming conventions
                name = self._normalize_ore_name(name)
                
                # Get price - prefer raw ore sell price
                if commodity.get('is_raw') == 1:
                    price = commodity.get('price_sell', 0)
                    if price > 0:
                        self.ore_prices[name] = price
                elif commodity.get('is_refined') == 1:
                    # Use refined price if we don't have raw
                    price = commodity.get('price_sell', 0)
                    if price > 0 and name not in self.ore_prices:
                        self.ore_prices[name] = price
                        
            self.last_fetch = time.time()
            self.prices_loaded = bool(self.ore_prices)
            self._save_cache()
            return self.prices_loaded
            
        except urllib.error.URLError as e:
            self.fetch_error = f"Network error: {e.reason}"
            return False
        except urllib.error.HTTPError as e:
            self.fetch_error = f"HTTP error {e.code}: {e.reason}"
            return False
        except json.JSONDecodeError as e:
            self.fetch_error = f"Invalid API response: {e}"
            return False
        except Exception as e:
            self.fetch_error = f"Error fetching prices: {e}"
            return False
            
    def _normalize_ore_name(self, name: str) -> str:
        """Normalize ore name to match Regolith conventions."""
        # UEX -> Regolith mapping
        mappings = {
            'INERT MATERIALS': 'INERTMATERIAL',
            'QUANTAINIUM': 'QUANTANIUM',
            'RAW ICE': 'ICE',
        }
        return mappings.get(name, name)
        
    def get_ore_price(self, ore_name: str) -> float:
        """Get price per SCU for an ore. Returns 0 if not found."""
        name = ore_name.upper().strip()
        
        # Try direct match
        if name in self.ore_prices:
            return self.ore_prices[name]
            
        # Try with common variations
        variations = [
            name.replace('_', ' '),
            name.replace(' ', ''),
        ]
        for var in variations:
            if var in self.ore_prices:
                return self.ore_prices[var]
                
        return 0
        
    def calculate_rock_value(
        self, 
        system: str, 
        rock_type: str,
        mass_override: Optional[float] = None,
        apply_refinery_yield: bool = True
    ) -> Tuple[float, Dict[str, Tuple[float, float, float, float]]]:
        """
        Calculate estimated value for a rock type.
        
        Args:
            system: Star system (e.g., "STANTON", "PYRO")
            rock_type: Rock type (e.g., "CTYPE", "QTYPE", "GRANITE")
            mass_override: Optional mass to use instead of median
            apply_refinery_yield: Whether to apply refinery yield factor (default True)
            
        Returns:
            Tuple of (total_value, {ore_name: (value, percentage, price, density)})
            
        Note:
            Value calculation per Lazarr Bandara's research:
            1. mineral_mass = deposit_mass × medPct × probability
            2. mineral_volume = mineral_mass / density
            3. value = mineral_volume × price × refinery_yield
        """
        system = system.upper()
        rock_type = rock_type.upper()
        
        # Get rock data
        system_data = self.rock_types.get(system, {})
        rock_data = system_data.get(rock_type)
        
        if not rock_data:
            return 0, {}
            
        mass = mass_override if mass_override else rock_data.get('mass', {}).get('med', 0)
        ores = rock_data.get('ores', {})
        
        # Apply refinery yield factor if enabled
        yield_factor = self.refinery_yield if apply_refinery_yield else 1.0
        
        total_value = 0
        ore_breakdown: Dict[str, Tuple[float, float, float, float]] = {}
        
        for ore_name, ore_data in ores.items():
            if ore_name == 'INERTMATERIAL':
                continue  # Skip inert, basically worthless
                
            median_pct = ore_data.get('medPct', 0)
            probability = ore_data.get('prob', 0)
            
            # Get price and density for this ore
            price = self.get_ore_price(ore_name)
            density = MINERAL_DENSITY.get(ore_name.upper(), 100.0)  # Default density if unknown
            
            if price > 0 and median_pct > 0 and probability > 0 and density > 0:
                # Step 1: Calculate mineral mass
                mineral_mass = mass * median_pct * probability
                
                # Step 2: Convert mass to volume (SCU)
                mineral_volume = mineral_mass / density
                
                # Step 3: Calculate value = volume × price × yield
                ore_value = mineral_volume * price * yield_factor
                
                ore_breakdown[ore_name] = (ore_value, median_pct, price, density)
                total_value += ore_value
                
        return total_value, ore_breakdown
        
    def get_rock_summary(self, system: str, rock_type: str) -> Optional[dict]:
        """Get summary info for a rock type including estimated value."""
        system = system.upper()
        rock_type = rock_type.upper()
        
        system_data = self.rock_types.get(system, {})
        rock_data = system_data.get(rock_type)
        
        if not rock_data:
            return None
            
        value, ore_breakdown = self.calculate_rock_value(system, rock_type)
        
        # Get top ores by value contribution
        # ore_breakdown format: {name: (value, pct, price, density)}
        top_ores = sorted(
            [(name, data[0], data[1], data[2], data[3]) for name, data in ore_breakdown.items()],
            key=lambda x: x[1], 
            reverse=True
        )[:5]
        
        return {
            'rock_type': rock_type,
            'system': system,
            'median_mass': rock_data.get('mass', {}).get('med', 0),
            'mass_range': (
                rock_data.get('mass', {}).get('min', 0),
                rock_data.get('mass', {}).get('max', 0)
            ),
            'median_instability': rock_data.get('inst', {}).get('med', 0),
            'median_resistance': rock_data.get('res', {}).get('med', 0),
            'estimated_value': value,
            'top_ores': top_ores,  # [(name, value, pct, price, density), ...]
            'scans': rock_data.get('scans', 0),
            'users': rock_data.get('users', 0)
        }
        
    def get_available_systems(self) -> List[str]:
        """Get list of systems with rock data."""
        return list(self.rock_types.keys())
        
    def get_rock_types_for_system(self, system: str) -> List[str]:
        """Get list of rock types for a system (excluding nulls)."""
        system_data = self.rock_types.get(system.upper(), {})
        return [k for k, v in system_data.items() if v is not None]
        
    def get_status(self) -> dict:
        """Get current status of pricing system."""
        return {
            'prices_loaded': self.prices_loaded,
            'rock_types_loaded': self.rock_types_loaded,
            'ore_count': len(self.ore_prices),
            'systems': self.get_available_systems(),
            'last_fetch': self.last_fetch,
            'cache_age_seconds': time.time() - self.last_fetch if self.last_fetch else None,
            'refinery_yield': self.refinery_yield,
            'refinery_yield_pct': int(self.refinery_yield * 100),
            'error': self.fetch_error
        }


# Module-level singleton
_pricing_manager: Optional[PricingManager] = None


def get_pricing_manager() -> PricingManager:
    """Get or create the global pricing manager instance."""
    global _pricing_manager
    if _pricing_manager is None:
        _pricing_manager = PricingManager()
    return _pricing_manager


def initialize_pricing() -> Tuple[bool, Optional[str]]:
    """
    Initialize pricing system on app start.
    
    Returns:
        Tuple of (success, error_message)
    """
    manager = get_pricing_manager()
    success = manager.initialize()
    return success, manager.fetch_error if not success else None


def refresh_pricing() -> Tuple[bool, Optional[str]]:
    """
    Force refresh prices from UEX API.
    
    Returns:
        Tuple of (success, error_message)
    """
    manager = get_pricing_manager()
    success = manager.refresh_prices()
    return success, manager.fetch_error if not success else None


def get_rock_value(system: str, rock_type: str) -> float:
    """Quick helper to get estimated value for a rock type."""
    manager = get_pricing_manager()
    value, _ = manager.calculate_rock_value(system, rock_type)
    return value


def get_refinery_yield() -> float:
    """Get current refinery yield factor."""
    return get_pricing_manager().get_refinery_yield()


def set_refinery_yield(yield_factor: float):
    """Set refinery yield factor (0.0 to 1.0)."""
    get_pricing_manager().set_refinery_yield(yield_factor)

