"""Auto-install a matching chromedriver so `pytest tests/bdd --headless` works
in CI without a manual ChromeDriver install (T033).

Requires an actual Chrome/Chromium browser to be present on the machine —
this only manages the driver binary, not the browser itself. See
`specs/015-create-template-python/quickstart.md` for the Chrome/Firefox
requirement (Microsoft Edge is not supported by Dash's test browser).
"""

from __future__ import annotations

import os
import shutil


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
        # PATH untouched and let dash.testing report its own clear error.
        return

    driver_dir = os.path.dirname(driver_path)
    os.environ["PATH"] = driver_dir + os.pathsep + os.environ.get("PATH", "")
