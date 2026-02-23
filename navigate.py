"""Navigation sequences and template-matching waits for the AFK Journey client.

All UI state transitions use ``wait_for_screen()`` template-matching polls.
``time.sleep()`` is only used as a 0.2 s yield inside poll loops — never as
a substitute for template matching.

This module drives ``pyautogui`` for mouse/keyboard input and delegates
screen capture to ``capture.py``.
"""

import logging
import time

import cv2
import numpy as np
import pyautogui

from capture import capture_window, find_game_window
from config import (
    CLICK_AFK_STAGES,
    CLICK_ARCANE_LABYRINTH,
    CLICK_BACK,
    CLICK_BATTLE_MODES,
    CLICK_DREAM_REALM,
    CLICK_FILTER_1_AFK_STAGES,
    CLICK_FILTER_1_ARCANE_LABYRINTH,
    CLICK_FILTER_1_DREAM_REALM,
    CLICK_FILTER_1_HONOR_DUEL,
    CLICK_FILTER_1_SUPREME_ARENA,
    CLICK_FILTER_2_AFK_STAGES,
    CLICK_FILTER_2_ARCANE_LABYRINTH,
    CLICK_FILTER_2_DREAM_REALM,
    CLICK_FILTER_2_HONOR_DUEL,
    CLICK_FILTER_2_SUPREME_ARENA,
    CLICK_GUILD,
    CLICK_GUILD_MENU,
    CLICK_HONOR_DUEL,
    CLICK_RANKING_AFK_STAGES,
    CLICK_RANKING_ARCANE_LABYRINTH,
    CLICK_RANKING_DREAM_REALM,
    CLICK_RANKING_HONOR_DUEL,
    CLICK_RANKING_SUPREME_ARENA,
    CLICK_SUPREME_ARENA,
    FRAME_STABILITY_TIMEOUT,
    NAV_HOME_CHECK_TIMEOUT,
    NAV_HOME_MAX_CLICKS,
    POLL_INTERVAL,
    STABILITY_THRESHOLD,
    TEMPLATE_BATTLE_MODES,
    TEMPLATE_DIR,
    TEMPLATE_GUILD_HALL,
    TEMPLATE_GUILD_MEMBER_LIST,
    TEMPLATE_MODE_SCREEN,
    TEMPLATE_RANKING_SCREEN,
    TEMPLATE_WORLD_SCREEN,
)

logger = logging.getLogger(__name__)


def game_click(x: int, y: int) -> None:
    """Click at game-relative coordinates, offset by the window position.

    Calls ``find_game_window()`` to determine the current window offset,
    then issues a ``pyautogui.click`` at the absolute screen position.

    Args:
        x: Horizontal position relative to the game client area.
        y: Vertical position relative to the game client area.
    """
    geometry = find_game_window()
    abs_x = x + geometry["left"]
    abs_y = y + geometry["top"]
    logger.debug("game_click(%d, %d) → absolute (%d, %d)", x, y, abs_x, abs_y)
    pyautogui.click(abs_x, abs_y)


def game_move_to(x: int, y: int) -> None:
    """Move the mouse to game-relative coordinates, offset by the window position.

    Calls ``find_game_window()`` to determine the current window offset,
    then issues a ``pyautogui.moveTo`` at the absolute screen position.

    Args:
        x: Horizontal position relative to the game client area.
        y: Vertical position relative to the game client area.
    """
    geometry = find_game_window()
    abs_x = x + geometry["left"]
    abs_y = y + geometry["top"]
    logger.debug("game_move_to(%d, %d) → absolute (%d, %d)", x, y, abs_x, abs_y)
    pyautogui.moveTo(abs_x, abs_y)


def wait_for_screen(
    template_path: str,
    timeout: float = 10.0,
    confidence: float = 0.85,
) -> None:
    """Poll until a template image is found on screen.

    Captures the game window repeatedly and runs ``cv2.matchTemplate``
    against the provided template until the match score meets or exceeds
    *confidence*, or *timeout* seconds elapse.

    Args:
        template_path: Path to the reference PNG template (1920x1080 crop).
        timeout: Maximum seconds to wait before raising.
        confidence: Minimum ``TM_CCOEFF_NORMED`` score to accept.

    Raises:
        FileNotFoundError: If the template image cannot be loaded.
        TimeoutError: If the template is not found within *timeout* seconds.
            This is fatal and triggers an abort with a debug screenshot.
    """
    start = time.time()
    template = cv2.imread(template_path)
    if template is None:
        raise FileNotFoundError(
            f"Template image not found or unreadable: {template_path}"
        )
    while time.time() - start < timeout:
        screenshot = capture_window()
        result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
        if result.max() >= confidence:
            logger.debug(
                "Template '%s' matched (score=%.3f)", template_path, result.max()
            )
            return
        time.sleep(POLL_INTERVAL)
    raise TimeoutError(f"Template '{template_path}' not found within {timeout}s")


def wait_for_stability(timeout: float = FRAME_STABILITY_TIMEOUT) -> np.ndarray:
    """Wait until two consecutive captured frames are nearly identical.

    Compares successive ``capture_window()`` frames via ``cv2.absdiff``.
    Returns the stable frame once the mean pixel difference drops below
    ``STABILITY_THRESHOLD``.

    Args:
        timeout: Maximum seconds to wait before raising.

    Returns:
        The stable BGR frame as a numpy array.

    Raises:
        TimeoutError: If frame stability is not reached within *timeout*.
    """
    start = time.time()
    prev = capture_window()
    while time.time() - start < timeout:
        time.sleep(POLL_INTERVAL)
        curr = capture_window()
        diff = cv2.absdiff(prev, curr).mean()
        if diff < STABILITY_THRESHOLD:
            logger.debug(
                "Frame stable (diff=%.3f, threshold=%.1f)",
                diff, STABILITY_THRESHOLD,
            )
            return curr
        logger.debug("Frame unstable (diff=%.3f), waiting...", diff)
        prev = curr
    raise TimeoutError(
        f"Frame stability not reached within {timeout}s "
        f"(threshold={STABILITY_THRESHOLD})"
    )


def navigate_home() -> None:
    """Navigate back to the World screen and verify arrival via template match.

    Clicks the back button up to ``NAV_HOME_MAX_CLICKS`` times, checking for
    the World screen template after each click. Raises ``TimeoutError`` if
    the World screen is never reached.

    Raises:
        TimeoutError: If the World screen template is not found after
            navigation.
    """
    template = str(TEMPLATE_DIR / TEMPLATE_WORLD_SCREEN)
    for attempt in range(NAV_HOME_MAX_CLICKS):
        try:
            wait_for_screen(template, timeout=NAV_HOME_CHECK_TIMEOUT)
            logger.info("Arrived at World screen")
            return
        except TimeoutError:
            logger.debug(
                "World screen not found (attempt %d/%d), clicking back",
                attempt + 1, NAV_HOME_MAX_CLICKS,
            )
            game_click(*CLICK_BACK)
    # Final attempt with full default timeout
    wait_for_screen(template)
    logger.info("Arrived at World screen")


def navigate_to_guild_members() -> None:
    """Navigate from the World screen to the Guild member list.

    Clicks the Guild button, waits for the Guild hall, then clicks the
    Guild menu button and waits for the member list screen.

    Raises:
        TimeoutError: If any intermediate screen template is not found.
    """
    logger.info("Navigating to Guild member list")
    game_click(*CLICK_GUILD)
    wait_for_screen(str(TEMPLATE_DIR / TEMPLATE_GUILD_HALL))
    game_click(*CLICK_GUILD_MENU)
    wait_for_screen(str(TEMPLATE_DIR / TEMPLATE_GUILD_MEMBER_LIST))
    logger.info("Arrived at Guild member list")


def _navigate_to_ranking(
    click_coords: tuple[int, int],
    ranking_click_coords: tuple[int, int],
    filter_1_coords: tuple[int, int],
    filter_2_coords: tuple[int, int],
    mode_name: str,
) -> None:
    """Navigate from World screen to a ranking screen and apply guild filter.

    Opens the Battle Modes menu, selects the specified mode, clicks the
    Ranking button on the mode's screen, waits for the ranking screen, and
    applies the guild-members-only filter.

    Args:
        click_coords: ``(x, y)`` coordinate for the specific mode button
            inside the Battle Modes menu.
        ranking_click_coords: ``(x, y)`` coordinate for the Ranking button
            on this mode's screen (differs per mode).
        filter_1_coords: ``(x, y)`` coordinate for the first filter click
            (opens filter menu) on this mode's ranking screen.
        filter_2_coords: ``(x, y)`` coordinate for the second filter click
            (selects guild option) on this mode's ranking screen.
        mode_name: Human-readable mode name for log messages.
    """
    logger.info("Navigating to %s ranking", mode_name)
    game_click(*CLICK_BATTLE_MODES)
    wait_for_screen(str(TEMPLATE_DIR / TEMPLATE_BATTLE_MODES))
    game_click(*click_coords)
    wait_for_screen(str(TEMPLATE_DIR / TEMPLATE_MODE_SCREEN))
    game_click(*ranking_click_coords)
    wait_for_screen(str(TEMPLATE_DIR / TEMPLATE_RANKING_SCREEN))
    apply_guild_filter(filter_1_coords, filter_2_coords)
    logger.info("Arrived at %s ranking with guild filter applied", mode_name)


def navigate_to_afk_stages_ranking() -> None:
    """Navigate from the World screen to the AFK Stages ranking screen.

    Goes through Battle Modes menu like all other ranking modes.
    Applies the guild-members-only filter after arriving.

    Raises:
        TimeoutError: If any intermediate screen template is not found.
    """
    _navigate_to_ranking(
        CLICK_AFK_STAGES, CLICK_RANKING_AFK_STAGES,
        CLICK_FILTER_1_AFK_STAGES, CLICK_FILTER_2_AFK_STAGES, "AFK Stages",
    )


def navigate_to_dream_realm_ranking() -> None:
    """Navigate from the World screen to the Dream Realm ranking screen.

    Applies the guild-members-only filter after arriving.

    Raises:
        TimeoutError: If any intermediate screen template is not found.
    """
    _navigate_to_ranking(
        CLICK_DREAM_REALM, CLICK_RANKING_DREAM_REALM,
        CLICK_FILTER_1_DREAM_REALM, CLICK_FILTER_2_DREAM_REALM, "Dream Realm",
    )


def navigate_to_supreme_arena_ranking() -> None:
    """Navigate from the World screen to the Supreme Arena ranking screen.

    Applies the guild-members-only filter after arriving.

    Raises:
        TimeoutError: If any intermediate screen template is not found.
    """
    _navigate_to_ranking(
        CLICK_SUPREME_ARENA, CLICK_RANKING_SUPREME_ARENA,
        CLICK_FILTER_1_SUPREME_ARENA, CLICK_FILTER_2_SUPREME_ARENA, "Supreme Arena",
    )


def navigate_to_arcane_labyrinth_ranking() -> None:
    """Navigate from the World screen to the Arcane Labyrinth ranking screen.

    Applies the guild-members-only filter after arriving.

    Raises:
        TimeoutError: If any intermediate screen template is not found.
    """
    _navigate_to_ranking(
        CLICK_ARCANE_LABYRINTH, CLICK_RANKING_ARCANE_LABYRINTH,
        CLICK_FILTER_1_ARCANE_LABYRINTH, CLICK_FILTER_2_ARCANE_LABYRINTH,
        "Arcane Labyrinth",
    )


def navigate_to_honor_duel_ranking() -> None:
    """Navigate from the World screen to the Honor Duel ranking screen.

    Applies the guild-members-only filter after arriving.

    Raises:
        TimeoutError: If any intermediate screen template is not found.
    """
    _navigate_to_ranking(
        CLICK_HONOR_DUEL, CLICK_RANKING_HONOR_DUEL,
        CLICK_FILTER_1_HONOR_DUEL, CLICK_FILTER_2_HONOR_DUEL, "Honor Duel",
    )


def apply_guild_filter(
    filter_1_coords: tuple[int, int],
    filter_2_coords: tuple[int, int],
) -> None:
    """Apply the guild-members-only filter on a ranking screen.

    Requires two clicks: the first opens the filter, the second selects
    the guild option. Waits for frame stability between clicks to ensure
    the UI has settled, then verifies the ranking screen is still visible.

    Args:
        filter_1_coords: ``(x, y)`` coordinate for opening the filter menu.
        filter_2_coords: ``(x, y)`` coordinate for selecting the guild option.

    Raises:
        TimeoutError: If the ranking screen template is not found after
            applying the filter.
    """
    logger.debug("Applying guild-members-only filter")
    game_click(*filter_1_coords)
    wait_for_stability()
    game_click(*filter_2_coords)
    wait_for_screen(str(TEMPLATE_DIR / TEMPLATE_RANKING_SCREEN))
    logger.debug("Guild filter applied")


def scroll_and_collect(
    mode: str,
    members: list[str],
) -> dict[str, str | int]:
    """Scroll through a ranking/activity list and collect data for all members.

    After each scroll step, waits for frame stability, detects player cards
    via template matching, OCRs data fields, and fuzzy-matches names against
    *members*. Stops when 30 unique names are collected or a full scroll
    yields no new names.

    Args:
        mode: One of ``"activity"``, ``"afk_stages"``, ``"dream_realm"``,
            ``"supreme_arena"``, ``"arcane_labyrinth"``, ``"honor_duel"``.
        members: Canonical member names from the Members sheet.

    Returns:
        A dict mapping canonical player names to their parsed value for this
        mode (int rank, str stage, or int activity).

    Raises:
        OCRConfidenceError: If a detected card's OCR confidence is below
            threshold.
        TimeoutError: If frame stability is not reached.
    """
    raise NotImplementedError
