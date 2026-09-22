"""Guards against silently-dropped Dash callback registrations.

Dash makes an `allow_duplicate=True` Output unique by hashing **only the
callback's Inputs** (`dash/_utils.py::create_callback_id`). Two pages that
declare the same Output *and* the same Inputs therefore produce the identical
callback id, and the second registration silently overwrites the first in
`dash._callback.GLOBAL_CALLBACK_MAP` — no warning, no error. The page imported
last simply wins, and the other pages' handlers never run.

That is exactly how the Performance page's "ITD" shortcut came to apply
Positions' year-to-date mapping instead of its own inception-to-date one: three
pages share the five `overview-shortcut-*` buttons as Inputs and both shared
date pickers as Outputs. Only a browser-driven test would otherwise notice, and
the BDD suite that covers shortcuts needs Chrome.

This test needs no browser: it instruments the registry during a fresh app
import and asserts nothing is overwritten.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Run in a subprocess: `import app` mutates Dash's module-level globals
# (GLOBAL_CALLBACK_MAP, the page registry), so the registry can only be
# observed from *before* the first import — impossible in-process once any
# other test has imported the app.
_PROBE = """
import inspect, json, sys
import dash._callback as _callback


class TrackingMap(dict):
    def __init__(self):
        super().__init__()
        self.collisions = []

    def __setitem__(self, key, value):
        if key in self:
            self.collisions.append((key, _registering_module()))
        super().__setitem__(key, value)


def _registering_module():
    for frame in inspect.stack():
        path = frame.filename.replace("\\\\", "/")
        if "/src/pages/" in path:
            return path.split("/src/pages/")[1]
        if path.endswith("/app.py"):
            return "app.py"
    return "<unknown>"


tracking = TrackingMap()
_callback.GLOBAL_CALLBACK_MAP = tracking

import app  # noqa: E402,F401  -- triggers page + callback registration

print(
    json.dumps(
        {
            "registered": len(tracking),
            "collisions": [
                {"callback_id": key, "overwritten_by": module}
                for key, module in tracking.collisions
            ],
        }
    )
)
"""


def _probe_registry() -> dict:
    """Import the app in a subprocess and report any overwritten callback ids."""
    result = subprocess.run(
        [sys.executable, "-c", _PROBE],
        cwd=str(_PROJECT_ROOT),
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, f"probe failed:\n{result.stdout}\n{result.stderr}"
    # The app logs structured JSON to stdout on import; the probe's own payload
    # is the last line.
    payload = [line for line in result.stdout.strip().splitlines() if line.startswith("{")][-1]
    return json.loads(payload)


def test_no_callback_is_silently_overwritten():
    """Every registered callback must survive startup with a unique id.

    A collision here means one page's handler is dead: the Output/Input pair it
    declares is identical to another page's, so whichever page Dash imports last
    owns the behaviour for every page that shares those controls.
    """
    report = _probe_registry()
    collisions = report["collisions"]

    detail = "\n".join(
        f"  - {c['callback_id'][:90]}\n      overwritten by {c['overwritten_by']}"
        for c in collisions
    )
    assert not collisions, (
        f"{len(collisions)} callback registration(s) silently overwritten during startup "
        f"({report['registered']} survived). Give each page's callback a page-local Input "
        f"so its id is unique, and add allow_duplicate=True to any shared Output:\n{detail}"
    )
