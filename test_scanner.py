#!/usr/bin/env python3
"""Quick test of signature scanner on a screenshot."""

from pathlib import Path
from scanner import SignatureScanner

def main():
    # Initialize scanner
    db_path = Path(__file__).parent / "data" / "combat_analyst_db.json"
    scanner = SignatureScanner(db_path)
    scanner.enable_debug(True)
    
    # Test on screenshot if available
    screenshots_dir = Path(r"C:\Users\larse\Pictures\Star Citizen")
    
    # Find recent JXR files
    jxr_files = list(screenshots_dir.glob("*.jxr"))
    if not jxr_files:
        print("No JXR files found in screenshots directory")
        print(f"Checked: {screenshots_dir}")
        return
    
    # Sort by modification time, newest first
    jxr_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    
    print(f"Found {len(jxr_files)} screenshots")
    print(f"Testing most recent: {jxr_files[0].name}\n")
    
    # Scan
    result = scanner.scan_image(jxr_files[0])
    
    if result is None:
        print("No signature detected")
        print("\nDebug info:")
        for key, val in scanner.last_debug_info.items():
            print(f"  {key}: {val}")
    elif 'error' in result:
        print(f"Error: {result['error']}")
    else:
        print(f"✓ Signature detected: {result['signature']:,}")
        print(f"  All signatures: {result.get('all_signatures', [])}")
        print(f"\nMatches:")
        for m in result.get('matches', [])[:5]:
            conf = m.get('confidence', 0) * 100
            print(f"  [{conf:.0f}%] {m.get('type')}: {m.get('name')}")
    
    print(f"\nDebug output saved to: {scanner.debug_dir}")

if __name__ == "__main__":
    main()
