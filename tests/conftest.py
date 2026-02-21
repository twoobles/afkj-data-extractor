"""Shared test configuration and fixtures.

Mocks optional modules (e.g. ``pyautogui``) that may not be installed in
the test environment so that modules which import them can still be loaded.
"""

import sys
from unittest.mock import MagicMock

# pyautogui requires a display server and may not be installed in CI / WSL.
# Insert a mock into sys.modules *before* any test imports navigate.py.
if "pyautogui" not in sys.modules:
    sys.modules["pyautogui"] = MagicMock()
