"""Auto-install a matching chromedriver so `pytest tests/bdd --headless` works
in CI without a manual ChromeDriver install (T033), and auto-skip every BDD
scenario when no real Chrome/Chromium browser is present (021 follow-up).

Requires an actual Chrome/Chromium browser to be present on the machine —
the driver-install step only manages the driver binary, not the browser
itself. See `specs/015-create-template-python/quickstart.md` for the
Chrome/Firefox requirement (Microsoft Edge is not supported by Dash's test
browser).

Why the whole suite is skipped rather than left to fail/hang: `dash_duo`
launches a real browser at fixture setup, which — with no browser binary on
the machine — either raises deep inside Selenium (`SessionNotCreatedException`,
`WebDriverException: chromedriver executable needs to be in PATH`) or hangs
waiting for a driver handshake, so a bare `pytest` run in this repo could
neither pass nor fail cleanly; it just got stuck. `pytest_collection_modifyitems`
below marks every item collected from this directory with a `skipif` that
only evaluates true when no browser can actually be found, so:
  - on a machine with Chrome/Chromium installed, these scenarios still run
    for real (nothing here permanently disables them — Principle III's
    "kept executable" still holds);
  - on a machine without one (this sandbox, and CI unless a browser step is
    added), they report SKIPPED, not FAILED and not hung, so `pytest`'s
    exit code and runtime are never held hostage by a missing browser.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

_WINDOWS_CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    r"C:\Program Files\Chromium\Application\chrome.exe",
]


def pytest_configure(config) -> None:  # noqa: ARG001
    if shutil.which("chromedriver"):
        return

    try:
        from webdriver_manager.chrome import ChromeDriverManager
    except ImportError:
        return

    try:
        driver_path = ChromeDriverManager().install()
    except Exception:  # pylint: disable=broad-except
        # No network access / no matching Chrome installed locally — leave
        # PATH untouched and let the skip logic below take over.
        return

    driver_dir = os.path.dirname(driver_path)
    os.environ["PATH"] = driver_dir + os.pathsep + os.environ.get("PATH", "")


def _chrome_browser_available() -> bool:
    """Best-effort detection of an actual Chrome/Chromium browser binary.

    Checked independently of chromedriver: a driver on PATH with no browser
    to drive still can't run a scenario, and vice versa.
    """
    for name in ("google-chrome", "chromium", "chromium-browser", "chrome"):
        if shutil.which(name):
            return True
    return any(Path(p).is_file() for p in _WINDOWS_CHROME_PATHS)


def _bdd_run_is_enabled() -> bool:
    """Both a browser binary and a driver must be available to run for real."""
    return _chrome_browser_available() and bool(shutil.which("chromedriver"))


_SKIP_REASON = (
    "BDD scenario disabled: no Chrome/Chromium browser and/or chromedriver "
    "found on this machine. dash_duo (Selenium) needs both to run a "
    "scenario; without them the test would hang or raise deep inside "
    "Selenium rather than reporting a clean pass/fail. This skip is "
    "environment-conditional, not permanent — the scenario runs normally "
    "wherever Chrome/Chromium and chromedriver are both present."
)


_THIS_DIR = Path(__file__).resolve().parent


def pytest_collection_modifyitems(config, items) -> None:  # noqa: ARG001
    """Skip only items collected from this directory (tests/bdd/) and below.

    A conftest.py hook implementation is registered for the WHOLE pytest
    session regardless of which directory defines it — `items` here is every
    test the session collected, not just this directory's. Without the path
    filter below, a bare `pytest` run would incorrectly skip tests/unit too.
    """
    if _bdd_run_is_enabled():
        return
    skip_marker = pytest.mark.skip(reason=_SKIP_REASON)
    for item in items:
        item_path = Path(str(getattr(item, "path", item.fspath)))
        if _THIS_DIR in item_path.parents:
            item.add_marker(skip_marker)
