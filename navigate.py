"""Navigation sequences and template-matching waits for the AFK Journey client.

All UI state transitions use ``wait_for_screen()`` template-matching polls.
``time.sleep()`` is only used as a 0.2 s yield inside poll loops — never as
a substitute for template matching.

This module drives ``pyautogui`` for mouse/keyboard input and delegates
screen capture to ``capture.py``.
"""

import logging

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
        TimeoutError: If the template is not found within *timeout* seconds.
            This is fatal and triggers an abort with a debug screenshot.
    """
    raise NotImplementedError


def navigate_home() -> None:
    """Navigate back to the World screen and verify arrival via template match.

    Raises:
        TimeoutError: If the World screen template is not found after
            navigation.
    """
    raise NotImplementedError


def navigate_to_guild_activeness() -> None:
    """Navigate from the World screen to the Guild Weekly Activeness view.

    Raises:
        TimeoutError: If any intermediate screen template is not found.
    """
    raise NotImplementedError


def navigate_to_afk_stages_ranking() -> None:
    """Navigate from the World screen to the AFK Stages ranking screen.

    Applies the guild-members-only filter after arriving.

    Raises:
        TimeoutError: If any intermediate screen template is not found.
    """
    raise NotImplementedError


def navigate_to_dream_realm_ranking() -> None:
    """Navigate from the World screen to the Dream Realm ranking screen.

    Applies the guild-members-only filter after arriving.

    Raises:
        TimeoutError: If any intermediate screen template is not found.
    """
    raise NotImplementedError


def navigate_to_supreme_arena_ranking() -> None:
    """Navigate from the World screen to the Supreme Arena ranking screen.

    Applies the guild-members-only filter after arriving.

    Raises:
        TimeoutError: If any intermediate screen template is not found.
    """
    raise NotImplementedError


def navigate_to_arcane_labyrinth_ranking() -> None:
    """Navigate from the World screen to the Arcane Labyrinth ranking screen.

    Applies the guild-members-only filter after arriving.

    Raises:
        TimeoutError: If any intermediate screen template is not found.
    """
    raise NotImplementedError


def navigate_to_honor_duel_ranking() -> None:
    """Navigate from the World screen to the Honor Duel ranking screen.

    Applies the guild-members-only filter after arriving.

    Raises:
        TimeoutError: If any intermediate screen template is not found.
    """
    raise NotImplementedError


def apply_guild_filter() -> None:
    """Toggle the guild-members-only filter on a ranking screen.

    Raises:
        TimeoutError: If the filter confirmation template is not found.
    """
    raise NotImplementedError


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
