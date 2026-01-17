#!/usr/bin/env python3
"""
Version checker for SC Signature Scanner.
Checks GitHub releases for updates.
"""

import urllib.request
import json
from typing import Tuple, Optional

# Try to use packaging for version comparison, fallback to simple string comparison
try:
    from packaging import version as pkg_version
    HAS_PACKAGING = True
except ImportError:
    HAS_PACKAGING = False


# Current version - update this with each release
CURRENT_VERSION = "3.1.7"

# GitHub repository info - UPDATE THESE when repo is created
GITHUB_OWNER = "Diftic"
GITHUB_REPO = "SC_Signature_Scanner"

# GitHub API URL for latest release
RELEASES_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"


def _parse_version_tuple(version_str: str) -> Tuple[int, ...]:
    """
    Parse a version string like '1.2.3' into a tuple (1, 2, 3).
    Fallback for when packaging module is not available.
    """
    try:
        parts = version_str.split('.')
        return tuple(int(p) for p in parts)
    except (ValueError, AttributeError):
        return (0, 0, 0)


def get_current_version() -> str:
    """Return the current application version."""
    return CURRENT_VERSION


def check_for_updates(timeout: int = 5) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Check GitHub for a newer version.
    
    Args:
        timeout: Request timeout in seconds
        
    Returns:
        Tuple of (update_available, latest_version, download_url)
        If check fails, returns (False, None, None)
    """
    try:
        # Create request with headers (GitHub API requires User-Agent)
        request = urllib.request.Request(
            RELEASES_URL,
            headers={
                'User-Agent': f'SC-Signature-Scanner/{CURRENT_VERSION}',
                'Accept': 'application/vnd.github.v3+json'
            }
        )
        
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode('utf-8'))
        
        # Extract version from tag (usually "v1.0.0" or "1.0.0")
        tag_name = data.get('tag_name', '')
        latest_ver = tag_name.lstrip('v')
        
        # Get download URL (HTML page for release)
        html_url = data.get('html_url', '')
        
        # Compare versions
        if latest_ver:
            try:
                if HAS_PACKAGING:
                    is_newer = pkg_version.parse(latest_ver) > pkg_version.parse(CURRENT_VERSION)
                else:
                    # Simple tuple comparison for semantic versions
                    is_newer = _parse_version_tuple(latest_ver) > _parse_version_tuple(CURRENT_VERSION)
                return (is_newer, latest_ver, html_url)
            except Exception:
                # Version parsing failed, assume update if different
                is_newer = latest_ver != CURRENT_VERSION
                return (is_newer, latest_ver, html_url)
        
        return (False, None, None)
        
    except urllib.error.HTTPError as e:
        if e.code == 404:
            # No releases yet
            return (False, None, None)
        print(f"HTTP error checking for updates: {e.code}")
        return (False, None, None)
        
    except Exception as e:
        print(f"Error checking for updates: {e}")
        return (False, None, None)


def get_release_notes(timeout: int = 5) -> Optional[str]:
    """
    Get release notes for the latest version.
    
    Returns:
        Release notes body text, or None if unavailable
    """
    try:
        request = urllib.request.Request(
            RELEASES_URL,
            headers={
                'User-Agent': f'SC-Signature-Scanner/{CURRENT_VERSION}',
                'Accept': 'application/vnd.github.v3+json'
            }
        )
        
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode('utf-8'))
        
        return data.get('body', '')
        
    except Exception:
        return None

