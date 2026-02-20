# AFK Journey Guild Scraper

Python tool that automates navigation of the AFK Journey PC native client
(1920x1080 fullscreen) to scrape guild member ranking statistics and append
data to per-player tabs in a Google Sheet.

Screen capture + OCR only — no game API, no memory reading, no browser
automation.

## Requirements

- Python 3.11+
- AFK Journey PC client running at 1920x1080 fullscreen
- Google Cloud service account with Sheets API access

## Setup

### 1. Clone and install dependencies

```bash
git clone https://github.com/twoobles/afkj-data-extractor.git
cd afkj-data-extractor
pip install -r requirements.txt
```

### PaddlePaddle install note

PaddlePaddle ships platform-specific wheels that are not always resolvable via
plain `pip install`. The `requirements.txt` pins the CPU-only wheel
(`paddlepaddle==2.6.1`). If installation fails on your platform, consult the
official install guide for the correct `--find-links` URL:

https://www.paddlepaddle.org.cn/install/quick

For example, on some Linux distributions you may need:

```bash
pip install paddlepaddle==2.6.1 -f https://www.paddlepaddle.org.cn/whl/linux/mkl/avx/stable.html
```

### 2. Google Sheets service account

1. Create a Google Cloud project and enable the Google Sheets API.
2. Create a service account and download the JSON key file.
3. Place the key file in the project root as `service_account.json`
   (this filename is gitignored — never commit credentials).
4. Share your target Google Spreadsheet with the service account email
   (found in the JSON key file under `client_email`).

### 3. Spreadsheet setup

- Create a **"Members"** tab with player names in column B, rows 2-31.
- Create one tab per player, named exactly as listed in the Members tab.
- The scraper appends data rows — it never creates or deletes tabs.

### 4. Configure

Edit `config.py` to set:

- `SPREADSHEET_ID` — the ID from your Google Spreadsheet URL.
- `SERVICE_ACCOUNT_KEY_PATH` — path to your JSON key (default:
  `service_account.json` in the project root).

## Usage

1. Open AFK Journey on PC at 1920x1080 fullscreen.
2. Navigate to the **World screen** (the scraper verifies this before starting).
3. Run:

```bash
python main.py
```

The scraper will navigate through all game modes, collect data, and append
one row per player to their respective sheet tab.

## Data collected

| Column | Source | Format |
|---|---|---|
| Date | UTC+0 | YYYY-MM-DD |
| Activity | Guild menu | integer 0-1080 |
| At Stage | AFK Stages ranking | S###, A###, or A1000 (Cleared) |
| DR Rank | Dream Realm ranking | integer or #N/A |
| SA Rank | Supreme Arena ranking | integer or #N/A |
| AL Rank | Arcane Labyrinth ranking | integer or #N/A |
| HD Rank | Honor Duel ranking | integer or #N/A |

## Development

```bash
# Lint
ruff check .

# Run tests
pytest tests/ -v
```

## Project structure

```
afkj-data-extractor/
├── main.py              # entry point, pipeline orchestration
├── config.py            # all constants: coords, regions, thresholds, IDs
├── exceptions.py        # OCRConfidenceError, ParseError
├── capture.py           # window detection, screen capture (mss)
├── navigate.py          # pyautogui sequences + template polling
├── parse.py             # OpenCV preprocessing, PaddleOCR, name matching
├── export.py            # gspread Sheets logic
├── assets/templates/    # reference PNGs for template matching (1920x1080)
├── debug/               # timestamped screenshots on failure (auto-created)
├── tests/
│   ├── fixtures/        # static screenshots for parse.py tests
│   ├── test_capture.py
│   ├── test_parse.py
│   ├── test_export.py
│   └── test_navigate.py
└── requirements.txt
```
