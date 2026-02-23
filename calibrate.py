#!/usr/bin/env python3
"""Manual calibration tool for the AFK Journey guild scraper.

Provides interactive commands for capturing screenshots, tracking mouse
positions, cropping template images, and tuning scroll/card detection
parameters against the live game.

Subcommands::

    capture    Take labelled screenshots and track mouse position interactively.
    template   Crop a region from a screenshot and save it as a template image.
    scroll     Scroll through modes and dump annotated frames with card detection.

The ``capture`` subcommand is the starting point — use it to capture reference
screenshots for measuring click coordinates, crop regions, and template images.

**Run this script on Windows** (not WSL) — the game runs on the Windows host
and ``mss`` / ``pyautogui`` must access the native display.

Usage::

    python calibrate.py capture
    python calibrate.py template debug/screenshot.png world_screen 100 200 300 50
    python calibrate.py scroll
    python calibrate.py scroll activity afk_stages --scroll-steps 5
"""

import argparse
import logging
import sys
import threading
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
import pyautogui

from capture import capture_window, find_game_window, save_debug_screenshot
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
    game_move_to,
    navigate_home,
    navigate_to_afk_stages_ranking,
    navigate_to_arcane_labyrinth_ranking,
    navigate_to_dream_realm_ranking,
    navigate_to_guild_members,
    navigate_to_honor_duel_ranking,
    navigate_to_supreme_arena_ranking,
    wait_for_screen,
    wait_for_stability,
)

logger = logging.getLogger(__name__)

MODE_NAVIGATORS: dict[str, Callable[[], None]] = {
    "activity": navigate_to_guild_members,
    "afk_stages": navigate_to_afk_stages_ranking,
    "dream_realm": navigate_to_dream_realm_ranking,
    "supreme_arena": navigate_to_supreme_arena_ranking,
    "arcane_labyrinth": navigate_to_arcane_labyrinth_ranking,
    "honor_duel": navigate_to_honor_duel_ranking,
}

MAX_SCROLL_STEPS: int = 10


# ---------------------------------------------------------------------------
# Capture subcommand
# ---------------------------------------------------------------------------


def _track_mouse() -> None:
    """Continuously print absolute and game-relative mouse position until Enter is pressed."""
    try:
        geom = find_game_window()
        off_x, off_y = geom["left"], geom["top"]
    except RuntimeError:
        off_x, off_y = 0, 0
        print("  (game window not found — showing absolute only)")

    print("  Tracking mouse position (press Enter to stop)...")
    stop = threading.Event()

    def printer() -> None:
        while not stop.is_set():
            ax, ay = pyautogui.position()
            gx, gy = ax - off_x, ay - off_y
            print(
                f"\r  Abs: ({ax:4d}, {ay:4d})  Game: ({gx:4d}, {gy:4d})  ",
                end="", flush=True,
            )
            stop.wait(0.3)

    t = threading.Thread(target=printer, daemon=True)
    t.start()
    try:
        input()
    except EOFError:
        pass
    stop.set()
    t.join(timeout=1.0)
    print()


MEASUREMENT_STEPS: list[tuple[str, str, str]] = [
    # (config_constant, description, navigation_instruction)
    # --- World screen ---
    ("CLICK_GUILD", "Guild button", "Navigate to the World screen."),
    ("CLICK_BATTLE_MODES", "Battle Modes button", ""),
    ("CLICK_BACK", "Back / close button (X)", ""),
    # --- Guild hall ---
    ("CLICK_GUILD_MENU", "Guild menu button (opens member list)",
     "Click the Guild button to enter the Guild hall."),
    # --- Battle Modes menu ---
    ("CLICK_AFK_STAGES", "AFK Stages button",
     "Go back to World screen, then open Battle Modes."),
    ("CLICK_DREAM_REALM", "Dream Realm button", ""),
    ("CLICK_SUPREME_ARENA", "Supreme Arena button", ""),
    ("CLICK_ARCANE_LABYRINTH", "Arcane Labyrinth button", ""),
    ("CLICK_HONOR_DUEL", "Honor Duel button", ""),
    # --- Per-mode: ranking button, filter open, filter select ---
    ("CLICK_RANKING_AFK_STAGES", "Ranking button (AFK Stages)",
     "Enter AFK Stages so you can see its main screen."),
    ("CLICK_FILTER_1_AFK_STAGES", "Filter button (AFK Stages)",
     "Open the AFK Stages ranking screen."),
    ("CLICK_FILTER_2_AFK_STAGES", "Guild filter selection (AFK Stages)",
     "Click the filter button so the menu is open."),
    ("CLICK_RANKING_DREAM_REALM", "Ranking button (Dream Realm)",
     "Enter Dream Realm so you can see its main screen."),
    ("CLICK_FILTER_1_DREAM_REALM", "Filter button (Dream Realm)",
     "Open the Dream Realm ranking screen."),
    ("CLICK_FILTER_2_DREAM_REALM", "Guild filter selection (Dream Realm)",
     "Click the filter button so the menu is open."),
    ("CLICK_RANKING_SUPREME_ARENA", "Ranking button (Supreme Arena)",
     "Enter Supreme Arena so you can see its main screen."),
    ("CLICK_FILTER_1_SUPREME_ARENA", "Filter button (Supreme Arena)",
     "Open the Supreme Arena ranking screen."),
    ("CLICK_FILTER_2_SUPREME_ARENA", "Guild filter selection (Supreme Arena)",
     "Click the filter button so the menu is open."),
    ("CLICK_RANKING_ARCANE_LABYRINTH", "Ranking button (Arcane Labyrinth)",
     "Enter Arcane Labyrinth so you can see its main screen."),
    ("CLICK_FILTER_1_ARCANE_LABYRINTH", "Filter button (Arcane Labyrinth)",
     "Open the Arcane Labyrinth ranking screen."),
    ("CLICK_FILTER_2_ARCANE_LABYRINTH", "Guild filter selection (Arcane Labyrinth)",
     "Click the filter button so the menu is open."),
    ("CLICK_RANKING_HONOR_DUEL", "Ranking button (Honor Duel)",
     "Enter Honor Duel so you can see its main screen."),
    ("CLICK_FILTER_1_HONOR_DUEL", "Filter button (Honor Duel)",
     "Open the Honor Duel ranking screen."),
    ("CLICK_FILTER_2_HONOR_DUEL", "Guild filter selection (Honor Duel)",
     "Click the filter button so the menu is open."),
    # --- Scroll region ---
    ("SCROLL_REGION_CENTER", "Center of the scrollable list area", ""),
]


def _run_measure() -> None:
    """Walk through each config constant, prompting the user to hover and confirm.

    Reads the game window position once at the start and subtracts the
    offset from each reading so that stored coordinates are game-relative.
    """
    try:
        geom = find_game_window()
        off_x, off_y = geom["left"], geom["top"]
    except RuntimeError:
        print("  WARNING: game window not found — coordinates will be absolute")
        off_x, off_y = 0, 0

    print()
    print("=" * 58)
    print("  Guided Coordinate Measurement (game-relative)")
    print("=" * 58)
    print()
    print("  For each step: navigate the game, hover your mouse over")
    print("  the target, then come back here and press Enter.")
    print("  Type 'skip' to skip a step, 'quit' to stop early.")
    if off_x or off_y:
        print(f"  Window offset: ({off_x}, {off_y})")
    print()

    results: list[tuple[str, tuple[int, int]]] = []

    for const_name, description, nav_hint in MEASUREMENT_STEPS:
        if nav_hint:
            print(f"  >>> {nav_hint}")
            print()

        print(f"  Hover over: {description}  ({const_name})")

        try:
            response = input("  Press Enter when ready (or 'skip'/'quit'): ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if response.lower() in ("quit", "q"):
            break
        if response.lower() == "skip":
            print(f"  Skipped {const_name}")
            print()
            continue

        ax, ay = pyautogui.position()
        gx, gy = ax - off_x, ay - off_y
        results.append((const_name, (gx, gy)))
        print(f"  {const_name} = ({gx}, {gy})  (abs: {ax}, {ay})")
        print()

    if not results:
        print("  No measurements taken.")
        return

    # Print summary
    print()
    print("=" * 58)
    print("  Measurement Results")
    print("=" * 58)
    print()
    for name, coords in results:
        print(f"  {name} = {coords}")

    # Save to file
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    outfile = DEBUG_DIR / f"measurements_{timestamp}.txt"
    with open(outfile, "w") as f:
        for name, coords in results:
            f.write(f"{name} = {coords}\n")
    print(f"\n  Saved to: {outfile}")
    print()


def cmd_capture(_args: argparse.Namespace) -> None:
    """Interactive screenshot capture and mouse position tracking.

    Verifies the game process is running, then enters an interactive loop
    where the user can take labelled screenshots and check mouse coordinates.
    Navigate the game manually between captures.
    """
    try:
        geom = find_game_window()
        off_x, off_y = geom["left"], geom["top"]
    except RuntimeError as exc:
        print(f"Error: {exc}")
        print("Make sure AFK Journey is running fullscreen at 1920x1080.")
        sys.exit(1)

    saved: list[Path] = []

    print()
    print("=" * 58)
    print("  AFK Journey Calibration — Capture Mode")
    print("=" * 58)
    print()
    print("Navigate the game manually, then use these commands:")
    print()
    print("  <label>   Capture screenshot (3s delay to Alt+Tab to game)")
    print("  Enter     Print current mouse (x, y) position")
    print("  track     Continuously print mouse position (Enter to stop)")
    print("  measure   Guided walkthrough of all click coordinates")
    print("  list      Show screenshots saved this session")
    print("  quit      Exit")
    print()
    print(f"Screenshots saved to: {DEBUG_DIR}/")
    print()

    while True:
        try:
            cmd = input("capture> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not cmd:
            ax, ay = pyautogui.position()
            gx, gy = ax - off_x, ay - off_y
            print(f"  Abs: ({ax}, {ay})  Game: ({gx}, {gy})")
            continue

        if cmd in ("quit", "q", "exit"):
            break

        if cmd == "track":
            _track_mouse()
            continue

        if cmd == "measure":
            _run_measure()
            continue

        if cmd == "list":
            if not saved:
                print("  No screenshots saved this session.")
            else:
                for p in saved:
                    print(f"  {p}")
            continue

        # Anything else is a label → capture screenshot with delay
        label = cmd.replace(" ", "_")
        for i in range(3, 0, -1):
            print(f"\r  Capturing in {i}...  ", end="", flush=True)
            time.sleep(1)
        print("\r  Capturing...        ", end="", flush=True)
        try:
            frame = capture_window()
        except RuntimeError as exc:
            print(f"\r  Capture failed: {exc}")
            continue

        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"calibrate_{timestamp}_{label}.png"
        filepath = DEBUG_DIR / filename
        cv2.imwrite(str(filepath), frame)
        saved.append(filepath)
        print(f"  Saved: {filepath}")

    print(f"\n{len(saved)} screenshot(s) saved to {DEBUG_DIR}/")


# ---------------------------------------------------------------------------
# Template subcommand
# ---------------------------------------------------------------------------


def cmd_template(args: argparse.Namespace) -> None:
    """Crop a region from a screenshot and save it as a template image.

    Reads the source image, crops the rectangle defined by (x, y, w, h),
    and writes the result to ``assets/templates/<name>.png``.
    """
    source = Path(args.source)
    if not source.exists():
        print(f"Error: source image not found: {source}")
        sys.exit(1)

    img = cv2.imread(str(source))
    if img is None:
        print(f"Error: could not read image: {source}")
        sys.exit(1)

    x, y, w, h = args.x, args.y, args.w, args.h
    img_h, img_w = img.shape[:2]

    if x < 0 or y < 0 or w <= 0 or h <= 0:
        print("Error: invalid crop region — x, y must be >= 0 and w, h must be > 0")
        sys.exit(1)

    if x + w > img_w or y + h > img_h:
        print(
            f"Error: crop region ({x}, {y}, {w}, {h}) exceeds image bounds "
            f"({img_w}x{img_h})"
        )
        sys.exit(1)

    cropped = img[y : y + h, x : x + w]

    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    name = args.name if args.name.endswith(".png") else f"{args.name}.png"
    dest = TEMPLATE_DIR / name
    cv2.imwrite(str(dest), cropped)
    print(f"Template saved: {dest}  ({w}x{h} from ({x}, {y}))")


# ---------------------------------------------------------------------------
# Scroll subcommand
# ---------------------------------------------------------------------------


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
        game_move_to(*SCROLL_REGION_CENTER)
        pyautogui.scroll(-SCROLL_STEP)
        logger.debug(
            "Scrolled down %d px at (%d, %d)", SCROLL_STEP, *SCROLL_REGION_CENTER
        )

    navigate_home()
    logger.info("Finished calibrating %s", mode)


def cmd_scroll(args: argparse.Namespace) -> None:
    """Navigate to each mode, scroll through rankings, and dump annotated frames."""
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


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point — parse subcommand and dispatch."""
    parser = argparse.ArgumentParser(
        description="Manual calibration tool for the AFK Journey guild scraper.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Typical workflow:\n"
            "  1. python calibrate.py capture\n"
            "     Navigate the game manually, take screenshots of each screen,\n"
            "     and use 'track' / Enter to record click coordinates.\n"
            "  2. python calibrate.py template debug/screenshot.png world_screen"
            " X Y W H\n"
            "     Crop template images from captured screenshots.\n"
            "  3. Update config.py with measured coordinates and thresholds.\n"
            "  4. python calibrate.py scroll\n"
            "     Test navigation and card detection with the new values."
        ),
    )
    subparsers = parser.add_subparsers(dest="command")

    # capture ---
    subparsers.add_parser(
        "capture",
        help="Interactive screenshot capture and mouse position tracking",
        description=(
            "Take labelled screenshots of the game and track mouse position. "
            "Navigate the game manually between captures. Use this to gather "
            "reference images for measuring click coordinates, crop regions, "
            "and creating template images."
        ),
    )

    # template ---
    tmpl_parser = subparsers.add_parser(
        "template",
        help="Crop a region from a screenshot and save as a template image",
        description=(
            "Crop a rectangle from a source screenshot and save it to "
            "assets/templates/<name>.png for use with template matching."
        ),
    )
    tmpl_parser.add_argument(
        "source",
        help="Path to the source screenshot (e.g. debug/calibrate_..._world.png)",
    )
    tmpl_parser.add_argument(
        "name",
        help="Template name (e.g. 'world_screen' → assets/templates/world_screen.png)",
    )
    tmpl_parser.add_argument("x", type=int, help="Left edge of crop region")
    tmpl_parser.add_argument("y", type=int, help="Top edge of crop region")
    tmpl_parser.add_argument("w", type=int, help="Width of crop region")
    tmpl_parser.add_argument("h", type=int, help="Height of crop region")

    # scroll ---
    scroll_parser = subparsers.add_parser(
        "scroll",
        help="Scroll through modes and dump annotated frames with card detection",
        description=(
            "Navigate to each mode, scroll through the ranking list, and "
            "save annotated frames with detected card positions to debug/. "
            "Requires template images and calibrated navigation coordinates."
        ),
    )
    scroll_parser.add_argument(
        "modes",
        nargs="*",
        default=list(MODE_NAVIGATORS.keys()),
        help=(
            "Modes to calibrate (default: all). "
            f"Choices: {', '.join(MODE_NAVIGATORS.keys())}"
        ),
    )
    scroll_parser.add_argument(
        "--scroll-steps",
        type=int,
        default=MAX_SCROLL_STEPS,
        help=f"Max scroll steps per mode (default: {MAX_SCROLL_STEPS})",
    )

    args = parser.parse_args()

    if args.command == "capture":
        # Minimal logging for interactive mode
        logging.basicConfig(level=logging.WARNING)
        cmd_capture(args)

    elif args.command == "template":
        logging.basicConfig(level=logging.WARNING)
        cmd_template(args)

    elif args.command == "scroll":
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        )
        for mode in args.modes:
            if mode not in MODE_NAVIGATORS:
                scroll_parser.error(
                    f"Unknown mode '{mode}'. "
                    f"Choose from: {', '.join(MODE_NAVIGATORS.keys())}"
                )
        cmd_scroll(args)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
