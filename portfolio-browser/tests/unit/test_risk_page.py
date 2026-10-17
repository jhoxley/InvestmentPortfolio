"""Unit tests for src/pages/risk.py's plain-function callback logic (024).

`app` is imported first, before `src.pages.risk` — `dash.register_page()`
inside risk.py requires the Dash app to already exist
(`Dash(use_pages=True, ...)`), mirroring every BDD steps module's own import
order (e.g. tests/bdd/steps/test_performance_steps.py).
"""

from __future__ import annotations

from typing import Any

import dash_bootstrap_components as dbc
import pytest
from dash.exceptions import PreventUpdate

import app as app_module  # noqa: F401
import src.pages.risk as risk_module


def _walk(component: Any) -> Any:
    """Yield `component` and every descendant in its `children` tree (027)."""
    yield component
    children = getattr(component, "children", None)
    if children is None:
        return
    if isinstance(children, (list, tuple)):
        for child in children:
            yield from _walk(child)
    else:
        yield from _walk(children)


def test_layout_has_no_tabs_component() -> None:
    """The merged single-page layout MUST NOT use dbc.Tabs/dbc.Tab (FR-001)."""
    nodes = list(_walk(risk_module.layout))
    assert not any(isinstance(node, dbc.Tabs) for node in nodes)
    assert not any(isinstance(node, dbc.Tab) for node in nodes)


def test_layout_shows_histogram_before_var_section() -> None:
    """The histogram section MUST appear before the Value at Risk section (FR-002)."""
    nodes = list(_walk(risk_module.layout))
    ids = [getattr(node, "id", None) for node in nodes]
    histogram_index = ids.index("risk-chart-container")
    var_index = ids.index("risk-var-controls-container")
    assert histogram_index < var_index


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
