# AFK Journey Guild Scraper — CLAUDE.md

## Project Overview
Python tool that automates navigation of the AFK Journey PC native client
(1920×1080 fullscreen) to scrape guild member ranking statistics and append
data to per-player tabs in a Google Sheet. Screen capture + OCR only — no
game API, no memory reading, no browser automation.

## Tech Stack
- Python 3.11+, `mss`, `pyautogui`, `opencv-python`, `paddlepaddle`+`paddleocr`
- `gspread` + `google-auth` — Sheets export via service account
- `rapidfuzz` — fuzzy name matching

> **PaddlePaddle install note:** PaddlePaddle ships platform-specific wheels
> that are not always resolvable via plain `pip install`. In `requirements.txt`,
> pin the CPU-only wheel explicitly (e.g. `paddlepaddle==2.6.1`). If install
> fails, users should consult https://www.paddlepaddle.org.cn/install/quick for
> the correct `--find-links` URL for their platform. Document this in
> `README.md`.

## Common Commands
```bash
pip install -r requirements.txt
python main.py       # full scrape pipeline
pytest tests/ -v
ruff check .
```

## Project Structure
```
afk-journey-scraper/
├── main.py              # entry point, pipeline orchestration
├── config.py            # ALL constants: coords, regions, thresholds, IDs
├── exceptions.py        # OCRConfidenceError, ParseError, and any future custom exceptions
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

## Architecture Principles
- **`config.py` is the single source of truth** for all magic values. Never
  hardcode coordinates, thresholds, timeouts, or IDs elsewhere.
- **One responsibility per module.** `capture.py` does not navigate.
  `navigate.py` does not parse. `parse.py` does not export.
- **Functions return data.** Use `logging`, never `print`.
- **All navigation waits use template matching polls.** Never use `time.sleep()` as a substitute for template polling. The only acceptable `time.sleep()` calls are the 0.2s yield inside `wait_for_screen()`'s poll loop and an equivalent yield inside the frame-stability poll loop in scrolling — do not add `time.sleep()` calls anywhere else.
- **On any failure, abort immediately.** No partial writes.
- **Startup check:** Verify World screen template before any navigation. If not
  found, abort with a clear message telling the user to navigate there first.

## Full Run Sequence (strictly ordered)
1. **Startup** — load Members list; duplicate-date check against all player tabs;
   abort if today's date already exists in any tab. *(Sheets auth is validated
   here — before any game interaction — so a bad key or missing tab fails fast
   without touching the game client.)*
2. **Verify World screen** — template match before any navigation
3. **Scrape all modes** — collect all data in memory; no Sheets writes yet
4. **Export** — append one fully populated row per player

Never interleave navigation and writes.

## Navigation Structure
"Home" means the **World screen** throughout this document. `navigate_home()`
navigates back to the World screen and calls `wait_for_screen()` on the World
screen template before returning.

World screen gives access to:
- **Guild** — Weekly Activeness data
- **AFK Stages** — direct menu (not via Battle Modes)
- **Battle Modes** — Dream Realm, Supreme Arena, Arcane Labyrinth, Honor Duel

Pipeline for each **ranking mode** (AFK Stages, DR, SA, AL, HD):
1. Navigate to ranking menu → apply guild-members-only filter → scroll + scrape
   → navigate home → repeat

**Weekly Activeness is different:** read from the Guild menu, not a ranking
screen. Single activity integer per member. No guild-members-only filter
needed (guild menu already shows only members), but scrolling is still
required to reach all 30 members. Use the same scroll + stability-check
approach as ranking modes. A missing Activity value after full scrolling is
an OCR failure, not a valid absent state — abort.

## Navigation & Waiting
All UI state transitions use template matching polls. The only acceptable uses of `time.sleep()` are the 0.2s yield inside `wait_for_screen()`'s poll loop and an equivalent yield inside the frame-stability poll loop (see Scrolling & Scan Termination).
```python
def wait_for_screen(template_path: str, timeout: float = 10.0,
                    confidence: float = 0.85) -> None:
    start = time.time()
    template = cv2.imread(template_path)
    while time.time() - start < timeout:
        screenshot = capture_window()
        result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
        if result.max() >= confidence:
            return
        time.sleep(0.2)
    raise TimeoutError(f"Template '{template_path}' not found within {timeout}s")
```
`TimeoutError` is fatal — triggers abort and debug screenshot dump.

## Scrolling & Scan Termination
After applying the guild filter, scroll the list to capture all members.
**Do not use pixel-change detection** — the list springs back past the end,
producing false positives.

**Stop scrolling when either:**
1. 30 unique player names collected (guild max)
2. A full scroll step yields no **new** names — meaning cards were detected and
   OCR'd successfully, but all resolved names were already in the collected set.
   If cards are detected but OCR fails, that is an `OCRConfidenceError` — abort.
   If the card template matches zero cards after a stable frame, that is also
   an error — abort with a clear message (do not silently treat it as
   termination).

After each scroll: compare successive captures until two consecutive frames
are nearly identical (`cv2.absdiff` mean < `STABILITY_THRESHOLD` in config)
— then template match a repeated card element to find card Y positions, then
OCR data fields at known offsets from each Y.

Players from the Members list absent after full scrolling are unranked for
that mode — store `"#N/A"`. Weekly Activeness is the exception: it always
lists all members, so a missing Activity value is an OCR failure — abort.

## Player Card Layout
Non-overlapping cards with a small gap. Layout differs by mode:
- **Ranking modes (DR, SA, AL, HD):** rank number on the left
- **AFK Stages:** stage progress on the right, below a faded "Phase Progress"
  label — **do not OCR the label**, only the value beneath it
- **Weekly Activeness:** activity integer on the right, different position than
  AFK Stages

**Card detection strategy:** requires experimentation once M2 screenshots are
available. Do not hardcode row offsets. Document chosen approach here before
starting M4.

**Crop coordinates:** unknown at authoring time. After M2, dump screenshots,
measure (x, y, w, h) per field per mode using an image viewer with pixel
readout, and add to `config.py`. One region per field per mode — do not reuse
across modes with different layouts.

## Player Name Matching (in `parse.py`)
After OCR'ing a card name, fuzzy match against the Members list using
`rapidfuzz` with a threshold from `config.py` (start at 0.85):
- Match found → use canonical Members-list spelling; log match at DEBUG level
- No match → not a guild member; skip silently
- Never abort on name match failure — unmatched cards are expected

Tab lookup in `export.py` uses the already-resolved canonical name (exact
match). Fuzzy matching happens only in `parse.py`, never in `export.py`.

## OCR Language
Init PaddleOCR with English **and** Chinese Simplified — member names may
contain CJK characters. Config in `config.py`.

## Game Modes & Data Schema

| Mode | Source | Field | Notes |
|---|---|---|---|
| Weekly Activeness | Guild menu | `Activity` | integer 0-1080 |
| AFK Stages | Ranking menu | `At Stage` | "S###", "A###", "A1000" if Cleared |
| Dream Realm | Ranking menu | `DR Rank` | integer or "#N/A" |
| Supreme Arena | Ranking menu | `SA Rank` | integer or "#N/A" |
| Arcane Labyrinth | Ranking menu | `AL Rank` | integer or "#N/A" |
| Honor Duel | Ranking menu | `HD Rank` | integer or "#N/A" |

Each row also has `Date` (UTC+0, `YYYY-MM-DD`).

### Column order (per player tab, strictly enforced)
`Date` | `Activity` | `At Stage` | `DR Rank` | `SA Rank` | `AL Rank` | `HD Rank`

Define this as `COLUMN_ORDER` in `config.py`. `append_player_row()` must build
the row list in this exact order — never rely on dict insertion order or field
enumeration order.

### Activity parsing
`parse_activity()` must apply digit correction before casting to int: replace
letter `O` → `0`, letter `l` or `I` → `1`. Then:
- If the corrected string is not a valid integer → raise `OCRConfidenceError`
  (the OCR result is unreadable).
- If it is a valid integer but outside 0–1080 → raise `ParseError` (OCR
  succeeded but the value is semantically invalid). `ParseError` is also fatal.
Do not silently clamp or discard out-of-range values. Define both exception
classes in a dedicated `exceptions.py` module so they can be imported by any
module without circular imports.

### AFK Stage special cases
- On-screen text is literally `"Stage 503"` or `"Apex 503"` (prefix + space +
  integer). Parse with `r"Stage\s+(\d+)"` → `"S{n}"` and `r"Apex\s+(\d+)"` →
  `"A{n}"`.
- **Cleared** (the literal word `"Cleared"` rendered in green) → `"A1000"`.
  Detect Cleared state **before** attempting stage string parsing using a
  two-pass strategy:
  1. **Color check first:** mask the card region for the Cleared green (HSV
     range to be measured from M2 screenshots and stored in `config.py` as
     `CLEARED_HSV_LOWER` / `CLEARED_HSV_UPPER`). If sufficient green pixels
     are found, classify as Cleared without OCR.
  2. **OCR fallback:** if the color check is inconclusive, OCR the region and
     check for the string `"Cleared"` (case-insensitive). If found, classify
     as Cleared.
  A Cleared detection that passes either check is not an OCR failure.

### Rank parsing
`parse_rank()` applies the same digit correction as `parse_activity()` (`O`→`0`,
`l`/`I`→`1`) before casting to int. A corrected string that is not a valid
positive integer raises `OCRConfidenceError`. There is no upper-bound range
check for ranks (guild size is 30 but guild-wide rank can be any positive
integer).

### Unranked / absent
Store as `"#N/A"`. Never use `None`, `""`, `0`, or `"Unranked"`.

## Google Sheets Export
- **Auth:** service account JSON key, path in `config.py`. Never commit key.
- **Player list:** read from "Members" tab, column B, rows 2-31 at startup.
- **Duplicate guard:** check last row Date in every player tab at startup;
  abort entire run if today's UTC+0 date already exists anywhere. `Date` is
  always column A (index 0) in player tabs. `get_last_date()` reads the last
  populated value in column A of the given sheet.
- **Tab lookup:** exact match on canonical player name (case-sensitive).
  Abort if tab not found — do not create tabs.
- **Append:** `append_row(..., value_input_option="USER_ENTERED")` — required
  so "#N/A" is written as a native Sheets error, not a text string. Never use RAW.
- **Rate limiting:** use gspread's built-in retry; add delay between writes if
  quota errors occur.

## Error Handling
- All errors are fatal — abort immediately on any exception.
- Before aborting: save timestamped screenshot to `debug/`, log full traceback
  with context (player, mode, step).
- Both `OCRConfidenceError` and `ParseError` are fatal. `OCRConfidenceError`
  means PaddleOCR's confidence score was below `OCR_CONFIDENCE_THRESHOLD`.
  `ParseError` means OCR succeeded but the result is semantically invalid
  (e.g. Activity value out of range 0–1080). Both are defined in `exceptions.py`.
  `OCRConfidenceError` applies to all OCR'd fields including the name region.
  Note: a card whose name OCRs fine but does *not* fuzzy-match any guild member
  is silently skipped (not an error).
- Never write a partial row.

## Code Style
- Type hints on all signatures; Google-style docstrings on public functions
- Max line length 100; `pathlib.Path` not `os.path`; `logging` not `print`
- Error messages must state what was expected vs. what was observed

## Testing

### Unit-testable (mock all external dependencies)
- Frame differencing — identical/different image pairs, threshold behaviour
- Scroll deduplication and termination — mock per-scroll name results
- `parse_activity`, `parse_at_stage`, `parse_rank` — static fixture screenshots in `tests/fixtures/`.
  Since real game screenshots are unavailable during development, fixture images
  should be **synthetic**: plain-colour numpy arrays with text rendered via
  `cv2.putText()` at realistic positions. Document the synthetic values (e.g.
  activity=750, stage="Apex 503") in the test itself so failures are readable.
- Fuzzy name matching — threshold behaviour, good matches, near-misses, and non-members; verify canonical name returned on match and None on no-match
- Export functions — mocked gspread
- Player list loading — mocked Sheets API

### Live calibration only — do not write unit tests for these
- Card template matching, `STABILITY_THRESHOLD`, scroll step amount

### Manual integration script (built in M3)
Scrolls each mode against the live game, dumps settled frames to `debug/` with
card Y positions drawn as rectangles, logs collected names. Use to tune
`config.py` values before starting M4.

## Development Milestones

### M1 — Foundation
- Module stubs with docstrings: `main.py`, `config.py`, `exceptions.py`,
  `capture.py`, `navigate.py`, `parse.py`, `export.py`
- `requirements.txt` (pinned); `assets/templates/` and `debug/` with `.gitkeep`
- `tests/` scaffolded; `.gitignore` (`*service_account*.json`, `credentials.json`, `debug/`, `__pycache__/`, `.env`)
- `README.md` with setup instructions

### M2 — Window detection & capture
- Detect AFK Journey window by process name; capture as numpy array via `mss`
- Timestamped debug screenshot to `debug/`; unit tests with mocked `mss`
- **Calibration deliverable:** from M2 screenshots, measure and record in
  `config.py`: `CLEARED_HSV_LOWER`, `CLEARED_HSV_UPPER` (green range for
  Cleared state), `STABILITY_THRESHOLD` initial estimate, and any other
  color/region constants visible at this stage. These must be in `config.py`
  before M4 begins.

### M3 — Navigation
- `wait_for_screen()` polling function
- Navigation sequence for all 6 modes; `navigate_home()`
- Manual integration script for live calibration (see Testing above)
- Unit tests with mocked `pyautogui` and `capture`

### M4 — OCR & parsing <- CURRENT
- `extract_text(region, confidence)` → raises `OCRConfidenceError` if below threshold
- `parse_activity()`, `parse_at_stage()` (incl. Cleared detection), `parse_rank()`
- Fuzzy name matching in `parse.py`
- Unit tests with fixture screenshots

### M5 — Sheets export
- `load_member_names()`, `get_last_date()` (used by duplicate run guard at startup), `get_player_sheet()`,
  `append_player_row()` (with `USER_ENTERED`)
- Unit tests with mocked gspread

### M6 — Pipeline & polish
- `main.py` full end-to-end orchestration; structured logging to file
- Graceful abort: debug screenshot + traceback + non-zero exit
- `README.md` updated with full usage and service account setup

## Out of Scope
No mobile client, no live monitoring, no game API/memory reading.
Do not create or delete Sheets tabs — append only.
