# SC Signature Scanner - Status

## Application Version: 3.0.0
## Database Version: 4.5 (for Star Citizen 4.5)
## OCR Engine: EasyOCR (deep learning)

## Mining Categories

### Space Deposits (Asteroids) ✓
Ship mining only (Prospector, MOLE). Mixed mineral composition.
| Type | Signature |
|------|-----------|
| I-type | 1660 |
| C-type | 1700 |
| S-type | 1720 |
| P-type | 1750 |
| M-type | 1850 |
| Q-type | 1870 |
| E-type | 1900 |

### Surface Deposits ✓
Ship mining only (Prospector, MOLE). Mixed mineral composition.
| Type | Signature |
|------|-----------|
| Shale | 1730 |
| Felsic | 1770 |
| Obsidian | 1790 |
| Atacamite | 1800 |
| Quartzite | 1820 |
| Gneiss | 1840 |
| Granite | 1920 |
| Igneous | 1950 |

### Ground Deposits ✓
ROC or FPS mining. 100% single mineral per cluster.

| Variant | Base Signature | Primary Method |
|---------|----------------|----------------|
| Small | 120 | FPS/Hand mining |
| Large | 620 | ROC/Vehicle mining |

**Minerals:** Hadanite, Dolivine, Aphorite, Beradom, Glacosite, Feynmaline, Jaclium

**Cluster Rules:**
- Each cluster spawns only ONE mineral type at 100% purity
- A mineral spawns as either small OR large deposits, never both in same cluster
- Small deposits can be vehicle-mined with skill
- Large deposits can be FPS-mined collaboratively

### Subsurface Deposits
- Status: NOT IN GAME
- Expected: Late 2026-2027
- First ship: Consolidated Outland Pioneer

### Salvage ✓
- Signature per panel: 2000

---

## Completed ✓
- [x] Database taxonomy finalized (v4.2)
- [x] All signature values verified from 2025 mining survey
- [x] Scanner updated for new ground deposit structure
- [x] PyInstaller build system configured
- [x] Path utilities for frozen exe
- [x] Test code removed
- [x] EasyOCR migration (replaced Tesseract)
- [x] Pillow 10.0.0+ compatibility (ANTIALIAS shim)
- [x] Overlay category matching fixed
- [x] Display names for asteroid types (C → "C-type Asteroid")
- [x] Regolith API integration (rock compositions from cache)
- [x] Pricing integration reads from Regolith cache (single source of truth)
- [x] Build script updated for PyInstaller _internal/ directory structure

## In Progress
- [ ] Testing on fresh install
- [ ] Version control setup (GitHub)

## Known Issues
- None currently identified

## Future Work
- [ ] Full signature review after next major mining patch
- [ ] GPU acceleration option for OCR (currently CPU-only)
