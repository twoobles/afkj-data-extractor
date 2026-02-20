"""Entry point and pipeline orchestration for the AFK Journey guild scraper.

Executes the full run sequence:
1. Startup — load Members list, duplicate-date guard, validate Sheets auth.
2. Verify World screen — template match before any navigation.
3. Scrape all modes — collect all data in memory (no Sheets writes).
4. Export — append one fully populated row per player.

All errors are fatal. On failure, a timestamped debug screenshot is saved
and the process exits with a non-zero code.
"""

import logging

logger = logging.getLogger(__name__)


def main() -> None:
    """Run the full scrape-and-export pipeline.

    Orchestrates startup checks, navigation through all six game modes,
    data collection, and final export to Google Sheets. Never interleaves
    navigation and writes — all data is collected in memory first, then
    written in a single pass.

    Raises:
        SystemExit: On any fatal error, after saving a debug screenshot
            and logging the full traceback.
    """
    raise NotImplementedError


if __name__ == "__main__":
    main()
