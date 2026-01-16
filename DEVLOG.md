# SC Signature Scanner - Development Log

**Project:** SC Signature Scanner  
**Location:** `C:\Users\larse\PycharmProjects\AREA52\SC_Signature_Scanner\`  
**Developer:** Mallachi  
**Current Version:** v3.1.2  
**Development Period:** January 8-14, 2026

---

## Project Overview

The SC Signature Scanner is a real-time target identification tool for Star Citizen. It monitors screenshots and uses OCR to detect signature values from the in-game HUD, then matches them against a database to identify asteroids, deposits, ships, and salvage targets.

---

## Development Rules

### 1. Devlog as Source of Truth

The development log shall serve as the authoritative project state document. It must be complete enough that any AI can read it and immediately understand: (a) current project status, (b) what has been implemented, (c) what remains to be done, (d) why key decisions were made.

### 2. Session Start Protocol

At the start of each development session, Claude shall review previous chat history to identify and document any unlogged events, decisions, or changes before proceeding with new work.

### 3. Session End Protocol

At session end, if substantial work was completed, the devlog shall be updated with: work completed, problems encountered and solutions, any new decisions or deferrals, and updated status of pending items.

### 4. Decision Documentation

Technical decisions shall be recorded with rationale. "We chose X" is insufficient - "We chose X because Y, and rejected Z because W" enables future AI to understand context and avoid revisiting settled questions.

### 5. Current State Clarity

The devlog shall always contain a clear "Current Status" or "Next Steps" section so any AI knows exactly where to resume work.

---

### Core Features
- Screenshot folder monitoring with automatic signature detection
- OCR-based signature value extraction from game HUD
- Database matching for asteroids, surface deposits, ground deposits, salvage
- Estimated value calculation using live UEX pricing data
- Mineral composition display for mining targets
- Tobii Eye Tracker 5 integration (optional, deferred)
- Manual scan region configuration (fallback)
- Regolith.rocks API integration for rock composition data

---

## Development Timeline

### Phase 1: Project Inception (January 8, 2026)

**Initial Concept:**
The project originated from an idea to enhance Wingman AI (a Star Citizen AI assistant) with Tobii Eye Tracker integration. The concept was to allow players to look at something in-game and ask "What is that?" with the AI analyzing the focused area.

**Key Decisions:**
- Standalone tool rather than Wingman AI skill (simpler distribution)
- Screenshot-based capture (using SC's native screenshot function)
- Folder monitoring approach (watchdog library)
- Overlay popup for results display

**Project Structure Created:**
```
SC_Signature_Scanner/
├── main.py           # Main application with tkinter UI
├── scanner.py        # OCR and signature matching
├── overlay.py        # Popup overlay display
├── monitor.py        # Screenshot folder watcher
├── config.py         # Configuration management
├── clean.py          # Cache cleanup utility
├── requirements.txt  # Python dependencies
└── data/
    └── combat_analyst_db.json  # Signature database
```

---

### Phase 2: Database Extraction (January 8-9, 2026)

**Data.p4k Mining:**
Used `scdatatools` and `unp4k` to extract signature data directly from Star Citizen's game files. This provided:
- Ship cross-section dimensions (CS values)
- Asteroid type signatures
- Deposit signatures
- Mining rock compositions

**Key Discovery - Signature Formula:**
```
Total Signature = Count × Base Signature
```
Example: Signature 3400 = 2× C-type asteroids (base 1700 each)

**Database Version 4.0 Created:**
| Category | Types | Signature Range |
|----------|-------|-----------------|
| Space Deposits (Asteroids) | I, C, S, P, M, Q, E | 1660-1900 |
| Surface Deposits | Shale, Felsic, Obsidian, Atacamite, Quartzite, Gneiss, Granite, Igneous | 1730-1950 |
| Ground Deposits (Small) | FPS/Hand mining | 120 base |
| Ground Deposits (Large) | ROC/Vehicle mining | 620 base |
| Salvage | Per panel | 2000 base |

---

### Phase 3: Detection Algorithm Evolution (January 9-10, 2026)

**Attempt 1: Naive OCR**
- Simple text search for "SIG:" label
- Failed: Label not always present, position varies

**Attempt 2: Gradient Bar Detection**
- Find two vertical gradient bars (always present when scanning)
- Calculate bar angle → rotate image to vertical
- Signature position = midpoint between bar tops
- Problem: Angle calculation returned -178.8° (picking up wrong elements)

**Attempt 3: Icon Triangle Detection**
- Find cone icon (left) and signal icon (right)
- Calculate equilateral triangle
- OCR at apex
- Problem: Too many similar-colored elements causing false matches

**Attempt 4: HUD Circle Detection**
- Find the targeting reticle using color saturation + Hough circles
- Calculate signature position relative to circle center
- Problem: Complex, unreliable across different HUD palettes

**Final Solution: Fixed Region + Manual Calibration**
- User defines scan region once via GUI tool
- OCR that fixed region on every screenshot
- Simple, reliable, works across all HUD styles

---

### Phase 4: Pricing Integration (January 9, 2026)

**UEX Corp API Integration:**
- Fetches live ore prices from `api.uexcorp.uk`
- 30-minute cache TTL
- Calculates estimated rock values using:
  - Rock composition data (from Regolith.rocks)
  - Current ore prices (from UEX)
  - Refinery yield setting (user configurable)

**Value Calculation Formula:**
```
mineral_mass = deposit_mass × mineral_percentage
mineral_volume = mineral_mass / density
value = mineral_volume × price × refinery_yield
```

**Mineral Composition Display:**
Each rock type now shows probable mineral spawns with:
- Spawn probability (%)
- Median percentage when present
- Individual mineral value
- Price per SCU

---

### Phase 5: Tobii Integration (January 10-11, 2026)

**Research Phase:**
- Tobii Eye Tracker 5 (consumer) has no official SDK
- Tobii 5L (commercial) requires €1495/year license
- Solution: PyEyetracker project (Apache-2.0 license)

**Implementation:**
- GazeServer.exe provides WebSocket interface on localhost:8765
- Returns gaze coordinates in normalized (0-1) format
- SC Signature Scanner connects and converts to pixel coordinates

**Tobii Tab Features:**
- Connection status indicator
- Download button for GazeServer.exe
- Test connection functionality
- Automatic fallback to fixed region if Tobii unavailable

**Decision (January 12):**
Tobii support removed from v1.1.0 release - too complex for initial tester distribution. Fixed region approach is sufficient. Tobii can be re-added later.

---

### Phase 6: UI Development (January 10-11, 2026)

**Theme: Regolith.rocks Inspired**
- Dark background (#1a1a2e)
- Orange accent (#f4a259)
- Cyan success (#4ecca3)
- Professional mining tool aesthetic

**Main Window Tabs:**
1. **Scanner** - Start/stop monitoring, activity log, results display
2. **Settings** - Screenshot folder, overlay options, debug mode, pricing
3. **Tobii Tracker** - Connection status, region configuration
4. **About** - Version info, credits

**Region Selector Tool:**
- Opens fullscreen with screenshot
- Click and drag to define scan region
- Escape to cancel
- Save/Clear/Cancel buttons

---

### Phase 7: Regolith.rocks API Integration (January 11-12, 2026)

**Partnership:**
Collaboration with Regolith.rocks team for:
- Rock composition survey data
- Mining location bonuses
- Authoritative mineral spawn rates

**API Features:**
- API key authentication (required)
- Profile validation on startup
- Rock composition queries per system
- Local cache with manual refresh

**Startup Flow:**
1. Check for saved API key
2. Validate against Regolith.rocks
3. If invalid → prompt for new key
4. If user cancels → exit app
5. Cache composition data locally

---

### Phase 8: OCR Improvements (January 12, 2026)

**Problem Identified:**
Original OCR pipeline was over-processing images:
1. Grayscale conversion (lost orange color info)
2. Fixed threshold at 80 (caught background noise)
3. Binary output (destroyed anti-aliasing)
4. 4x upscale on binary (blocky artifacts)

Result: "1,850" read as "1950"

**Solution: Hybrid OCR Mode**

**Mode 1: Raw (Minimal Processing)**
- Just grayscale conversion
- Preserves anti-aliasing
- Better for clean HUD text

**Mode 2: Adaptive (OpenCV)**
- Adaptive thresholding with Gaussian method
- Handles uneven backgrounds
- Better for cluttered scenes

**Mode 3: Hybrid (Default)**
- Try raw first
- If no signatures found, try adaptive
- Best of both worlds

**Implementation:**
```python
self.ocr_mode = 'hybrid'  # Options: 'raw', 'adaptive', 'hybrid'
```

---

### Phase 9: Build & Distribution (January 11-12, 2026)

**PyInstaller Configuration:**
- Single-folder distribution
- Bundled database and assets
- Hidden imports handled (cv2, scipy, etc.)

**Build Output:**
```
dist/SC_Signature_Scanner/
├── SC_Signature_Scanner.exe
├── data/
│   └── combat_analyst_db.json
└── [runtime dependencies]
```

**Runtime Files (created on first use):**
- `config.json` - User settings + API key
- `scan_region.json` - Defined scan region
- `SignatureScannerBugreport/` - Debug output folder

**Tester Distribution:**
- Debug mode with timestamp-prefixed files
- Configurable debug output folder
- Clean.py utility for resetting state

---

### Phase 10: OCR Engine Migration (January 14, 2026)

**Problem with Tesseract:**
The pytesseract/Tesseract OCR dependency was causing distribution headaches:
- External binary required (tesseract.exe)
- PATH configuration issues on user machines
- Inconsistent versions across installations
- Complex PyInstaller bundling
- Users reporting "tesseract not found" errors

**Solution: EasyOCR**
Migrated to EasyOCR, a deep learning-based OCR engine:
- Pure Python package (pip install)
- No external binaries
- Models download automatically on first use (~115MB)
- Runs entirely offline after initial download
- Better accuracy on styled game text

**Implementation Details:**

| Component | Change |
|-----------|--------|
| `scanner.py` | Complete rewrite of OCR pipeline |
| `requirements.txt` | Added easyocr, torch, torchvision; removed pytesseract |
| `SC_Signature_Scanner.spec` | Added EasyOCR hidden imports + data files |

**Key Design Decisions:**

1. **Lazy Initialization**: OCR reader created on first scan, not at startup
   - Faster app launch
   - Model download happens when actually needed
   - UI can show progress during download

2. **CPU-Only Mode**: `gpu=False` by default
   - Works on all machines
   - Avoids CUDA dependency complexity
   - GPU auto-detected if available

3. **Digit Allowlist**: `allowlist='0123456789,.'`
   - Maximum accuracy for signature values
   - Prevents letter/digit confusion (O vs 0, l vs 1)

4. **Simplified Preprocessing**: 
   - EasyOCR handles most preprocessing internally
   - Only upscale small regions for better detection
   - Removed complex threshold/binary conversion pipeline

**Model Download Flow:**
```
First OCR use:
1. Check ~/.EasyOCR/model/ for cached models
2. If missing, download from EasyOCR servers (~115MB)
3. Load models into memory
4. All subsequent runs use local cache
```

**Files Modified:**
- `scanner.py` - New EasyOCR-based implementation
- `requirements.txt` - Updated dependencies
- `SC_Signature_Scanner.spec` - PyInstaller config for EasyOCR

**Removed:**
- Hybrid OCR mode (raw/adaptive) - no longer needed
- Complex image preprocessing pipeline
- Tesseract binary dependency

---

## Version History

### v3.1.2 (January 16, 2026)
*Scipy bundling fix for PyInstaller*

- **FIX:** Removed scipy excludes from PyInstaller spec - partial scipy exclusion breaks C extension imports
- **ROOT CAUSE:** EasyOCR requires scipy.ndimage, but excluding other scipy modules broke the shared binary loader
- **NOTE:** Build size will increase ~50-100MB but scipy now works correctly in frozen builds

### v3.1.1 (January 16, 2026)
*EasyOCR type hint fix*

- **FIX:** Changed type hints from `easyocr.Reader` to `Any` in scanner.py
- **ROOT CAUSE:** Type hints evaluate at class definition time; if import fails, the type hint crashes

### v3.0.0 (January 14, 2026)
*Regolith API integration complete - Ready for testing*

- **FIX:** pricing.py now reads rock compositions from Regolith cache (was looking for separate rock_types.json)
- **CHANGE:** Single source of truth - regolith_cache.json contains all rock composition data
- **REMOVE:** Dependency on static data/rock_types.json file
- **FIX:** Build script verification updated for PyInstaller _internal/ directory structure
- **READY:** Build complete, ready for testing and version control setup

### v1.0.0 (January 11, 2026)
- Initial tester release
- Fixed region scanning
- Basic OCR with threshold
- Pricing integration
- Regolith.rocks API

### v2.1.2 (January 14, 2026)
*Display name improvements*

- **FIX:** Asteroid display names now show full names ("C" → "C-type Asteroid")
- **FIX:** Added count suffix for multiples ("C-type Asteroid (x4)" for 4 asteroids)
- **NOTE:** Composition table requires Regolith cache (rock_types.json) - if missing, only basic info shown

### v2.1.1 (January 14, 2026)
*Bug fixes for EasyOCR integration*

- **FIX:** Pillow 10.0.0+ compatibility - added ANTIALIAS shim (EasyOCR uses deprecated constant)
- **FIX:** Overlay category mismatch - scanner returns `space_deposit`/`surface_deposit`/`ground_deposit`, overlay was checking for old names (`asteroid`/`deposit`/`fps_mining`)
- **FIX:** Ground deposit display now shows possible minerals list instead of "Unknown"
- **IMPROVE:** clean.py updated with `--ocr` flag to optionally remove EasyOCR models (~115MB)

### v2.1.0 (January 14, 2026) - Pre-release
*Major OCR engine migration*

- **BREAKING:** Replaced pytesseract/Tesseract with EasyOCR (deep learning OCR)
- **NEW:** Automatic model download on first use (~115MB, then offline)
- **NEW:** Lazy OCR initialization (faster startup)
- **NEW:** UI callbacks for model download progress
- **REMOVE:** Hybrid OCR mode (no longer needed with EasyOCR)
- **REMOVE:** Tesseract binary dependency
- **IMPROVE:** Simplified image preprocessing pipeline
- **IMPROVE:** Digit allowlist for maximum signature accuracy

### v2.0.0 (January 14, 2026) - Pre-release
*Designated for tester review before public release*

- **CHANGE:** Startup order - API key validation now happens first, before loading signature database and pricing
- **ADD:** "Thanks To" section in About tab acknowledging testers
- **FIX:** About tab left panel background color (was light gray, now matches dark theme)
- **IMPROVE:** clean.py - now removes deprecated files automatically
- **IMPROVE:** build.py - added pre-build verification checks
- **DOCS:** Added Development Rules to DEVLOG for AI continuity
- **DOCS:** Added Current Status section to DEVLOG

### v1.1.0 (January 12, 2026)
- **NEW:** Hybrid OCR mode (raw + adaptive)
- **FIX:** OCR misreading digits (1850 → 1950)
- **FIX:** Region selector buttons accessibility in fullscreen
- **ADD:** OpenCV dependency for adaptive thresholding
- **REMOVE:** Tobii support (deferred to future release)
- **IMPROVE:** Debug output with per-mode images

---

## Technical Decisions Log

| Decision | Rationale |
|----------|-----------|
| Fixed region over auto-detection | Reliability across HUD variants |
| EasyOCR over Tesseract | No external binary, pure Python, better accuracy on game text |
| Regolith API mandatory | Ensures data quality, supports partner |
| Screenshot-based over live capture | Works with any display mode |
| Tkinter over Qt | Lighter weight, sufficient for needs |
| Local database over API-only | Offline capability, faster lookups |
| Lazy OCR init over eager | Faster startup, download only when needed |
| CPU-only OCR default | Universal compatibility, avoids CUDA complexity |
| Comma removed from OCR allowlist | Was causing misreads like "7,480" → "7,4480"; plain digit parsing is more reliable |
| Layer 3 signature validation | OCR reads commas/periods as digits; validation + correction against known bases fixes this |
| Morphological punctuation filtering | Commas/periods are ~5-20px vs digits 100+px; remove small connected components before OCR |
| Prefer lowest count in correction | 7400 = 4× M-type is more realistic than 7440 = 62× small ground deposit |
| Startup splash screen | Torch/EasyOCR takes 15-20s to load; users need visual feedback that app is working |
| Use `Any` for easyocr type hints | Type hints evaluate at class definition; if import fails, `easyocr.Reader` crashes |
| Full scipy bundling over partial | Excluding scipy submodules breaks C extension loader; ~50-100MB size increase is acceptable for reliability |

---

## Known Issues / Future Work

### Deferred to Future Releases
- [ ] Tobii Eye Tracker integration
- [ ] Ship signature matching (currently mining-focused)
- [ ] Auto-detection as fallback to fixed region
- [ ] Multi-monitor support testing
- [ ] Localization for non-English clients

### Database Maintenance
- Ground deposit signatures (120, 620) need periodic verification
- New deposit types may be added with SC patches
- Ship signatures need complete extraction

---

## External Dependencies

| Dependency | Purpose | License |
|------------|---------|---------|
| easyocr | Deep learning OCR engine | Apache 2.0 |
| torch | PyTorch (EasyOCR backend) | BSD |
| torchvision | PyTorch vision utilities | BSD |
| Pillow | Image processing | HPND |
| opencv-python | Image preprocessing | Apache 2.0 |
| watchdog | Folder monitoring | Apache 2.0 |
| requests | API calls | Apache 2.0 |
| numpy | Array operations | BSD |

**Note:** First run downloads ~115MB of EasyOCR model files to `~/.EasyOCR/model/`. Subsequent runs are fully offline.

---

## Current Status / Next Steps

**Status:** v3.1.2 - Scipy bundling fix

**Immediate priorities:**
1. ~~Fix About tab background color issue~~ ✓ (completed Jan 14)
2. ~~Update clean.py and build.py~~ ✓ (completed Jan 14)
3. ~~Change startup order (API validation first)~~ ✓ (completed Jan 14)
4. ~~Add "Thanks To" section for testers~~ ✓ (completed Jan 14)
5. ~~Migrate from pytesseract to EasyOCR~~ ✓ (completed Jan 14)
6. ~~Fix Pillow ANTIALIAS compatibility~~ ✓ (completed Jan 14)
7. ~~Fix overlay category mismatch~~ ✓ (completed Jan 14)
8. ~~Fix asteroid display names~~ ✓ (completed Jan 14)
9. ~~Connect pricing.py to Regolith cache~~ ✓ (completed Jan 14)
10. ~~Fix build script for PyInstaller _internal/ structure~~ ✓ (completed Jan 14)
11. ~~Version control setup (GitHub)~~ ✓ (completed Jan 14)
12. ~~Fix OCR comma/period misreading~~ ✓ (completed Jan 15)
13. ~~Add startup splash screen~~ ✓ (completed Jan 15)
14. ~~Fix easyocr import NameError crash~~ ✓ (completed Jan 16)
15. Testing on fresh install

**Blocking issues:** 
- None

**Ready for:** Fresh install testing, distribution to testers

**Session Log - January 16, 2026 (Session 9):**
- **BUG REPORT:** Tester error: `scipy install seems to be broken (extension modules cannot be imported)`
- **ROOT CAUSE:** PyInstaller spec excluded scipy modules to reduce build size, but partial exclusion breaks scipy's shared C extension loader
- **FIX:** Removed scipy excludes from SC_Signature_Scanner.spec - full scipy now bundled
- **TRADE-OFF:** Build size increases ~50-100MB, but scipy works correctly
- Bumped version to v3.1.2

**Session Log - January 16, 2026 (Session 8):**
- **BUG REPORT:** Tester crash on startup: `NameError: name 'easyocr' is not defined`
- **ROOT CAUSE:** Type hints `Optional[easyocr.Reader]` evaluated at class definition time
- When `import easyocr` fails, the name `easyocr` doesn't exist, so the type hint crashes
- **FIX:** Changed type hints from `easyocr.Reader` to `Any` in scanner.py
- Affected: `self._ocr_reader` attribute and `_get_ocr_reader()` return type
- Now app loads even if easyocr import fails (shows proper error instead of crash)
- Bumped version to v3.1.1

**Session Log - January 15, 2026 (Session 7):**
- **BUG:** Overlay crash `TclError: bad screen distance "5 0"` when showing ground deposit popup
- **ROOT CAUSE:** Tkinter Label constructor doesn't accept tuple `pady=(5, 0)` — only `.pack()` does
- **FIX:** Moved tuple pady from Label constructor to `.pack(pady=(5, 0))` in overlay.py
- **BUG:** Signature correction picked wrong value: `74400` → `7440` instead of `7400`
- **ROOT CAUSE:** `max(candidates)` picked larger value; 7440 = 62× small ground (120) vs 7400 = 4× M-type (1850)
- **FIX:** Changed `_try_correct_signature()` to prefer lowest count: `min(candidates, key=min_count)`
- **IMPROVEMENT:** Implemented morphological filtering to remove commas/periods BEFORE OCR
- **RATIONALE:** Commas are ~5-20 pixels, digits are 100+ pixels — size-based filtering is reliable
- **NEW:** Added `_remove_small_components()` method using OpenCV connected components
- Removes components < 50 pixels, fills with background color
- Debug mode saves `04a_removed_components.png` showing removed pixels in red
- **BUG:** 20-second startup with no feedback — users think app is frozen
- **FIX:** Added splash.py with animated loading screen shown immediately
- Status messages: "Loading core modules...", "Loading OCR engine...", "Loading UI components...", "Loading pricing data..."
- Splash closes before main window appears (only one Tk root allowed)
- **TESTED:** Comma filtering works — `7,400` now correctly read as `7400`
- Bumped version to v3.1.0

**Session Log - January 14, 2026 (Session 6):**
- Investigated OCR failure: `7,480` misread as `7,4480` → parsed as `[7448, 4480]` → no match
- Root cause: Comma in allowlist causing EasyOCR to interpolate extra digits around comma position
- **FIX:** Removed comma from OCR allowlist (`'0123456789,.'` → `'0123456789.'`)
- Pattern 2 in `_extract_signatures` handles plain digit sequences, so comma removal is safe
- Tested with tighter scan region: OCR read `1850` with 0.89 confidence ✓
- **BUG:** Threading crash when showing overlay - watchdog callback runs in background thread, Tkinter requires main thread
- **FIX:** Changed `overlay.show()` to use `root.after(0, lambda: self._show_overlay(...))` for thread-safe GUI update
- Added `_show_overlay()` helper method to main.py
- **BUG:** `6.000` parsed but returned empty (period pattern worked, but value not matched)
- **FIX:** Added Pattern 2 for period-separated numbers (`\d{1,3}\.\d{3}`)
- **BUG:** `7,400` read as `74400` (comma read as digit `4` when not in allowlist)
- **ROOT CAUSE:** Both comma and period can be read as digits by OCR - no allowlist config solves this
- **FIX:** Implemented Layer 3 signature validation:
  - Added `KNOWN_BASE_SIGNATURES` constant with all valid base values
  - Added `_is_exact_multiple()` to check if value divides cleanly by any known base
  - Added `_try_correct_signature()` to fix phantom digit insertion
  - Updated `_extract_signatures()` to validate and auto-correct signatures
- Example: `74400` → not valid → try removing digits → `7400` ÷ 1850 = 4 ✓ → corrected to 7400

**Session Log - January 14, 2026 (Session 5):**
- Identified disconnect: regolith_api.py saves to regolith_cache.json, pricing.py was loading from data/rock_types.json
- Fixed pricing.py to import regolith_api and read rock_compositions from cache
- Removed rock_types_file reference from PricingManager
- Fixed build.py verification path (PyInstaller now uses _internal/ subdirectory)
- Bumped version to v3.0.0
- Build successful, ready for testing
- Tested EasyOCR on full scan results panel (standalone test) - works but accuracy limited by image quality; signature scanner's focused region approach is better suited
- **GIT:** Pushed to GitHub - encountered 100MB file limit on dist zip (221MB)
- **FIX:** Rewrote git history to remove large files from commits (`git filter-branch`)
- **FIX:** Updated .gitignore to exclude build/, dist/, *.zip
- Successfully pushed v3.0.0 to GitHub

**Session Log - January 14, 2026 (Session 4):**
- Added ROCK_DISPLAY_NAMES mapping for short asteroid codes
- Scanner now shows "C-type Asteroid" instead of just "C"
- Added count suffix for multiples: "C-type Asteroid (x4)"
- Identified missing rock_types.json as cause of empty composition table
- Bumped version to v2.1.2

**Session Log - January 14, 2026 (Session 3):**
- Fixed Pillow 10.0.0+ compatibility (ANTIALIAS constant removed, added shim)
- Fixed overlay category mismatch (scanner uses space_deposit/surface_deposit/ground_deposit)
- Fixed ground deposit mineral display (shows possible_minerals list)
- Updated clean.py with --ocr flag and --help
- Bumped version to v2.1.1

**Session Log - January 14, 2026 (Session 2):**
- **MAJOR:** Migrated OCR engine from pytesseract to EasyOCR
- Rewrote scanner.py with EasyOCR implementation
- Updated requirements.txt (easyocr, torch, torchvision)
- Updated SC_Signature_Scanner.spec with EasyOCR hidden imports and data files
- Removed hybrid OCR mode (raw/adaptive) - no longer needed
- Added lazy OCR initialization with UI callback hooks
- Added digit allowlist for maximum signature accuracy
- Bumped version to v2.1.0 (Pre-release)

**Session Log - January 14, 2026 (Session 1):**
- Fixed About tab background color (missing bg parameter)
- Added Development Rules section to DEVLOG
- Added Current Status section to DEVLOG
- Updated clean.py: now removes deprecated files (hud_calibration.py, identifier_window.py, tobii_tracker.py)
- Updated build.py: added pre-build checks, better formatting, deprecated file warnings
- Changed startup order: API key validation now happens before signature database and pricing loads
- Added "Thanks To" section in About tab
- Bumped version to v2.0.0 (Pre-release)
- Designated v2.0.0 for tester review

---

## Credits

- **Developer:** Mallachi
- **Data Sources:** 
  - Star Citizen game files (Data.p4k)
  - UEX Corp API (pricing)
  - Regolith.rocks (rock compositions)
- **Inspiration:** Wingman AI project
- **Testing:** Regolith.rocks community testers

---

## Current File Reference

*Updated: January 15, 2026*

```
SC_Signature_Scanner/
├── main.py              # Main application, tkinter UI, startup flow
├── splash.py            # Startup splash screen with loading status
├── scanner.py           # EasyOCR engine, signature matching, component filtering
├── overlay.py           # Results popup display, position adjuster
├── monitor.py           # Screenshot folder watcher (watchdog)
├── config.py            # Configuration persistence (JSON)
├── paths.py             # Path utilities for frozen exe support
├── pricing.py           # UEX API integration, value calculations
├── theme.py             # RegolithTheme, UI colors/fonts
├── region_selector.py   # Scan region definition tool
├── regolith_api.py      # Regolith.rocks API client
├── version_checker.py   # GitHub release checker
├── clean.py             # Cache/pycache cleanup utility
├── build.py             # PyInstaller build script
├── requirements.txt     # Python dependencies
├── run_scanner.bat      # Windows launch script
├── SC_Signature_Scanner.spec  # PyInstaller spec file
├── README.md            # User documentation
├── TODO.md              # Signature database reference
├── DEVLOG.md            # This file
├── data/
│   ├── combat_analyst_db.json  # Signature database
│   └── uex_prices.json         # UEX cache (runtime)
├── assets/              # UI assets (if any)
├── build/               # PyInstaller build output
├── dist/                # Distribution packages
└── screenshots/         # Test screenshots
```

**Runtime files (created on first use):**
- `config.json` — User settings, API key
- `scan_region.json` — Defined scan region coordinates
- `regolith_cache.json` — Regolith.rocks rock composition data (in user data folder)
- `SignatureScannerBugreport/` — Debug output folder (configurable)

---

*Document generated: January 12, 2026*  
*Last updated: January 16, 2026 - v3.1.2 scipy bundling fix*
