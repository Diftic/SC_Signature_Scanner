# SC Signature Scanner

Real-time signature identification tool for Star Citizen. Monitors your screenshot folder and identifies ships, asteroids, and salvage targets from in-game signature readings.

## ⚠️ Requirements

- **Display Mode**: Windowed or Borderless Windowed (exclusive fullscreen not supported)
- **Python**: 3.10+
- **Tesseract OCR**: Must be installed separately

## Installation

### 1. Install Tesseract OCR

**Windows:**
Download from: https://github.com/UB-Mannheim/tesseract/wiki

After installation, add to PATH or set in environment:
```
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Run

```bash
python main.py
```

## Usage

1. Set Star Citizen to **Windowed** or **Borderless Windowed** mode
2. Launch SC Signature Scanner
3. Select your Star Citizen screenshot folder
4. Click **Start Monitoring**
5. In-game: Press **PrintScreen** when you see a signature value
6. Overlay popup shows identification results

## How It Works

1. **Screenshot Detection**: Watches your screenshot folder for new images
2. **OCR Processing**: Extracts signature values from screenshots
3. **Database Matching**: Compares against known signatures
4. **Overlay Display**: Shows matches ranked by likelihood

## Signature Types

| Type | Signature Range | Notes |
|------|----------------|-------|
| **Ships** | Varies by size | Cross-section in meters |
| **Asteroids** | 1660-1900 | Per rock, additive |
| **Deposits** | 1730-1950 | Surface mining |
| **FPS Gems** | 1920 | Hand mining |
| **Ground Vehicle** | 620 | ROC mining |
| **Salvage** | 2000/panel | Additive per panel |

## Formulas

- **Mining**: `rock_count = total_signature ÷ base_signature`
- **Salvage**: `panel_count = signature ÷ 2000`

## Configuration

Settings are saved to `config.json`:

- `screenshot_folder`: Path to SC screenshots
- `popup_position`: top-left, top-right, bottom-left, bottom-right, center
- `popup_duration`: Seconds to display overlay (1-30)
- `max_results`: Maximum matches to show (1-10)

## Database

Ship and mining signatures extracted from Star Citizen game files (Data.p4k).

To update after a patch, use the SC Signature Extractor tool.

## Files

```
SC_Signature_Scanner/
├── main.py           # Main application
├── scanner.py        # OCR and signature matching
├── overlay.py        # Popup overlay display
├── monitor.py        # Screenshot folder watcher
├── config.py         # Configuration management
├── clean.py          # Cache cleanup utility
├── requirements.txt  # Python dependencies
└── data/
    └── combat_analyst_db.json  # Signature database
```

## Troubleshooting

**No signature detected:**
- Ensure screenshot captures the signature value clearly
- Check OCR region settings
- Try adjusting in-game UI scale

**Overlay not visible:**
- Confirm game is in Windowed/Borderless Windowed mode
- Check popup position setting

**Wrong matches:**
- Signatures can match multiple types
- Results sorted by confidence
- Mining/salvage signatures are additive

## License

For personal use with Star Citizen.
