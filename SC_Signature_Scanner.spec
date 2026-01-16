# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for SC Signature Scanner
Build with: pyinstaller SC_Signature_Scanner.spec

OCR Engine: EasyOCR (deep learning based)
- Models download on first run (~115MB to ~/.EasyOCR/model/)
- Character definition files bundled with app

Author: Mallachi
"""

import sys
from pathlib import Path

block_cipher = None

# Get the project root
PROJECT_ROOT = Path(SPECPATH)

# Find EasyOCR package location for data files
import importlib.util
easyocr_spec = importlib.util.find_spec('easyocr')
if easyocr_spec and easyocr_spec.origin:
    EASYOCR_PATH = Path(easyocr_spec.origin).parent
else:
    # Fallback - try common locations
    import site
    for site_dir in site.getsitepackages():
        candidate = Path(site_dir) / 'easyocr'
        if candidate.exists():
            EASYOCR_PATH = candidate
            break
    else:
        EASYOCR_PATH = None

# Data files to include
datas = [
    # Database file
    (str(PROJECT_ROOT / 'data' / 'combat_analyst_db.json'), 'data'),
]

# Add EasyOCR character files if found
if EASYOCR_PATH:
    character_dir = EASYOCR_PATH / 'character'
    dict_dir = EASYOCR_PATH / 'dict'
    
    if character_dir.exists():
        # Include all character definition files
        datas.append((str(character_dir), 'easyocr/character'))
    
    if dict_dir.exists():
        # Include dictionary files (word lists for each language)
        datas.append((str(dict_dir), 'easyocr/dict'))

# Note: scan_region.json and config.json are user config files
# created at runtime - do NOT bundle them

# Hidden imports that PyInstaller might miss
hiddenimports = [
    # Tkinter
    'PIL._tkinter_finder',
    
    # Image processing
    'cv2',
    'numpy',
    
    # EasyOCR and PyTorch
    'easyocr',
    'easyocr.easyocr',
    'easyocr.craft',
    'easyocr.craft_utils',
    'easyocr.imgproc',
    'easyocr.recognition',
    'easyocr.utils',
    'easyocr.model.vgg_model',
    'easyocr.model.model',
    
    # PyTorch core
    'torch',
    'torch.nn',
    'torch.nn.functional',
    'torch.utils',
    'torch.utils.data',
    'torchvision',
    'torchvision.models',
    'torchvision.transforms',
    'torchvision.transforms.functional',
    
    # File monitoring
    'watchdog.observers',
    'watchdog.events',
    
    # Networking
    'requests',
    
    # SciPy (sometimes needed by torch/numpy)
    'scipy.ndimage',
]

# Collect all torch and torchvision submodules
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hiddenimports += collect_submodules('torch')
hiddenimports += collect_submodules('torchvision')
hiddenimports += collect_submodules('easyocr')

# Collect torch data files (e.g., CUDA libs if present)
torch_datas = collect_data_files('torch')
torchvision_datas = collect_data_files('torchvision')
datas += torch_datas
datas += torchvision_datas

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
        # Note: scipy must NOT be excluded - EasyOCR requires scipy.ndimage
        # and partial scipy bundling breaks the C extensions
        # Exclude dev tools
        'IPython',
        'jupyter',
        'notebook',
        'pytest',
        'setuptools',
        'wheel',
        # Exclude matplotlib (not needed)
        'matplotlib',
        'pandas',
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
