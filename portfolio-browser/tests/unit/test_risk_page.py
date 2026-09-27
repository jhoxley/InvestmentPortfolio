"""Unit tests for src/pages/risk.py's plain-function callback logic (024).

`app` is imported first, before `src.pages.risk` — `dash.register_page()`
inside risk.py requires the Dash app to already exist
(`Dash(use_pages=True, ...)`), mirroring every BDD steps module's own import
order (e.g. tests/bdd/steps/test_performance_steps.py).
"""

from __future__ import annotations

import pytest
from dash.exceptions import PreventUpdate

import app as app_module  # noqa: F401
import src.pages.risk as risk_module


def test_validate_date_range_rejects_end_not_after_start() -> None:
    message = risk_module._validate_date_range("2024-06-28", "2024-01-02", 1)
    assert message == "The end date must be after the start date."


def test_validate_date_range_rejects_equal_dates() -> None:
    message = risk_module._validate_date_range("2024-01-02", "2024-01-02", 1)
    assert message == "The end date must be after the start date."


def test_validate_date_range_accepts_end_after_start() -> None:
    message = risk_module._validate_date_range("2024-01-02", "2024-06-28", 1)
    assert message == ""


def test_validate_date_range_prevents_update_with_missing_dates() -> None:
    with pytest.raises(PreventUpdate):
        risk_module._validate_date_range(None, "2024-06-28", 1)
    with pytest.raises(PreventUpdate):
        risk_module._validate_date_range("2024-01-02", None, 1)
