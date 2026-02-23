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
    GAME_HEIGHT,
    GAME_PROCESS_NAME,
    GAME_WIDTH,
)

logger = logging.getLogger(__name__)


def _find_window_rect_windows() -> dict[str, int]:
    """Find the AFK Journey client area rectangle using the Windows API.

    Uses ``ctypes`` to enumerate visible windows, find one whose title
    contains ``GAME_PROCESS_NAME``, then read its client-area origin via
    ``GetClientRect`` + ``ClientToScreen``.

    Returns:
        A dict with keys ``"left"``, ``"top"``, ``"width"``, ``"height"``
        describing the client area in screen coordinates.

    Raises:
        RuntimeError: If no matching window is found, or the client area
            dimensions do not match ``GAME_WIDTH x GAME_HEIGHT``.
    """
    import ctypes
    import ctypes.wintypes

    user32 = ctypes.windll.user32

    # Storage for the result found by the callback
    found: list[int] = []  # will hold [hwnd] if found

    # EnumWindows callback type
    WNDENUMPROC = ctypes.WINFUNCTYPE(
        ctypes.wintypes.BOOL,
        ctypes.wintypes.HWND,
        ctypes.wintypes.LPARAM,
    )

    def enum_callback(hwnd: int, _lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True  # continue enumeration
        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        if GAME_PROCESS_NAME.lower() in buf.value.lower():
            found.append(hwnd)
            return False  # stop enumeration
        return True

    user32.EnumWindows(WNDENUMPROC(enum_callback), 0)

    if not found:
        raise RuntimeError(
            f"Game window not found: no visible window with title containing "
            f"'{GAME_PROCESS_NAME}'"
        )

    hwnd = found[0]

    # Get client area dimensions
    rect = ctypes.wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rect))
    client_w = rect.right - rect.left
    client_h = rect.bottom - rect.top

    if client_w != GAME_WIDTH or client_h != GAME_HEIGHT:
        raise RuntimeError(
            f"Game client area dimensions mismatch: expected "
            f"{GAME_WIDTH}x{GAME_HEIGHT}, got {client_w}x{client_h}"
        )

    # Convert client (0, 0) to screen coordinates
    point = ctypes.wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(point))

    logger.info(
        "Found game window at screen position (%d, %d), client area %dx%d",
        point.x, point.y, client_w, client_h,
    )

    return {
        "left": point.x,
        "top": point.y,
        "width": GAME_WIDTH,
        "height": GAME_HEIGHT,
    }


def find_game_window() -> dict[str, int]:
    """Locate the AFK Journey window and return its client area geometry.

    On Windows, uses the Windows API (``EnumWindows``, ``GetClientRect``,
    ``ClientToScreen``) to find the actual window position. On Linux, falls
    back to a subprocess ``pgrep`` check with hardcoded geometry (the game
    only runs on Windows; Linux path exists for development convenience).

    Returns:
        A dict with keys ``"left"``, ``"top"``, ``"width"``, ``"height"``
        describing the client area in screen coordinates.

    Raises:
        RuntimeError: If the game window cannot be found, or client area
            dimensions do not match ``GAME_WIDTH x GAME_HEIGHT``.
    """
    system = platform.system()

    if system == "Windows":
        return _find_window_rect_windows()

    # Linux fallback — process check only (hardcoded geometry)
    result = subprocess.run(
        ["pgrep", "-fi", GAME_PROCESS_NAME],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Game window not found: expected process '{GAME_PROCESS_NAME}' "
            f"to be running, but it was not detected"
        )

    logger.info("Found game process: %s", GAME_PROCESS_NAME)
    return {
        "left": 0,
        "top": 0,
        "width": GAME_WIDTH,
        "height": GAME_HEIGHT,
    }


def capture_window() -> np.ndarray:
    """Capture the game window as a BGR numpy array.

    The returned image is always ``GAME_WIDTH x GAME_HEIGHT`` regardless of
    actual window position on the desktop.

    Returns:
        A numpy array of shape ``(GAME_HEIGHT, GAME_WIDTH, 3)`` in BGR
        colour order.

    Raises:
        RuntimeError: If capture fails or the window is not found.
    """
    geometry = find_game_window()

    with mss.mss() as sct:
        screenshot = sct.grab(geometry)

    # mss returns BGRA; drop alpha channel for OpenCV-compatible BGR.
    frame = np.array(screenshot)[:, :, :3]

    if frame.shape != (GAME_HEIGHT, GAME_WIDTH, 3):
        raise RuntimeError(
            f"Unexpected capture dimensions: expected "
            f"({GAME_HEIGHT}, {GAME_WIDTH}, 3), got {frame.shape}"
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
