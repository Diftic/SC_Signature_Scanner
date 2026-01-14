#!/usr/bin/env python3
"""
Regolith.rocks API Client for SC Signature Scanner.

Handles:
- API key validation
- Data fetching (lookups, survey data)
- Local cache management (7-day expiry)

API Documentation: See RegolithAPI/API_DOCUMENTATION.md
"""

import json
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

import paths


# API Configuration
API_URL = "https://api.regolith.rocks"
CACHE_FILE = "regolith_cache.json"
CACHE_MAX_AGE_DAYS = 7
CURRENT_EPOCH = "4.4"  # Current Star Citizen version


class RegolithAPIError(Exception):
    """Exception for Regolith API errors."""
    pass


class RegolithAPI:
    """Client for Regolith.rocks GraphQL API."""
    
    def __init__(self, api_key: str = None):
        """Initialize the API client.
        
        Args:
            api_key: Regolith.rocks API key (from profile/api page)
        """
        self.api_key = api_key
        self.cache_path = paths.get_user_data_path() / CACHE_FILE
        self._cache: Optional[Dict[str, Any]] = None
    
    def set_api_key(self, api_key: str):
        """Set or update the API key."""
        self.api_key = api_key
    
    def _make_request(self, query: str, variables: Dict = None) -> Dict[str, Any]:
        """Make a GraphQL request to the API.
        
        Args:
            query: GraphQL query string
            variables: Optional query variables
            
        Returns:
            Response data dict
            
        Raises:
            RegolithAPIError: On API errors or network issues
        """
        if not self.api_key:
            raise RegolithAPIError("API key not set")
        
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key
        }
        
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        
        try:
            response = requests.post(API_URL, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if "errors" in data:
                error_msg = data["errors"][0].get("message", "Unknown API error")
                raise RegolithAPIError(f"API error: {error_msg}")
            
            return data.get("data", {})
            
        except requests.exceptions.Timeout:
            raise RegolithAPIError("API request timed out")
        except requests.exceptions.ConnectionError:
            raise RegolithAPIError("Could not connect to Regolith.rocks API")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                raise RegolithAPIError("Invalid API key")
            elif e.response.status_code == 403:
                raise RegolithAPIError("API key unauthorized")
            elif e.response.status_code == 429:
                raise RegolithAPIError("Rate limit exceeded (3,600 requests/day)")
            elif e.response.status_code >= 500:
                raise RegolithAPIError(f"Regolith.rocks server error ({e.response.status_code}). Try again later.")
            else:
                raise RegolithAPIError(f"HTTP error: {e.response.status_code}")
        except json.JSONDecodeError:
            raise RegolithAPIError("Invalid response from API")
    
    def validate_key(self) -> Tuple[bool, str]:
        """Validate the API key by fetching user profile.
        
        Returns:
            Tuple of (is_valid, message)
            - If valid: (True, username)
            - If invalid: (False, error_message)
        """
        query = """
        {
            profile {
                userId
                scName
                plan
                state
            }
        }
        """
        
        try:
            data = self._make_request(query)
            profile = data.get("profile")
            
            if not profile:
                return False, "Could not retrieve profile"
            
            sc_name = profile.get("scName", "Unknown")
            plan = profile.get("plan", "FREE")
            
            return True, f"{sc_name} ({plan})"
            
        except RegolithAPIError as e:
            return False, str(e)
    
    def fetch_lookups(self) -> Dict[str, Any]:
        """Fetch reference data (densities, prices, refinery methods).
        
        Returns:
            Dict with CIG and UEX lookup data
        """
        query = """
        {
            lookups {
                CIG {
                    densitiesLookups
                    methodsBonusLookup
                    oreProcessingLookup
                }
                UEX {
                    maxPrices
                    refineryBonuses
                }
            }
        }
        """
        
        data = self._make_request(query)
        return data.get("lookups", {})
    
    def fetch_survey_data(self, data_name: str, epoch: str = CURRENT_EPOCH) -> Dict[str, Any]:
        """Fetch survey statistics.
        
        Args:
            data_name: Dataset name (e.g., 'shipOreByRockClassProb', 'vehicleProbs')
            epoch: Game version (default: current)
            
        Returns:
            Survey data dict
        """
        query = """
        query ($dataName: String!, $epoch: String!) {
            surveyData(dataName: $dataName, epoch: $epoch) {
                data
                dataName
                epoch
                lastUpdated
            }
        }
        """
        
        variables = {"dataName": data_name, "epoch": epoch}
        data = self._make_request(query, variables)
        
        survey = data.get("surveyData", {})
        return survey.get("data", {})
    
    def fetch_all_data(self) -> Dict[str, Any]:
        """Fetch all required data for the scanner.
        
        Returns:
            Complete data dict with lookups and survey data
        """
        result = {
            "last_updated": datetime.utcnow().isoformat() + "Z",
            "epoch": CURRENT_EPOCH,
            "lookups": {},
            "rock_compositions": {},
            "location_bonuses": {}
        }
        
        # Fetch lookups (prices, densities, refinery methods)
        result["lookups"] = self.fetch_lookups()
        
        # Fetch rock compositions by type (for signature → value calculation)
        for system in ["STANTON", "PYRO", "NYX"]:
            try:
                rock_data = self.fetch_survey_data("shipOreByRockClassProb")
                if system in rock_data:
                    result["rock_compositions"][system] = rock_data[system]
            except RegolithAPIError:
                pass  # System might not have data
        
        # Fetch location bonuses
        try:
            result["location_bonuses"] = self.fetch_survey_data("bonusMap")
        except RegolithAPIError:
            result["location_bonuses"] = {}
        
        return result
    
    # === Cache Management ===
    
    def load_cache(self) -> Optional[Dict[str, Any]]:
        """Load cached data from disk.
        
        Returns:
            Cached data dict, or None if no valid cache exists
        """
        if not self.cache_path.exists():
            return None
        
        try:
            with open(self.cache_path, 'r', encoding='utf-8') as f:
                self._cache = json.load(f)
                return self._cache
        except (json.JSONDecodeError, IOError):
            return None
    
    def save_cache(self, data: Dict[str, Any]):
        """Save data to cache file.
        
        Args:
            data: Data dict to cache
        """
        self._cache = data
        
        try:
            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save cache: {e}")
    
    def is_cache_valid(self) -> bool:
        """Check if cache exists and is less than 7 days old.
        
        Returns:
            True if cache is valid, False otherwise
        """
        cache = self.load_cache()
        if not cache:
            return False
        
        last_updated_str = cache.get("last_updated")
        if not last_updated_str:
            return False
        
        try:
            # Parse ISO format timestamp
            last_updated = datetime.fromisoformat(last_updated_str.replace("Z", "+00:00"))
            age = datetime.now(last_updated.tzinfo) - last_updated
            
            return age < timedelta(days=CACHE_MAX_AGE_DAYS)
        except (ValueError, TypeError):
            return False
    
    def get_cache_age_str(self) -> str:
        """Get human-readable cache age.
        
        Returns:
            String like "2 days ago" or "Unknown"
        """
        cache = self.load_cache()
        if not cache:
            return "No cache"
        
        last_updated_str = cache.get("last_updated")
        if not last_updated_str:
            return "Unknown"
        
        try:
            last_updated = datetime.fromisoformat(last_updated_str.replace("Z", "+00:00"))
            age = datetime.now(last_updated.tzinfo) - last_updated
            
            if age.days == 0:
                hours = age.seconds // 3600
                if hours == 0:
                    return "Just now"
                elif hours == 1:
                    return "1 hour ago"
                else:
                    return f"{hours} hours ago"
            elif age.days == 1:
                return "1 day ago"
            else:
                return f"{age.days} days ago"
        except (ValueError, TypeError):
            return "Unknown"
    
    def get_cached_data(self) -> Optional[Dict[str, Any]]:
        """Get cached data if available.
        
        Returns:
            Cached data dict, or None
        """
        if self._cache:
            return self._cache
        return self.load_cache()
    
    def refresh_cache(self) -> Tuple[bool, str]:
        """Fetch fresh data and update cache.
        
        Returns:
            Tuple of (success, message)
        """
        try:
            data = self.fetch_all_data()
            self.save_cache(data)
            return True, f"Data refreshed (epoch {CURRENT_EPOCH})"
        except RegolithAPIError as e:
            return False, str(e)
    
    def clear_cache(self):
        """Delete the cache file."""
        if self.cache_path.exists():
            self.cache_path.unlink()
        self._cache = None


# === Module-level convenience functions ===

_instance: Optional[RegolithAPI] = None


def get_api(api_key: str = None) -> RegolithAPI:
    """Get or create the global API instance.
    
    Args:
        api_key: Optional API key to set
        
    Returns:
        RegolithAPI instance
    """
    global _instance
    
    if _instance is None:
        _instance = RegolithAPI(api_key)
    elif api_key:
        _instance.set_api_key(api_key)
    
    return _instance


def validate_api_key(api_key: str) -> Tuple[bool, str]:
    """Validate an API key.
    
    Args:
        api_key: Key to validate
        
    Returns:
        Tuple of (is_valid, message)
    """
    api = get_api(api_key)
    return api.validate_key()
