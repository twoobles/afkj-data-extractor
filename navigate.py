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

from capture import capture_window
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
    CLICK_SUPREME_ARENA,
    FRAME_STABILITY_TIMEOUT,
    NAV_HOME_CHECK_TIMEOUT,
    NAV_HOME_MAX_CLICKS,
    POLL_INTERVAL,
    STABILITY_THRESHOLD,
    TEMPLATE_BATTLE_MODES,
    TEMPLATE_DIR,
    TEMPLATE_GUILD_ACTIVENESS,
    TEMPLATE_GUILD_MENU,
    TEMPLATE_RANKING_SCREEN,
    TEMPLATE_WORLD_SCREEN,
)

logger = logging.getLogger(__name__)


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
            pyautogui.click(*CLICK_BACK)
    # Final attempt with full default timeout
    wait_for_screen(template)
    logger.info("Arrived at World screen")


def navigate_to_guild_activeness() -> None:
    """Navigate from the World screen to the Guild Weekly Activeness view.

    Clicks the Guild button, waits for the Guild menu, then clicks the
    Weekly Activeness tab and waits for the activeness screen.

    Raises:
        TimeoutError: If any intermediate screen template is not found.
    """
    logger.info("Navigating to Guild Activeness")
    pyautogui.click(*CLICK_GUILD)
    wait_for_screen(str(TEMPLATE_DIR / TEMPLATE_GUILD_MENU))
    pyautogui.click(*CLICK_GUILD_ACTIVENESS)
    wait_for_screen(str(TEMPLATE_DIR / TEMPLATE_GUILD_ACTIVENESS))
    logger.info("Arrived at Guild Activeness screen")


def _navigate_to_ranking(
    click_coords: tuple[int, int],
    mode_name: str,
) -> None:
    """Navigate from World screen to a ranking screen and apply guild filter.

    Opens the Battle Modes menu, clicks the specified mode, waits for the
    ranking screen, and applies the guild-members-only filter.

    Args:
        click_coords: ``(x, y)`` coordinate for the specific mode button.
        mode_name: Human-readable mode name for log messages.
    """
    logger.info("Navigating to %s ranking", mode_name)
    pyautogui.click(*CLICK_BATTLE_MODES)
    wait_for_screen(str(TEMPLATE_DIR / TEMPLATE_BATTLE_MODES))
    pyautogui.click(*click_coords)
    wait_for_screen(str(TEMPLATE_DIR / TEMPLATE_RANKING_SCREEN))
    apply_guild_filter()
    logger.info("Arrived at %s ranking with guild filter applied", mode_name)


def navigate_to_afk_stages_ranking() -> None:
    """Navigate from the World screen to the AFK Stages ranking screen.

    Applies the guild-members-only filter after arriving.

    Raises:
        TimeoutError: If any intermediate screen template is not found.
    """
    _navigate_to_ranking(CLICK_AFK_STAGES, "AFK Stages")


def navigate_to_dream_realm_ranking() -> None:
    """Navigate from the World screen to the Dream Realm ranking screen.

    Applies the guild-members-only filter after arriving.

    Raises:
        TimeoutError: If any intermediate screen template is not found.
    """
    _navigate_to_ranking(CLICK_DREAM_REALM, "Dream Realm")


def navigate_to_supreme_arena_ranking() -> None:
    """Navigate from the World screen to the Supreme Arena ranking screen.

    Applies the guild-members-only filter after arriving.

    Raises:
        TimeoutError: If any intermediate screen template is not found.
    """
    _navigate_to_ranking(CLICK_SUPREME_ARENA, "Supreme Arena")


def navigate_to_arcane_labyrinth_ranking() -> None:
    """Navigate from the World screen to the Arcane Labyrinth ranking screen.

    Applies the guild-members-only filter after arriving.

    Raises:
        TimeoutError: If any intermediate screen template is not found.
    """
    _navigate_to_ranking(CLICK_ARCANE_LABYRINTH, "Arcane Labyrinth")


def navigate_to_honor_duel_ranking() -> None:
    """Navigate from the World screen to the Honor Duel ranking screen.

    Applies the guild-members-only filter after arriving.

    Raises:
        TimeoutError: If any intermediate screen template is not found.
    """
    _navigate_to_ranking(CLICK_HONOR_DUEL, "Honor Duel")


def apply_guild_filter() -> None:
    """Toggle the guild-members-only filter on a ranking screen.

    Clicks the guild filter button and re-verifies the ranking screen
    template is still visible (confirming we didn't navigate away).

    Raises:
        TimeoutError: If the ranking screen template is not found after
            clicking the filter.
    """
    logger.debug("Applying guild-members-only filter")
    pyautogui.click(*CLICK_GUILD_FILTER)
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
