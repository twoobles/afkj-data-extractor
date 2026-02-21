"""Tests for navigate.py — navigation sequences and template matching."""

from unittest.mock import MagicMock, call, patch

import numpy as np
import pytest

from config import (
    CLICK_AFK_STAGES,
    CLICK_ARCANE_LABYRINTH,
    CLICK_BACK,
    CLICK_BATTLE_MODES,
    CLICK_DREAM_REALM,
    CLICK_GUILD,
    CLICK_GUILD_ACTIVENESS,
    CLICK_GUILD_FILTER,
    CLICK_HONOR_DUEL,
    CLICK_RANKING,
    CLICK_SUPREME_ARENA,
    NAV_HOME_CHECK_TIMEOUT,
    NAV_HOME_MAX_CLICKS,
    POLL_INTERVAL,
    STABILITY_THRESHOLD,
    TEMPLATE_AFK_STAGES_MENU,
    TEMPLATE_BATTLE_MODES,
    TEMPLATE_DIR,
    TEMPLATE_GUILD_ACTIVENESS,
    TEMPLATE_GUILD_MENU,
    TEMPLATE_MODE_SCREEN,
    TEMPLATE_RANKING_SCREEN,
    TEMPLATE_WORLD_SCREEN,
)


# ---------------------------------------------------------------------------
# TestWaitForScreen
# ---------------------------------------------------------------------------

class TestWaitForScreen:
    """Tests for the wait_for_screen() template-polling function."""

    @patch("navigate.time.sleep")
    @patch("navigate.time.time")
    @patch("navigate.cv2.matchTemplate")
    @patch("navigate.cv2.imread")
    @patch("navigate.capture_window")
    def test_returns_immediately_on_first_match(
        self, mock_capture, mock_imread, mock_match, mock_time, mock_sleep
    ):
        """Should return without sleeping when the first poll matches."""
        mock_imread.return_value = np.zeros((50, 50, 3), dtype=np.uint8)
        mock_capture.return_value = np.zeros((1080, 1920, 3), dtype=np.uint8)
        # start=0.0, loop check=0.1
        mock_time.side_effect = [0.0, 0.1]
        result = MagicMock()
        result.max.return_value = 0.95
        mock_match.return_value = result

        from navigate import wait_for_screen
        wait_for_screen("template.png")

        mock_capture.assert_called_once()
        mock_sleep.assert_not_called()

    @patch("navigate.time.sleep")
    @patch("navigate.time.time")
    @patch("navigate.cv2.matchTemplate")
    @patch("navigate.cv2.imread")
    @patch("navigate.capture_window")
    def test_polls_until_match(
        self, mock_capture, mock_imread, mock_match, mock_time, mock_sleep
    ):
        """Should keep polling and sleeping until the template is found."""
        mock_imread.return_value = np.zeros((50, 50, 3), dtype=np.uint8)
        mock_capture.return_value = np.zeros((1080, 1920, 3), dtype=np.uint8)
        # start=0.0, then 3 loop checks
        mock_time.side_effect = [0.0, 0.3, 0.6, 0.9]

        fail_result = MagicMock()
        fail_result.max.return_value = 0.5
        pass_result = MagicMock()
        pass_result.max.return_value = 0.90
        mock_match.side_effect = [fail_result, fail_result, pass_result]

        from navigate import wait_for_screen
        wait_for_screen("template.png", timeout=10.0)

        assert mock_capture.call_count == 3
        assert mock_sleep.call_count == 2
        mock_sleep.assert_called_with(POLL_INTERVAL)

    @patch("navigate.time.sleep")
    @patch("navigate.time.time")
    @patch("navigate.cv2.matchTemplate")
    @patch("navigate.cv2.imread")
    @patch("navigate.capture_window")
    def test_raises_timeout_when_no_match(
        self, mock_capture, mock_imread, mock_match, mock_time, mock_sleep
    ):
        """Should raise TimeoutError after timeout elapses without a match."""
        mock_imread.return_value = np.zeros((50, 50, 3), dtype=np.uint8)
        mock_capture.return_value = np.zeros((1080, 1920, 3), dtype=np.uint8)
        # start=0.0, one loop at 5.0, then 11.0 exceeds 10s timeout
        mock_time.side_effect = [0.0, 5.0, 11.0]

        fail_result = MagicMock()
        fail_result.max.return_value = 0.3
        mock_match.return_value = fail_result

        from navigate import wait_for_screen
        with pytest.raises(TimeoutError, match="not found within 10.0s"):
            wait_for_screen("template.png", timeout=10.0)

    @patch("navigate.time.sleep")
    @patch("navigate.time.time")
    @patch("navigate.cv2.imread")
    @patch("navigate.capture_window")
    def test_raises_file_not_found_for_missing_template(
        self, mock_capture, mock_imread, mock_time, mock_sleep
    ):
        """Should raise FileNotFoundError when cv2.imread returns None."""
        mock_imread.return_value = None
        mock_time.side_effect = [0.0]

        from navigate import wait_for_screen
        with pytest.raises(FileNotFoundError, match="not found or unreadable"):
            wait_for_screen("nonexistent.png")

    @patch("navigate.time.sleep")
    @patch("navigate.time.time")
    @patch("navigate.cv2.matchTemplate")
    @patch("navigate.cv2.imread")
    @patch("navigate.capture_window")
    def test_uses_custom_confidence(
        self, mock_capture, mock_imread, mock_match, mock_time, mock_sleep
    ):
        """Should respect a custom confidence threshold."""
        mock_imread.return_value = np.zeros((50, 50, 3), dtype=np.uint8)
        mock_capture.return_value = np.zeros((1080, 1920, 3), dtype=np.uint8)
        mock_time.side_effect = [0.0, 0.1]

        result = MagicMock()
        # 0.80 is below default 0.85 but above custom 0.70
        result.max.return_value = 0.80
        mock_match.return_value = result

        from navigate import wait_for_screen
        wait_for_screen("template.png", confidence=0.70)

        mock_capture.assert_called_once()

    @patch("navigate.time.sleep")
    @patch("navigate.time.time")
    @patch("navigate.cv2.matchTemplate")
    @patch("navigate.cv2.imread")
    @patch("navigate.capture_window")
    def test_uses_tm_ccoeff_normed(
        self, mock_capture, mock_imread, mock_match, mock_time, mock_sleep
    ):
        """Should call cv2.matchTemplate with TM_CCOEFF_NORMED method."""
        import cv2

        mock_imread.return_value = np.zeros((50, 50, 3), dtype=np.uint8)
        mock_capture.return_value = np.zeros((1080, 1920, 3), dtype=np.uint8)
        mock_time.side_effect = [0.0, 0.1]

        result = MagicMock()
        result.max.return_value = 0.95
        mock_match.return_value = result

        from navigate import wait_for_screen
        wait_for_screen("template.png")

        mock_match.assert_called_once()
        assert mock_match.call_args[0][2] == cv2.TM_CCOEFF_NORMED


# ---------------------------------------------------------------------------
# TestWaitForStability
# ---------------------------------------------------------------------------

class TestWaitForStability:
    """Tests for the wait_for_stability() frame-comparison function."""

    @patch("navigate.time.sleep")
    @patch("navigate.time.time")
    @patch("navigate.capture_window")
    def test_returns_stable_frame_on_identical_captures(
        self, mock_capture, mock_time, mock_sleep
    ):
        """Should return when consecutive frames are identical (diff=0)."""
        frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
        mock_capture.return_value = frame
        # start=0.0, one loop iteration at 0.3
        mock_time.side_effect = [0.0, 0.3]

        from navigate import wait_for_stability
        result = wait_for_stability()

        assert result.shape == (1080, 1920, 3)
        mock_sleep.assert_called_once_with(POLL_INTERVAL)

    @patch("navigate.time.sleep")
    @patch("navigate.time.time")
    @patch("navigate.capture_window")
    def test_waits_until_frames_converge(
        self, mock_capture, mock_time, mock_sleep
    ):
        """Should keep polling until frame diff drops below threshold."""
        frame_a = np.zeros((1080, 1920, 3), dtype=np.uint8)
        frame_b = np.full((1080, 1920, 3), 100, dtype=np.uint8)
        frame_c = np.zeros((1080, 1920, 3), dtype=np.uint8)

        # Initial capture returns frame_a, then b (unstable), c (unstable
        # relative to b), c again (stable relative to c)
        mock_capture.side_effect = [frame_a, frame_b, frame_c, frame_c]
        mock_time.side_effect = [0.0, 0.3, 0.6, 0.9]

        from navigate import wait_for_stability
        result = wait_for_stability()

        assert mock_sleep.call_count == 3
        assert result.shape == (1080, 1920, 3)

    @patch("navigate.time.sleep")
    @patch("navigate.time.time")
    @patch("navigate.capture_window")
    def test_raises_timeout_on_persistent_instability(
        self, mock_capture, mock_time, mock_sleep
    ):
        """Should raise TimeoutError if frames never stabilize."""
        frame_a = np.zeros((1080, 1920, 3), dtype=np.uint8)
        frame_b = np.full((1080, 1920, 3), 200, dtype=np.uint8)
        mock_capture.side_effect = [frame_a, frame_b, frame_a]
        # start=0.0, loop at 2.0, then 6.0 exceeds 5.0 timeout
        mock_time.side_effect = [0.0, 2.0, 6.0]

        from navigate import wait_for_stability
        with pytest.raises(TimeoutError, match="Frame stability not reached"):
            wait_for_stability(timeout=5.0)

    @patch("navigate.time.sleep")
    @patch("navigate.time.time")
    @patch("navigate.capture_window")
    def test_respects_stability_threshold(
        self, mock_capture, mock_time, mock_sleep
    ):
        """Frames with diff below STABILITY_THRESHOLD should count as stable."""
        frame_a = np.zeros((100, 100, 3), dtype=np.uint8)
        frame_b = frame_a.copy()
        # Tiny diff: ~0.5 mean, well below STABILITY_THRESHOLD (2.0)
        frame_b[:50, :, :] = 1

        mock_capture.side_effect = [frame_a, frame_b]
        mock_time.side_effect = [0.0, 0.3]

        from navigate import wait_for_stability
        result = wait_for_stability()

        assert result is frame_b


# ---------------------------------------------------------------------------
# TestNavigateHome
# ---------------------------------------------------------------------------

class TestNavigateHome:
    """Tests for navigate_home()."""

    @patch("navigate.pyautogui.click")
    @patch("navigate.wait_for_screen")
    def test_returns_when_already_on_world_screen(self, mock_wait, mock_click):
        """Should return without clicking back if World screen is found."""
        from navigate import navigate_home
        navigate_home()

        mock_wait.assert_called_once_with(
            str(TEMPLATE_DIR / TEMPLATE_WORLD_SCREEN),
            timeout=NAV_HOME_CHECK_TIMEOUT,
        )
        mock_click.assert_not_called()

    @patch("navigate.pyautogui.click")
    @patch("navigate.wait_for_screen")
    def test_clicks_back_once_on_single_timeout(self, mock_wait, mock_click):
        """Should click back and retry when first check times out."""
        mock_wait.side_effect = [TimeoutError("test"), None]

        from navigate import navigate_home
        navigate_home()

        mock_click.assert_called_once_with(*CLICK_BACK)
        assert mock_wait.call_count == 2

    @patch("navigate.pyautogui.click")
    @patch("navigate.wait_for_screen")
    def test_retries_up_to_max_clicks(self, mock_wait, mock_click):
        """Should click back NAV_HOME_MAX_CLICKS times before final attempt."""
        # All loop attempts fail, final attempt succeeds
        mock_wait.side_effect = (
            [TimeoutError("test")] * NAV_HOME_MAX_CLICKS + [None]
        )

        from navigate import navigate_home
        navigate_home()

        assert mock_click.call_count == NAV_HOME_MAX_CLICKS
        assert mock_wait.call_count == NAV_HOME_MAX_CLICKS + 1

    @patch("navigate.pyautogui.click")
    @patch("navigate.wait_for_screen")
    def test_raises_if_all_attempts_fail(self, mock_wait, mock_click):
        """Should propagate TimeoutError if world screen is never found."""
        mock_wait.side_effect = TimeoutError("world screen not found")

        from navigate import navigate_home
        with pytest.raises(TimeoutError):
            navigate_home()

        assert mock_click.call_count == NAV_HOME_MAX_CLICKS


# ---------------------------------------------------------------------------
# TestNavigateToGuildActiveness
# ---------------------------------------------------------------------------

class TestNavigateToGuildActiveness:
    """Tests for navigate_to_guild_activeness()."""

    @patch("navigate.pyautogui.click")
    @patch("navigate.wait_for_screen")
    def test_click_sequence_and_template_waits(self, mock_wait, mock_click):
        """Should click Guild → wait guild menu → click Activeness → wait."""
        from navigate import navigate_to_guild_activeness
        navigate_to_guild_activeness()

        expected_clicks = [
            call(*CLICK_GUILD),
            call(*CLICK_GUILD_ACTIVENESS),
        ]
        assert mock_click.call_args_list == expected_clicks

        expected_waits = [
            call(str(TEMPLATE_DIR / TEMPLATE_GUILD_MENU)),
            call(str(TEMPLATE_DIR / TEMPLATE_GUILD_ACTIVENESS)),
        ]
        assert mock_wait.call_args_list == expected_waits

    @patch("navigate.pyautogui.click")
    @patch("navigate.wait_for_screen")
    def test_propagates_timeout_from_guild_menu(self, mock_wait, mock_click):
        """Should propagate TimeoutError if Guild menu is not found."""
        mock_wait.side_effect = TimeoutError("guild menu not found")

        from navigate import navigate_to_guild_activeness
        with pytest.raises(TimeoutError):
            navigate_to_guild_activeness()


# ---------------------------------------------------------------------------
# TestNavigateToAfkStagesRanking
# ---------------------------------------------------------------------------

class TestNavigateToAfkStagesRanking:
    """Tests for navigate_to_afk_stages_ranking() — direct from World."""

    @patch("navigate.pyautogui.click")
    @patch("navigate.wait_for_screen")
    def test_navigates_directly_not_via_battle_modes(
        self, mock_wait, mock_click
    ):
        """Should go World → AFK Stages menu → Ranking → filter."""
        from navigate import navigate_to_afk_stages_ranking
        navigate_to_afk_stages_ranking()

        expected_clicks = [
            call(*CLICK_AFK_STAGES),
            call(*CLICK_RANKING),
            call(*CLICK_GUILD_FILTER),
        ]
        assert mock_click.call_args_list == expected_clicks

        expected_waits = [
            call(str(TEMPLATE_DIR / TEMPLATE_AFK_STAGES_MENU)),
            call(str(TEMPLATE_DIR / TEMPLATE_RANKING_SCREEN)),
            call(str(TEMPLATE_DIR / TEMPLATE_RANKING_SCREEN)),  # filter re-verify
        ]
        assert mock_wait.call_args_list == expected_waits



# ---------------------------------------------------------------------------
# TestNavigateToRanking (parameterized for Battle Modes: DR, SA, AL, HD)
# ---------------------------------------------------------------------------

class TestNavigateToRanking:
    """Tests for the four Battle Modes ranking navigation functions."""

    @pytest.mark.parametrize(
        "navigate_func_name,click_coords",
        [
            ("navigate_to_dream_realm_ranking", CLICK_DREAM_REALM),
            ("navigate_to_supreme_arena_ranking", CLICK_SUPREME_ARENA),
            ("navigate_to_arcane_labyrinth_ranking", CLICK_ARCANE_LABYRINTH),
            ("navigate_to_honor_duel_ranking", CLICK_HONOR_DUEL),
        ],
    )
    @patch("navigate.pyautogui.click")
    @patch("navigate.wait_for_screen")
    def test_navigates_via_battle_modes_with_ranking_click(
        self, mock_wait, mock_click, navigate_func_name, click_coords
    ):
        """Battle Modes → mode → mode screen → Ranking → filter."""
        import navigate
        navigate_func = getattr(navigate, navigate_func_name)
        navigate_func()

        expected_clicks = [
            call(*CLICK_BATTLE_MODES),
            call(*click_coords),
            call(*CLICK_RANKING),
            call(*CLICK_GUILD_FILTER),
        ]
        assert mock_click.call_args_list == expected_clicks

        expected_waits = [
            call(str(TEMPLATE_DIR / TEMPLATE_BATTLE_MODES)),
            call(str(TEMPLATE_DIR / TEMPLATE_MODE_SCREEN)),
            call(str(TEMPLATE_DIR / TEMPLATE_RANKING_SCREEN)),
            call(str(TEMPLATE_DIR / TEMPLATE_RANKING_SCREEN)),  # filter re-verify
        ]
        assert mock_wait.call_args_list == expected_waits

    @patch("navigate.pyautogui.click")
    @patch("navigate.wait_for_screen")
    def test_propagates_timeout_from_battle_modes(self, mock_wait, mock_click):
        """Should propagate TimeoutError if Battle Modes menu is not found."""
        mock_wait.side_effect = TimeoutError("battle modes not found")

        from navigate import navigate_to_dream_realm_ranking
        with pytest.raises(TimeoutError):
            navigate_to_dream_realm_ranking()


# ---------------------------------------------------------------------------
# TestApplyGuildFilter
# ---------------------------------------------------------------------------

class TestApplyGuildFilter:
    """Tests for apply_guild_filter()."""

    @patch("navigate.pyautogui.click")
    @patch("navigate.wait_for_screen")
    def test_clicks_filter_and_verifies_ranking_screen(
        self, mock_wait, mock_click
    ):
        """Should click the guild filter and re-verify the ranking screen."""
        from navigate import apply_guild_filter
        apply_guild_filter()

        mock_click.assert_called_once_with(*CLICK_GUILD_FILTER)
        mock_wait.assert_called_once_with(
            str(TEMPLATE_DIR / TEMPLATE_RANKING_SCREEN)
        )

    @patch("navigate.pyautogui.click")
    @patch("navigate.wait_for_screen")
    def test_propagates_timeout_after_filter(self, mock_wait, mock_click):
        """Should propagate TimeoutError if ranking screen lost after filter."""
        mock_wait.side_effect = TimeoutError("ranking screen lost")

        from navigate import apply_guild_filter
        with pytest.raises(TimeoutError):
            apply_guild_filter()
