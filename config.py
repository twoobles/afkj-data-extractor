"""Central configuration for the AFK Journey guild scraper.

This module is the single source of truth for all magic values — coordinates,
regions, thresholds, timeouts, and IDs. Never hardcode these values elsewhere.

Constants marked "# TODO(M2)" or similar require calibration from real game
screenshots and will be populated in the corresponding milestone.
"""

from pathlib import Path
from typing import Final

import numpy as np

# ---------------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------------

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parent
DEBUG_DIR: Final[Path] = PROJECT_ROOT / "debug"
TEMPLATE_DIR: Final[Path] = PROJECT_ROOT / "assets" / "templates"

# ---------------------------------------------------------------------------
# Google Sheets — service account & spreadsheet
# ---------------------------------------------------------------------------

# Path to the service account JSON key file. Never commit this file.
SERVICE_ACCOUNT_KEY_PATH: Final[Path] = PROJECT_ROOT / "service_account.json"

# The Google Spreadsheet ID (from the URL).  # TODO(M5): populate
SPREADSHEET_ID: Final[str] = ""

# ---------------------------------------------------------------------------
# Google Sheets — Members tab layout
# ---------------------------------------------------------------------------

SHEET_MEMBERS_TAB: Final[str] = "Members"
SHEET_MEMBERS_COL: Final[str] = "B"
SHEET_MEMBERS_ROW_START: Final[int] = 2
SHEET_MEMBERS_ROW_END: Final[int] = 31

# ---------------------------------------------------------------------------
# Column order (per-player tab, strictly enforced)
# ---------------------------------------------------------------------------

COLUMN_ORDER: Final[list[str]] = [
    "Date",
    "Activity",
    "At Stage",
    "DR Rank",
    "SA Rank",
    "AL Rank",
    "HD Rank",
]

# ---------------------------------------------------------------------------
# Game window
# ---------------------------------------------------------------------------

# Process name used to locate the AFK Journey window.  # TODO(M2): confirm
GAME_PROCESS_NAME: Final[str] = "AFK Journey"

SCREEN_WIDTH: Final[int] = 1920
SCREEN_HEIGHT: Final[int] = 1080

# ---------------------------------------------------------------------------
# Template matching & waiting
# ---------------------------------------------------------------------------

TEMPLATE_CONFIDENCE: Final[float] = 0.85
WAIT_TIMEOUT: Final[float] = 10.0
POLL_INTERVAL: Final[float] = 0.2

# ---------------------------------------------------------------------------
# Frame stability (used after scrolling)
# ---------------------------------------------------------------------------

# Mean pixel difference threshold for cv2.absdiff.  # TODO(M2): calibrate
STABILITY_THRESHOLD: Final[float] = 2.0

# ---------------------------------------------------------------------------
# Scrolling
# ---------------------------------------------------------------------------

# Pixels to scroll per step.  # TODO(M3): calibrate
SCROLL_STEP: Final[int] = 300

# Maximum number of guild members.
GUILD_MAX_MEMBERS: Final[int] = 30

# ---------------------------------------------------------------------------
# OCR
# ---------------------------------------------------------------------------

# PaddleOCR language list — English + Chinese Simplified for CJK names.
OCR_LANGUAGES: Final[list[str]] = ["en", "ch"]

# Minimum OCR confidence score to accept a result.  # TODO(M4): tune
OCR_CONFIDENCE_THRESHOLD: Final[float] = 0.7

# ---------------------------------------------------------------------------
# Fuzzy name matching
# ---------------------------------------------------------------------------

FUZZY_MATCH_THRESHOLD: Final[float] = 0.85

# ---------------------------------------------------------------------------
# AFK Stage — Cleared detection (HSV colour check)
# ---------------------------------------------------------------------------

# HSV range for the green "Cleared" text.  # TODO(M2): measure from screenshots
CLEARED_HSV_LOWER: Final[np.ndarray] = np.array([0, 0, 0])
CLEARED_HSV_UPPER: Final[np.ndarray] = np.array([0, 0, 0])

# Minimum number of green pixels to classify a card as Cleared.  # TODO(M2)
CLEARED_PIXEL_THRESHOLD: Final[int] = 50

# ---------------------------------------------------------------------------
# Data values
# ---------------------------------------------------------------------------

UNRANKED_VALUE: Final[str] = "#N/A"

# Activity valid range (inclusive).
ACTIVITY_MIN: Final[int] = 0
ACTIVITY_MAX: Final[int] = 1080

# ---------------------------------------------------------------------------
# Navigation click coordinates (1920x1080)
# ---------------------------------------------------------------------------
# Each entry is an (x, y) tuple.  # TODO(M3): measure from screenshots

# World screen → Guild menu
CLICK_GUILD: Final[tuple[int, int]] = (0, 0)

# Guild menu → Weekly Activeness tab
CLICK_GUILD_ACTIVENESS: Final[tuple[int, int]] = (0, 0)

# World screen → Battle Modes / Ranking menus
CLICK_BATTLE_MODES: Final[tuple[int, int]] = (0, 0)
CLICK_AFK_STAGES: Final[tuple[int, int]] = (0, 0)
CLICK_DREAM_REALM: Final[tuple[int, int]] = (0, 0)
CLICK_SUPREME_ARENA: Final[tuple[int, int]] = (0, 0)
CLICK_ARCANE_LABYRINTH: Final[tuple[int, int]] = (0, 0)
CLICK_HONOR_DUEL: Final[tuple[int, int]] = (0, 0)

# Guild-members-only filter toggle
CLICK_GUILD_FILTER: Final[tuple[int, int]] = (0, 0)

# Back / close buttons
CLICK_BACK: Final[tuple[int, int]] = (0, 0)

# ---------------------------------------------------------------------------
# Scroll region (the area to position the mouse before scrolling)
# ---------------------------------------------------------------------------

SCROLL_REGION_CENTER: Final[tuple[int, int]] = (960, 540)  # TODO(M3): refine

# ---------------------------------------------------------------------------
# Template file names (inside TEMPLATE_DIR)
# ---------------------------------------------------------------------------

TEMPLATE_WORLD_SCREEN: Final[str] = "world_screen.png"
TEMPLATE_GUILD_MENU: Final[str] = "guild_menu.png"
TEMPLATE_RANKING_SCREEN: Final[str] = "ranking_screen.png"
TEMPLATE_CARD: Final[str] = "card.png"

# ---------------------------------------------------------------------------
# Card OCR crop regions — (x_offset, y_offset, width, height)
# Offsets are relative to the detected card Y position.
# ---------------------------------------------------------------------------
# TODO(M4): measure from screenshots — one region per field per mode

# Player name region (shared across all modes if layout is consistent)
CROP_NAME: Final[tuple[int, int, int, int]] = (0, 0, 0, 0)

# Ranking modes (DR, SA, AL, HD) — rank number on the left
CROP_RANK: Final[tuple[int, int, int, int]] = (0, 0, 0, 0)

# AFK Stages — stage progress on the right
CROP_AFK_STAGE: Final[tuple[int, int, int, int]] = (0, 0, 0, 0)

# Weekly Activeness — activity integer on the right
CROP_ACTIVITY: Final[tuple[int, int, int, int]] = (0, 0, 0, 0)
