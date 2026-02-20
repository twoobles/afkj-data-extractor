"""Google Sheets export logic via gspread.

Handles service-account authentication, reading the Members list, duplicate-
date checking, player tab lookup, and row appending. All writes use
``value_input_option="USER_ENTERED"`` so that ``"#N/A"`` is stored as a
native Sheets error.
"""

import logging
from typing import Optional

import gspread

logger = logging.getLogger(__name__)


def get_sheets_client() -> gspread.Client:
    """Authenticate with Google Sheets using the service account key.

    The key path is read from ``config.SERVICE_ACCOUNT_KEY_PATH``.

    Returns:
        An authorized ``gspread.Client``.

    Raises:
        FileNotFoundError: If the service account key file does not exist.
        google.auth.exceptions.DefaultCredentialsError: If the key is invalid.
    """
    raise NotImplementedError


def load_member_names(client: gspread.Client) -> list[str]:
    """Read canonical player names from the Members tab.

    Reads column B, rows 2-31 from the "Members" tab as configured in
    ``config.py``.

    Args:
        client: An authorized gspread client.

    Returns:
        A list of up to 30 player name strings.

    Raises:
        gspread.exceptions.SpreadsheetNotFound: If the spreadsheet ID is
            invalid.
        gspread.exceptions.WorksheetNotFound: If the Members tab does not
            exist.
    """
    raise NotImplementedError


def get_last_date(worksheet: gspread.Worksheet) -> Optional[str]:
    """Read the last populated date value from column A of a player tab.

    Used by the duplicate-run guard at startup to check whether today's
    date has already been written.

    Args:
        worksheet: A gspread Worksheet for a single player tab.

    Returns:
        The last non-empty value in column A as a string, or ``None`` if
        the column is empty (no data rows yet).
    """
    raise NotImplementedError


def get_player_sheet(
    spreadsheet: gspread.Spreadsheet,
    player_name: str,
) -> gspread.Worksheet:
    """Look up a player's tab by exact name match.

    Args:
        spreadsheet: The gspread Spreadsheet object.
        player_name: The canonical player name (case-sensitive).

    Returns:
        The matching ``gspread.Worksheet``.

    Raises:
        ValueError: If no tab with the exact name *player_name* exists.
            The scraper does not create tabs — this is fatal.
    """
    raise NotImplementedError


def append_player_row(
    worksheet: gspread.Worksheet,
    row_data: dict[str, str],
) -> None:
    """Append a single data row to a player tab.

    Builds the row list in ``config.COLUMN_ORDER`` order and appends it
    with ``value_input_option="USER_ENTERED"`` so ``"#N/A"`` becomes a
    native Sheets error.

    Args:
        worksheet: The player's gspread Worksheet.
        row_data: A dict mapping column names (from ``config.COLUMN_ORDER``)
            to their string values.

    Raises:
        KeyError: If *row_data* is missing any key from
            ``config.COLUMN_ORDER``.
    """
    raise NotImplementedError
