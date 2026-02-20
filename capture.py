"""Window detection and screen capture for the AFK Journey client.

Uses ``mss`` to capture the game window as a numpy array. All capture
operations go through this module — no other module should import ``mss``
directly.
"""

import logging
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import cv2
import mss
import numpy as np

from config import (
    DEBUG_DIR,
    GAME_PROCESS_NAME,
    SCREEN_HEIGHT,
    SCREEN_WIDTH,
)

logger = logging.getLogger(__name__)


def find_game_window() -> dict[str, int]:
    """Locate the AFK Journey window by process name.

    Verifies that the game process is running via platform-appropriate
    process lookup. Since the game runs fullscreen at 1920x1080, the
    returned geometry covers the primary monitor origin.

    Returns:
        A dict with keys ``"left"``, ``"top"``, ``"width"``, ``"height"``
        describing the window geometry in screen coordinates.

    Raises:
        RuntimeError: If the game window cannot be found.
    """
    system = platform.system()

    if system == "Windows":
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {GAME_PROCESS_NAME}*",
             "/FO", "CSV", "/NH"],
            capture_output=True, text=True, check=False,
        )
        found = GAME_PROCESS_NAME.lower() in result.stdout.lower()
    else:
        result = subprocess.run(
            ["pgrep", "-fi", GAME_PROCESS_NAME],
            capture_output=True, text=True, check=False,
        )
        found = result.returncode == 0

    if not found:
        raise RuntimeError(
            f"Game window not found: expected process '{GAME_PROCESS_NAME}' "
            f"to be running, but it was not detected"
        )

    logger.info("Found game process: %s", GAME_PROCESS_NAME)
    return {
        "left": 0,
        "top": 0,
        "width": SCREEN_WIDTH,
        "height": SCREEN_HEIGHT,
    }


def capture_window() -> np.ndarray:
    """Capture the game window as a BGR numpy array.

    The returned image is always 1920x1080 regardless of actual window
    position on the desktop. The game must be running fullscreen.

    Returns:
        A numpy array of shape (1080, 1920, 3) in BGR colour order.

    Raises:
        RuntimeError: If capture fails or the window is not found.
    """
    geometry = find_game_window()

    with mss.mss() as sct:
        screenshot = sct.grab(geometry)

    # mss returns BGRA; drop alpha channel for OpenCV-compatible BGR.
    frame = np.array(screenshot)[:, :, :3]

    if frame.shape != (SCREEN_HEIGHT, SCREEN_WIDTH, 3):
        raise RuntimeError(
            f"Unexpected capture dimensions: expected "
            f"({SCREEN_HEIGHT}, {SCREEN_WIDTH}, 3), got {frame.shape}"
        )

    logger.debug("Captured frame: shape=%s", frame.shape)
    return frame


def save_debug_screenshot(context: str) -> Path:
    """Save a timestamped screenshot to the debug directory.

    Captures the current game window and writes it as a PNG with a
    UTC-timestamped filename. If the game window cannot be captured,
    falls back to a full primary-monitor capture.

    Args:
        context: A short label included in the filename to identify what
            triggered the screenshot (e.g. ``"ocr_failure_activity"``).

    Returns:
        The path to the saved PNG file.
    """
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{context}.png"
    filepath = DEBUG_DIR / filename

    try:
        frame = capture_window()
    except RuntimeError:
        logger.warning(
            "Game window unavailable for debug screenshot; "
            "falling back to primary monitor capture"
        )
        with mss.mss() as sct:
            screenshot = sct.grab(sct.monitors[1])
        frame = np.array(screenshot)[:, :, :3]

    cv2.imwrite(str(filepath), frame)
    logger.info("Debug screenshot saved: %s", filepath)
    return filepath
