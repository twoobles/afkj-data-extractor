"""Tests for capture.py — window detection and screen capture."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from capture import capture_window, find_game_window, save_debug_screenshot
from config import GAME_HEIGHT, GAME_WIDTH


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_bgra_frame(
    width: int = GAME_WIDTH,
    height: int = GAME_HEIGHT,
) -> np.ndarray:
    """Create a fake BGRA frame matching mss output format."""
    return np.zeros((height, width, 4), dtype=np.uint8)


def _mock_window_rect(left: int = 100, top: int = 50) -> dict[str, int]:
    """Return a window geometry dict with a non-zero origin."""
    return {
        "left": left,
        "top": top,
        "width": GAME_WIDTH,
        "height": GAME_HEIGHT,
    }


def _mock_subprocess_not_found() -> MagicMock:
    """Return a mock subprocess result indicating the process was not found."""
    mock = MagicMock()
    mock.stdout = 'INFO: No tasks are running which match the specified criteria.\n'
    mock.returncode = 1
    return mock


# ---------------------------------------------------------------------------
# find_game_window — Windows path
# ---------------------------------------------------------------------------

class TestFindGameWindowWindows:
    """Tests for find_game_window() on Windows (via _find_window_rect_windows)."""

    @patch("capture._find_window_rect_windows")
    @patch("capture.platform.system", return_value="Windows")
    def test_found_on_windows(
        self, _mock_system: MagicMock, mock_rect: MagicMock,
    ) -> None:
        """Returns geometry dict when game window is detected on Windows."""
        mock_rect.return_value = _mock_window_rect(left=200, top=100)

        result = find_game_window()

        assert result == {
            "left": 200,
            "top": 100,
            "width": GAME_WIDTH,
            "height": GAME_HEIGHT,
        }
        mock_rect.assert_called_once()

    @patch("capture._find_window_rect_windows")
    @patch("capture.platform.system", return_value="Windows")
    def test_not_found_on_windows(
        self, _mock_system: MagicMock, mock_rect: MagicMock,
    ) -> None:
        """Raises RuntimeError when game window is not detected on Windows."""
        mock_rect.side_effect = RuntimeError("Game window not found")

        with pytest.raises(RuntimeError, match="Game window not found"):
            find_game_window()

    @patch("capture._find_window_rect_windows")
    @patch("capture.platform.system", return_value="Windows")
    def test_geometry_values_match_config(
        self, _mock_system: MagicMock, mock_rect: MagicMock,
    ) -> None:
        """Returned geometry uses GAME_WIDTH and GAME_HEIGHT from config."""
        mock_rect.return_value = _mock_window_rect()

        result = find_game_window()

        assert result["width"] == 1920
        assert result["height"] == 1080


# ---------------------------------------------------------------------------
# find_game_window — Linux path
# ---------------------------------------------------------------------------

class TestFindGameWindowLinux:
    """Tests for find_game_window() on Linux (subprocess fallback)."""

    @patch("capture.subprocess.run")
    @patch("capture.platform.system", return_value="Linux")
    def test_found_on_linux(
        self, _mock_system: MagicMock, mock_run: MagicMock,
    ) -> None:
        """Returns geometry dict when game process is detected on Linux."""
        mock_run.return_value = MagicMock(returncode=0, stdout="1234\n")

        result = find_game_window()

        assert result == {
            "left": 0,
            "top": 0,
            "width": GAME_WIDTH,
            "height": GAME_HEIGHT,
        }

    @patch("capture.subprocess.run")
    @patch("capture.platform.system", return_value="Linux")
    def test_not_found_on_linux(
        self, _mock_system: MagicMock, mock_run: MagicMock,
    ) -> None:
        """Raises RuntimeError when game process is not detected on Linux."""
        mock_run.return_value = MagicMock(returncode=1, stdout="")

        with pytest.raises(RuntimeError, match="Game window not found"):
            find_game_window()


# ---------------------------------------------------------------------------
# capture_window
# ---------------------------------------------------------------------------

class TestCaptureWindow:
    """Tests for capture_window()."""

    @patch("capture.mss.mss")
    @patch("capture.find_game_window")
    def test_returns_bgr_array(
        self, mock_find: MagicMock, mock_mss_cls: MagicMock,
    ) -> None:
        """Returns a BGR numpy array with expected shape."""
        mock_find.return_value = _mock_window_rect()
        mock_sct = MagicMock()
        mock_sct.grab.return_value = _fake_bgra_frame()
        mock_mss_cls.return_value.__enter__ = MagicMock(return_value=mock_sct)
        mock_mss_cls.return_value.__exit__ = MagicMock(return_value=False)

        frame = capture_window()

        assert frame.shape == (GAME_HEIGHT, GAME_WIDTH, 3)
        assert frame.dtype == np.uint8

    @patch("capture.mss.mss")
    @patch("capture.find_game_window")
    def test_drops_alpha_channel(
        self, mock_find: MagicMock, mock_mss_cls: MagicMock,
    ) -> None:
        """Output has 3 channels (BGR), not 4 (BGRA)."""
        mock_find.return_value = _mock_window_rect()
        # Set alpha channel to 255 so we can verify it's dropped
        bgra = _fake_bgra_frame()
        bgra[:, :, 3] = 255
        mock_sct = MagicMock()
        mock_sct.grab.return_value = bgra
        mock_mss_cls.return_value.__enter__ = MagicMock(return_value=mock_sct)
        mock_mss_cls.return_value.__exit__ = MagicMock(return_value=False)

        frame = capture_window()

        assert frame.shape[2] == 3

    @patch("capture.find_game_window")
    def test_raises_when_game_not_found(
        self, mock_find: MagicMock,
    ) -> None:
        """Raises RuntimeError when find_game_window fails."""
        mock_find.side_effect = RuntimeError("Game window not found")

        with pytest.raises(RuntimeError, match="Game window not found"):
            capture_window()

    @patch("capture.mss.mss")
    @patch("capture.find_game_window")
    def test_raises_on_wrong_dimensions(
        self, mock_find: MagicMock, mock_mss_cls: MagicMock,
    ) -> None:
        """Raises RuntimeError when captured frame has unexpected dimensions."""
        mock_find.return_value = _mock_window_rect()
        # Return a frame with wrong dimensions
        wrong_frame = np.zeros((720, 1280, 4), dtype=np.uint8)
        mock_sct = MagicMock()
        mock_sct.grab.return_value = wrong_frame
        mock_mss_cls.return_value.__enter__ = MagicMock(return_value=mock_sct)
        mock_mss_cls.return_value.__exit__ = MagicMock(return_value=False)

        with pytest.raises(RuntimeError, match="Unexpected capture dimensions"):
            capture_window()

    @patch("capture.mss.mss")
    @patch("capture.find_game_window")
    def test_passes_geometry_to_mss_grab(
        self, mock_find: MagicMock, mock_mss_cls: MagicMock,
    ) -> None:
        """Passes the full geometry dict (including offset) to mss.grab()."""
        geom = _mock_window_rect(left=200, top=100)
        mock_find.return_value = geom
        mock_sct = MagicMock()
        mock_sct.grab.return_value = _fake_bgra_frame()
        mock_mss_cls.return_value.__enter__ = MagicMock(return_value=mock_sct)
        mock_mss_cls.return_value.__exit__ = MagicMock(return_value=False)

        capture_window()

        mock_sct.grab.assert_called_once_with(geom)


# ---------------------------------------------------------------------------
# save_debug_screenshot
# ---------------------------------------------------------------------------

class TestSaveDebugScreenshot:
    """Tests for save_debug_screenshot()."""

    @patch("capture.cv2.imwrite")
    @patch("capture.capture_window")
    def test_saves_file_and_returns_path(
        self, mock_capture: MagicMock, mock_imwrite: MagicMock, tmp_path,
    ) -> None:
        """Saves a PNG to debug dir and returns the file path."""
        mock_capture.return_value = np.zeros(
            (GAME_HEIGHT, GAME_WIDTH, 3), dtype=np.uint8,
        )
        mock_imwrite.return_value = True

        with patch("capture.DEBUG_DIR", tmp_path):
            result = save_debug_screenshot("test_context")

        assert result.parent == tmp_path
        assert "test_context" in result.name
        assert result.suffix == ".png"
        mock_imwrite.assert_called_once()

    @patch("capture.cv2.imwrite")
    @patch("capture.capture_window")
    def test_filename_contains_utc_timestamp(
        self, mock_capture: MagicMock, mock_imwrite: MagicMock, tmp_path,
    ) -> None:
        """Filename includes a UTC timestamp in YYYYMMDD_HHMMSS format."""
        mock_capture.return_value = np.zeros(
            (GAME_HEIGHT, GAME_WIDTH, 3), dtype=np.uint8,
        )
        mock_imwrite.return_value = True

        with patch("capture.DEBUG_DIR", tmp_path):
            result = save_debug_screenshot("ctx")

        # Filename format: YYYYMMDD_HHMMSS_ctx.png
        stem = result.stem  # e.g. "20260220_120000_ctx"
        parts = stem.split("_")
        assert len(parts) >= 3
        assert len(parts[0]) == 8  # YYYYMMDD
        assert len(parts[1]) == 6  # HHMMSS
        assert parts[0].isdigit()
        assert parts[1].isdigit()

    @patch("capture.cv2.imwrite")
    @patch("capture.mss.mss")
    @patch("capture.capture_window")
    def test_falls_back_to_full_screen_on_game_not_found(
        self,
        mock_capture: MagicMock,
        mock_mss_cls: MagicMock,
        mock_imwrite: MagicMock,
        tmp_path,
    ) -> None:
        """Falls back to primary monitor capture when game window is unavailable."""
        mock_capture.side_effect = RuntimeError("Game not found")

        # Mock full-screen fallback
        mock_sct = MagicMock()
        mock_sct.monitors = [
            {"left": 0, "top": 0, "width": 3840, "height": 2160},  # virtual
            {"left": 0, "top": 0, "width": 1920, "height": 1080},  # primary
        ]
        mock_sct.grab.return_value = np.zeros((1080, 1920, 4), dtype=np.uint8)
        mock_mss_cls.return_value.__enter__ = MagicMock(return_value=mock_sct)
        mock_mss_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_imwrite.return_value = True

        with patch("capture.DEBUG_DIR", tmp_path):
            result = save_debug_screenshot("fallback_test")

        assert result.suffix == ".png"
        mock_imwrite.assert_called_once()

    @patch("capture.cv2.imwrite")
    @patch("capture.capture_window")
    def test_creates_debug_dir_if_missing(
        self, mock_capture: MagicMock, mock_imwrite: MagicMock, tmp_path,
    ) -> None:
        """Creates the debug directory if it does not exist."""
        debug_subdir = tmp_path / "new_debug"
        mock_capture.return_value = np.zeros(
            (GAME_HEIGHT, GAME_WIDTH, 3), dtype=np.uint8,
        )
        mock_imwrite.return_value = True

        with patch("capture.DEBUG_DIR", debug_subdir):
            save_debug_screenshot("mkdir_test")

        assert debug_subdir.exists()
