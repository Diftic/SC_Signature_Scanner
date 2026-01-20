# SC Signature Scanner

[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20A%20Coffee-Support-orange?style=flat&logo=buy-me-a-coffee)](https://buymeacoffee.com/Mallachi)

Real-time signature identification tool for Star Citizen. Monitors your screenshot folder and automatically identifies asteroids, deposits, and salvage targets from in-game signature values.

**Version:** 3.1.8  
**Author:** Mallachi

## Features

### Core Scanning
- **Automatic OCR** — Extracts signature values from screenshots using EasyOCR deep learning
- **Mining Identification** — Identifies asteroids (I/C/S/P/M/Q/E-type), surface deposits, and ground deposits (FPS/ROC)
- **Salvage Detection** — Hull panel count estimation from salvage signatures
- **Configurable Scan Region** — Define exactly where signatures appear on your screen for faster, more accurate detection

### Data & Pricing
- **Live Pricing** — Real-time ore values from UEX Corp API
- **Mineral Composition** — Probable mineral spawns and their values via Regolith.rocks API
- **Multiple Refinery Methods** — 9 refinery yield options (Dinyx, Ferron, Cormack, etc.) for accurate value estimates
- **Automatic Data Caching** — Caches API data locally for offline use and faster startups

### Overlay Display
- **In-Game Overlay Popup** — Non-intrusive results display over the game
- **Customizable Position** — Drag-to-position overlay anywhere on screen
- **Adjustable Scale** — 50% to 200% size scaling
- **Configurable Duration** — 1-30 seconds display time

### Monitoring & Workflow
- **Folder Monitoring** — Automatically detects new screenshots in your SC screenshot folder
- **Test Screenshot** — Manually test OCR on any image file
- **Detection Log** — Timestamped log of all scans and results
- **Screenshot Counter** — Tracks screenshots processed per session

### Quality of Life
- **Automatic Updates** — Checks for new versions on startup with one-click download
- **Debug Mode** — Saves OCR processing images for troubleshooting
- **Custom Debug Folder** — Choose where debug images are saved
- **Test Popup** — Preview overlay appearance with sample data
- **Splash Screen** — Loading progress display during startup

## Screenshots

<img src="images/main_window.png" width="600" alt="Main Scanner Window">

<img src="images/overlay_popup.png" width="400" alt="Overlay Popup">

<img src="images/settings.png" width="600" alt="Settings Tab">

## Requirements

- **Windows 10/11**
- **Star Citizen** in Windowed or Borderless Windowed mode
- **Regolith.rocks API Key** — Free, required for rock composition data

## Quick Start

### For Users (Executable)

1. Download the latest release
2. Extract the `SC_Signature_Scanner` folder
3. Run `SC_Signature_Scanner.exe`
4. Enter your Regolith.rocks API key when prompted
5. Configure your scan region in Settings
6. Start monitoring and take screenshots in-game!

### For Developers (Python)

```bash
# Clone and install
git clone https://github.com/OWNER/SC_Signature_Scanner.git
cd SC_Signature_Scanner
pip install -r requirements.txt

# Run
python main.py
```

**Note:** First run downloads ~115MB of OCR models to `~/.EasyOCR/model/`

## Usage

1. **Configure Scan Region** (first time only)
   - Go to Settings → Define Scan Region
   - Take a screenshot with a signature visible
   - Click and drag to select the signature value area
   - Save the region

2. **Start Monitoring**
   - Set your Star Citizen screenshot folder
   - Click "Start Monitoring"
   - In-game: Press PrintScreen when you see a signature
   - Results appear in an overlay popup

## Signature Reference

### Space Deposits (Asteroids)
Ship mining with Prospector/MOLE. Mixed mineral composition.

| Type | Base Signature |
|------|----------------|
| I-type | 1660 |
| C-type | 1700 |
| S-type | 1720 |
| P-type | 1750 |
| M-type | 1850 |
| Q-type | 1870 |
| E-type | 1900 |

### Surface Deposits
Ship mining with Prospector/MOLE. Mixed mineral composition.

| Type | Base Signature |
|------|----------------|
| Shale | 1730 |
| Felsic | 1770 |
| Obsidian | 1790 |
| Atacamite | 1800 |
| Quartzite | 1820 |
| Gneiss | 1840 |
| Granite | 1920 |
| Igneous | 1950 |

### Ground Deposits
100% single mineral purity per cluster.

| Variant | Base Signature | Method |
|---------|----------------|--------|
| Small | 120 | FPS/Hand mining |
| Large | 620 | ROC/Vehicle mining |

### Salvage
| Type | Signature |
|------|-----------|
| Hull Panel | 2000 each |

## Formulas

```
Mining:  rock_count = total_signature ÷ base_signature
Salvage: panel_count = signature ÷ 2000
```

Example: Signature 5100 = 3× C-type asteroids (1700 × 3)

## Configuration

Settings saved to `config.json`:

| Setting | Description |
|---------|-------------|
| Screenshot folder | Path to Star Citizen screenshots |
| Overlay position | Screen coordinates for popup |
| Overlay duration | Seconds to display (1-30) |
| Overlay scale | Size multiplier (0.5-2.0) |
| Debug mode | Save OCR processing images |
| Refinery yield | For value calculations (default 85%) |

## File Structure

```
SC_Signature_Scanner/
├── SC_Signature_Scanner.exe  # Main executable
├── _internal/                # Runtime dependencies
│   └── data/
│       └── combat_analyst_db.json
│
├── config.json              # User settings (created on first run)
├── scan_region.json         # Scan region config
└── regolith_cache.json      # Cached rock compositions
```

## Troubleshooting

**"No signature detected"**
- Ensure scan region is correctly configured
- Screenshot must capture the signature value clearly
- Try adjusting in-game UI scale

**"OCR not available"**
- First run requires internet to download models (~115MB)
- Check `~/.EasyOCR/model/` exists after download

**Overlay not visible**
- Game must be in Windowed or Borderless Windowed mode
- Check overlay position isn't off-screen

**Wrong identification**
- Multiple deposit types can have similar signatures
- Results sorted by confidence (count-based)
- Lower counts are more likely

**Slow startup**
- Normal — PyTorch/EasyOCR takes 15-20 seconds to load
- Splash screen shows loading progress

## Data Sources

- **Signatures:** Extracted from Star Citizen game files (Data.p4k)
- **Rock Compositions:** [Regolith.rocks](https://regolith.rocks) API
- **Ore Prices:** [UEX Corp](https://uexcorp.space) API

## Credits

- **Developer:** Mallachi
- **Rock Data:** Regolith.rocks team
- **Pricing Data:** UEX Corp
- **Testing:** Regolith.rocks community

## License

MIT License - Free to use, modify, and distribute. See [LICENSE](LICENSE) for details.

Not affiliated with Cloud Imperium Games or Roberts Space Industries.
