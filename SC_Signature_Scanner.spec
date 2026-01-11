# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for SC Signature Scanner
Build with: pyinstaller SC_Signature_Scanner.spec
"""

import sys
from pathlib import Path

block_cipher = None

# Get the project root
PROJECT_ROOT = Path(SPECPATH)

# Data files to include
datas = [
    # Database file
    (str(PROJECT_ROOT / 'data' / 'combat_analyst_db.json'), 'data'),
    # Include any cached pricing data if it exists
]

# Add scan_region.json if it exists (user config)
scan_region = PROJECT_ROOT / 'scan_region.json'
if scan_region.exists():
    datas.append((str(scan_region), '.'))

# Hidden imports that PyInstaller might miss
hiddenimports = [
    'PIL._tkinter_finder',
    'cv2',
    'scipy.ndimage',
    'numpy',
    'watchdog.observers',
    'watchdog.events',
]

a = Analysis(
    ['main.py'],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'pandas',
        'scipy.spatial',
        'scipy.optimize', 
        'scipy.integrate',
        'scipy.interpolate',
        'scipy.linalg',
        'scipy.signal',
        'scipy.sparse',
        'scipy.stats',
        'IPython',
        'jupyter',
        'notebook',
        'pytest',
        'setuptools',
        'wheel',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SC_Signature_Scanner',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # No console window (GUI app)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='assets/icon.ico',  # Uncomment if you add an icon
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SC_Signature_Scanner',
)
