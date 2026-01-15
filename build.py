#!/usr/bin/env python3
"""
Build script for SC Signature Scanner.
Creates a standalone .exe distribution using PyInstaller.

Author: Mallachi
"""

import subprocess
import shutil
import sys
from pathlib import Path


def print_header(text: str):
    """Print a formatted header."""
    print()
    print("=" * 60)
    print(f"  {text}")
    print("=" * 60)
    print()


def print_section(text: str):
    """Print a section header."""
    print(f"\n[{text}]")


def run_command(cmd: list, description: str) -> bool:
    """Run a command and return success status."""
    print(f"  {description}...")
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        if result.stdout:
            for line in result.stdout.strip().split('\n'):
                print(f"    {line}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ERROR: {e}")
        if e.stderr:
            print(e.stderr)
        return False
    except FileNotFoundError:
        print(f"  ERROR: Command not found: {cmd[0]}")
        return False


def main():
    print_header("SC Signature Scanner - Build Script")
    
    # Ensure we're in the right directory
    project_dir = Path(__file__).parent
    if not (project_dir / "main.py").exists():
        print("ERROR: main.py not found. Run this script from the project directory.")
        sys.exit(1)
    
    import os
    os.chdir(project_dir)
    print(f"Project: {project_dir}")
    
    # Get version
    try:
        import version_checker
        version = version_checker.CURRENT_VERSION
        print(f"Version: {version}")
    except ImportError:
        version = "unknown"
        print("Warning: Could not determine version")
    
    # ===== Pre-build Checks =====
    print_section("Pre-build Checks")
    
    # Required source files
    required_files = [
        "main.py",
        "scanner.py",
        "overlay.py",
        "splash.py",
        "monitor.py",
        "config.py",
        "theme.py",
        "paths.py",
        "pricing.py",
        "version_checker.py",
        "region_selector.py",
        "regolith_api.py",
        "requirements.txt",
        "SC_Signature_Scanner.spec",
    ]
    
    missing = []
    for filename in required_files:
        filepath = project_dir / filename
        if not filepath.exists():
            missing.append(filename)
    
    if missing:
        print(f"  ERROR: Missing required files:")
        for f in missing:
            print(f"    - {f}")
        sys.exit(1)
    print(f"  ✓ All {len(required_files)} required source files present")
    
    # Required data files
    data_dir = project_dir / "data"
    db_file = data_dir / "combat_analyst_db.json"
    if not db_file.exists():
        print(f"  ERROR: Database not found: {db_file}")
        sys.exit(1)
    print(f"  ✓ Database file present")
    
    # Check for deprecated files (warning only)
    deprecated_files = [
        "hud_calibration.py",
        "identifier_window.py",
        "jxr_converter.py",
        "tobii_tracker.py",
    ]
    
    found_deprecated = []
    for filename in deprecated_files:
        if (project_dir / filename).exists():
            found_deprecated.append(filename)
    
    if found_deprecated:
        print(f"  ⚠ Warning: Deprecated files found (run clean.py first):")
        for f in found_deprecated:
            print(f"    - {f}")
    
    # ===== Clean Previous Builds =====
    print_section("Cleaning Previous Builds")
    
    for folder in ["build", "dist"]:
        path = project_dir / folder
        if path.exists():
            shutil.rmtree(path)
            print(f"  Removed: {folder}/")
    
    # ===== Check PyInstaller =====
    print_section("PyInstaller")
    
    try:
        import PyInstaller
        print(f"  ✓ PyInstaller {PyInstaller.__version__} found")
    except ImportError:
        print("  PyInstaller not found, installing...")
        if not run_command([sys.executable, "-m", "pip", "install", "pyinstaller"], "Installing"):
            print("  ERROR: Failed to install PyInstaller")
            sys.exit(1)
    
    # ===== Build =====
    print_header("Building Executable")
    
    spec_file = project_dir / "SC_Signature_Scanner.spec"
    
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", str(spec_file), "--noconfirm"],
        cwd=project_dir
    )
    
    if result.returncode != 0:
        print_header("BUILD FAILED")
        sys.exit(1)
    
    # ===== Verify Output =====
    print_section("Verifying Build")
    
    dist_dir = project_dir / "dist" / "SC_Signature_Scanner"
    exe_file = dist_dir / "SC_Signature_Scanner.exe"
    # PyInstaller puts data files in _internal/ subdirectory
    internal_dir = dist_dir / "_internal"
    data_dir_dist = internal_dir / "data"
    db_file_dist = data_dir_dist / "combat_analyst_db.json"
    
    errors = []
    
    if not exe_file.exists():
        errors.append("Executable not found")
    else:
        size_mb = exe_file.stat().st_size / (1024 * 1024)
        print(f"  ✓ Executable: {exe_file.name} ({size_mb:.1f} MB)")
    
    if not db_file_dist.exists():
        errors.append("Database file not bundled")
    else:
        print(f"  ✓ Database: data/combat_analyst_db.json")
    
    if errors:
        print("\n  Errors:")
        for e in errors:
            print(f"    ✗ {e}")
        sys.exit(1)
    
    # ===== Summary =====
    print_header("BUILD COMPLETE")
    
    print(f"Version:     v{version}")
    print(f"Output:      {dist_dir}")
    print(f"Executable:  SC_Signature_Scanner.exe")
    print()
    print("Bundled files:")
    print("  - data/combat_analyst_db.json")
    print()
    print("Runtime files (created on first use):")
    print("  - config.json              (user settings + API key)")
    print("  - scan_region.json         (scan region config)")
    print("  - regolith_cache.json      (Regolith.rocks cache)")
    print("  - SignatureScannerBugreport/  (debug output)")
    print()
    print("Distribution:")
    print("  Copy the entire SC_Signature_Scanner folder.")
    print("  Users run SC_Signature_Scanner.exe")
    print()
    
    # Open the dist folder (Windows)
    if sys.platform == "win32":
        import os
        os.startfile(dist_dir)


if __name__ == "__main__":
    main()
