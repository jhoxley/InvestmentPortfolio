"""Unit tests for src/pages/_var_controls.py's pure build_controls() (026-var-risk-view)."""

from __future__ import annotations

from dash import html

from src.models.portfolio_analysis import MethodLookback, VarMethodsResponse
from src.pages._var_controls import build_controls

_METHODS = VarMethodsResponse(
    method="historical-simulation",
    methodology_version="1.0.0",
    lookbacks=[
        MethodLookback(code="1y", business_days=260, is_headline=False),
        MethodLookback(code="2y", business_days=520, is_headline=True),
        MethodLookback(code="5y", business_days=1300, is_headline=False),
    ],
    confidence_levels_bp=[9500, 9750, 9900],
    measures=[],
    _links={"self": "/v1/risk/var/methods"},
)


def _find(component: object, component_id: str) -> object | None:
    """Depth-first search a Dash component tree for a component with the given id."""
    if getattr(component, "id", None) == component_id:
        return component
    children = getattr(component, "children", None)
    if children is None:
        return None
    if not isinstance(children, list):
        children = [children]
    for child in children:
        found = _find(child, component_id)
        if found is not None:
            return found
    return None


def test_none_methods_renders_a_placeholder_with_no_controls() -> None:
    block = build_controls(None)
    assert isinstance(block, html.Div)
    assert _find(block, "risk-var-confidence") is None
    assert _find(block, "risk-var-lookback") is None


def test_confidence_control_options_are_percentages_values_are_basis_points() -> None:
    block = build_controls(_METHODS)
    confidence = _find(block, "risk-var-confidence")
    assert confidence is not None
    options = confidence.options  # type: ignore[attr-defined]
    by_value = {opt["value"]: opt["label"] for opt in options}
    assert by_value == {9500: "95%", 9750: "97.5%", 9900: "99%"}


def test_confidence_control_defaults_to_every_level_selected() -> None:
    block = build_controls(_METHODS)
    confidence = _find(block, "risk-var-confidence")
    assert confidence.value == [9500, 9750, 9900]  # type: ignore[attr-defined]


def test_no_lookback_control_is_rendered() -> None:
    """027 FR-007: the Look-back dropdown is removed -- the page's single shared range
    control (shortcut buttons + a new page-local "2Y" button) drives the look-back
    instead (see research.md #5 in specs/027-risk-page-cleanup).
    """
    block = build_controls(_METHODS)
    assert _find(block, "risk-var-lookback") is None


def test_units_toggle_defaults_to_money() -> None:
    block = build_controls(_METHODS)
    units = _find(block, "risk-var-units")
    assert units is not None
    assert units.value == "gbp"  # type: ignore[attr-defined]


def test_pnl_basis_toggle_defaults_to_hypothetical() -> None:
    block = build_controls(_METHODS)
    pnl_basis = _find(block, "risk-var-pnl-basis")
    assert pnl_basis is not None
    assert pnl_basis.value == "hypothetical"  # type: ignore[attr-defined]


def test_hide_degraded_toggle_defaults_off() -> None:
    block = build_controls(_METHODS)
    toggle = _find(block, "risk-var-hide-degraded")
    assert toggle is not None
    assert toggle.value is False  # type: ignore[attr-defined]


def test_show_es_toggle_defaults_off() -> None:
    block = build_controls(_METHODS)
    toggle = _find(block, "risk-var-show-es")
    assert toggle is not None
    assert toggle.value is False  # type: ignore[attr-defined]
