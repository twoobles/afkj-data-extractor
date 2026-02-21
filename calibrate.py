#!/usr/bin/env python3
"""Manual integration script for live calibration of navigation and scrolling.

Scrolls each mode against the live game, waits for frame stability, detects
card Y positions via template matching, draws rectangles on detected positions,
and dumps annotated frames to ``debug/``.  Use to tune ``config.py`` values
(scroll step, card template, crop regions) before starting M4.

This is **not** a unit test — it requires the AFK Journey client to be running
at 1920x1080 fullscreen on the World screen.

Usage::

    python calibrate.py                              # all modes
    python calibrate.py activity afk_stages          # specific modes
    python calibrate.py --scroll-steps 5 dream_realm # limit scroll steps
"""

import argparse
import logging
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
import pyautogui

from capture import save_debug_screenshot
from config import (
    DEBUG_DIR,
    SCROLL_REGION_CENTER,
    SCROLL_STEP,
    TEMPLATE_CARD,
    TEMPLATE_CONFIDENCE,
    TEMPLATE_DIR,
    TEMPLATE_WORLD_SCREEN,
)
from navigate import (
    navigate_home,
    navigate_to_afk_stages_ranking,
    navigate_to_arcane_labyrinth_ranking,
    navigate_to_dream_realm_ranking,
    navigate_to_guild_activeness,
    navigate_to_honor_duel_ranking,
    navigate_to_supreme_arena_ranking,
    wait_for_screen,
    wait_for_stability,
)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

MODE_NAVIGATORS: dict[str, Callable[[], None]] = {
    "activity": navigate_to_guild_activeness,
    "afk_stages": navigate_to_afk_stages_ranking,
    "dream_realm": navigate_to_dream_realm_ranking,
    "supreme_arena": navigate_to_supreme_arena_ranking,
    "arcane_labyrinth": navigate_to_arcane_labyrinth_ranking,
    "honor_duel": navigate_to_honor_duel_ranking,
}

MAX_SCROLL_STEPS: int = 10


def detect_card_positions(frame: np.ndarray) -> list[int]:
    """Detect card Y positions in *frame* via template matching.

    Loads the card template from ``TEMPLATE_DIR / TEMPLATE_CARD`` and finds
    all match locations above ``TEMPLATE_CONFIDENCE``.  Nearby Y values are
    clustered (within template height) to avoid duplicates.

    Args:
        frame: BGR screenshot to search.

    Returns:
        Sorted list of unique card Y positions.  Empty if the card template
        is missing or no matches are found.
    """
    card_path = str(TEMPLATE_DIR / TEMPLATE_CARD)
    card_template = cv2.imread(card_path)
    if card_template is None:
        logger.warning(
            "Card template not found at %s — skipping card detection", card_path
        )
        return []

    result = cv2.matchTemplate(frame, card_template, cv2.TM_CCOEFF_NORMED)
    locations = np.where(result >= TEMPLATE_CONFIDENCE)
    y_values = sorted(set(locations[0].tolist()))

    if not y_values:
        logger.info("No card positions detected above confidence %.2f", TEMPLATE_CONFIDENCE)
        return []

    # Cluster nearby Y values (within one template height)
    template_h = card_template.shape[0]
    clusters: list[list[int]] = [[y_values[0]]]
    for y in y_values[1:]:
        if y - clusters[-1][0] < template_h:
            clusters[-1].append(y)
        else:
            clusters.append([y])

    positions = [int(np.mean(c)) for c in clusters]
    logger.info("Detected %d card(s) at Y positions: %s", len(positions), positions)
    return positions


def draw_card_rectangles(
    frame: np.ndarray,
    y_positions: list[int],
    card_height: int = 120,
) -> np.ndarray:
    """Draw labelled rectangles at each card Y position on a copy of *frame*.

    Args:
        frame: BGR image to annotate.
        y_positions: Y coordinates of detected cards.
        card_height: Approximate card height in pixels for rectangle sizing.

    Returns:
        Annotated copy of *frame*.
    """
    annotated = frame.copy()
    for i, y in enumerate(y_positions):
        cv2.rectangle(
            annotated,
            (50, y),
            (frame.shape[1] - 50, y + card_height),
            (0, 0, 255),
            2,
        )
        cv2.putText(
            annotated,
            f"Card {i} (y={y})",
            (60, y - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 0, 255),
            2,
        )
    return annotated


def save_calibration_frame(
    frame: np.ndarray,
    mode: str,
    step: int,
) -> Path:
    """Write an annotated calibration frame to ``DEBUG_DIR``.

    Args:
        frame: BGR image to save.
        mode: Mode name for the filename.
        step: Scroll step number.

    Returns:
        Path to the saved PNG file.
    """
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"calibrate_{timestamp}_{mode}_step{step:02d}.png"
    filepath = DEBUG_DIR / filename
    cv2.imwrite(str(filepath), frame)
    logger.info("Saved calibration frame: %s", filepath)
    return filepath


def calibrate_mode(mode: str, max_steps: int = MAX_SCROLL_STEPS) -> None:
    """Navigate to *mode*, scroll through the list, and dump annotated frames.

    For each scroll step:

    1. Wait for frame stability.
    2. Detect card Y positions via template matching.
    3. Draw rectangles at detected positions.
    4. Save the annotated frame to ``debug/``.
    5. Scroll down by ``SCROLL_STEP`` pixels.

    After all steps, navigates home.

    Args:
        mode: One of the keys in ``MODE_NAVIGATORS``.
        max_steps: Maximum number of scroll steps to perform.
    """
    logger.info("=" * 60)
    logger.info("Calibrating mode: %s", mode)
    logger.info("=" * 60)

    navigator = MODE_NAVIGATORS[mode]
    navigator()

    for step in range(max_steps):
        logger.info("--- Scroll step %d/%d ---", step, max_steps - 1)

        try:
            frame = wait_for_stability()
        except TimeoutError:
            logger.error("Frame stability not reached at step %d, stopping", step)
            break

        y_positions = detect_card_positions(frame)
        annotated = draw_card_rectangles(frame, y_positions)
        save_calibration_frame(annotated, mode, step)

        # Scroll down
        pyautogui.moveTo(*SCROLL_REGION_CENTER)
        pyautogui.scroll(-SCROLL_STEP)
        logger.debug("Scrolled down %d px at (%d, %d)", SCROLL_STEP, *SCROLL_REGION_CENTER)

    navigate_home()
    logger.info("Finished calibrating %s", mode)


def main() -> None:
    """Entry point — parse arguments and run calibration for selected modes."""
    parser = argparse.ArgumentParser(
        description="Manual calibration: scroll modes and dump annotated frames",
    )
    parser.add_argument(
        "modes",
        nargs="*",
        default=list(MODE_NAVIGATORS.keys()),
        help=(
            "Modes to calibrate (default: all). "
            f"Choices: {', '.join(MODE_NAVIGATORS.keys())}"
        ),
    )
    parser.add_argument(
        "--scroll-steps",
        type=int,
        default=MAX_SCROLL_STEPS,
        help=f"Max scroll steps per mode (default: {MAX_SCROLL_STEPS})",
    )
    args = parser.parse_args()

    # Validate mode names
    for mode in args.modes:
        if mode not in MODE_NAVIGATORS:
            parser.error(
                f"Unknown mode '{mode}'. "
                f"Choose from: {', '.join(MODE_NAVIGATORS.keys())}"
            )

    # Verify world screen before any navigation
    world_template = str(TEMPLATE_DIR / TEMPLATE_WORLD_SCREEN)
    logger.info("Checking for World screen...")
    try:
        wait_for_screen(world_template, timeout=5.0)
    except (TimeoutError, FileNotFoundError) as exc:
        logger.error(
            "World screen not detected. Please navigate to the World screen "
            "in the AFK Journey client before running this script. (%s)",
            exc,
        )
        sys.exit(1)

    logger.info("World screen confirmed. Starting calibration for: %s", args.modes)

    for mode in args.modes:
        try:
            calibrate_mode(mode, max_steps=args.scroll_steps)
        except Exception:
            logger.exception("Calibration failed for mode: %s", mode)
            save_debug_screenshot(f"calibrate_fail_{mode}")
            sys.exit(1)

    logger.info("All calibration complete.")


if __name__ == "__main__":
    main()
