"""Window detection and screen capture for the AFK Journey client.

Uses ``mss`` to capture the game window as a numpy array. All capture
operations go through this module — no other module should import ``mss``
directly.
"""

import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


def find_game_window() -> dict[str, int]:
    """Locate the AFK Journey window by process name.

    Returns:
        A dict with keys ``"left"``, ``"top"``, ``"width"``, ``"height"``
        describing the window geometry in screen coordinates.

    Raises:
        RuntimeError: If the game window cannot be found.
    """
    raise NotImplementedError


def capture_window() -> np.ndarray:
    """Capture the game window as a BGR numpy array.

    The returned image is always 1920x1080 regardless of actual window
    position on the desktop.

    Returns:
        A numpy array of shape (1080, 1920, 3) in BGR colour order.

    Raises:
        RuntimeError: If capture fails or the window is not found.
    """
    raise NotImplementedError


def save_debug_screenshot(context: str) -> Path:
    """Save a timestamped screenshot to the debug directory.

    Args:
        context: A short label included in the filename to identify what
            triggered the screenshot (e.g. ``"ocr_failure_activity"``).

    Returns:
        The path to the saved PNG file.
    """
    raise NotImplementedError
