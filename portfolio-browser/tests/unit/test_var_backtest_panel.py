"""Unit tests for src/pages/_var_backtest_panel.py's pure build_panel() (026, US2)."""

from __future__ import annotations

from dash import html

from src.pages._var_backtest_panel import build_panel


def _level(confidence_bp: int = 9500, observation_count: int = 250, **overrides: object) -> dict:
    base = {
        "confidence_bp": confidence_bp,
        "observation_count": observation_count,
        "exception_count": 6,
        "expected_exceptions": 12.5,
        "exception_rate": 0.024,
        "kupiec_lr": 1.2,
        "kupiec_p_value": 0.27,
        "christoffersen_independence_lr": 0.3,
        "christoffersen_independence_p_value": 0.58,
        "conditional_coverage_lr": 1.5,
        "conditional_coverage_p_value": 0.47,
        "zone": "green",
        "exception_dates": [],
        "mean_var_gbp": 100.0,
        "var_stability": 0.02,
        "rolling_exceptions": None,
    }
    base.update(overrides)
    return base


def _backtest_by_basis_quality(level: dict) -> dict:
    return {
        "hypothetical": {"ok": {"levels": [level]}, "degraded": {"levels": [level]}},
        "ladder": {"ok": {"levels": [level]}, "degraded": {"levels": [level]}},
    }


def _text(component: object) -> str:
    if isinstance(component, str):
        return component
    children = getattr(component, "children", None)
    if children is None:
        return ""
    if not isinstance(children, list):
        children = [children]
    return "".join(_text(c) for c in children)


def test_selects_hypothetical_degraded_by_default() -> None:
    hyp_level = _level(exception_count=6)
    ladder_level = _level(exception_count=99)
    data = {
        "hypothetical": {"ok": {"levels": [hyp_level]}, "degraded": {"levels": [hyp_level]}},
        "ladder": {"ok": {"levels": [ladder_level]}, "degraded": {"levels": [ladder_level]}},
    }
    panel = build_panel(
        data, selected_confidence_bp=[9500], pnl_basis="hypothetical", hide_degraded=False
    )
    text = _text(panel)
    assert "6" in text
    assert "99" not in text


def test_hide_degraded_selects_the_ok_result() -> None:
    ok_level = _level(exception_count=3)
    degraded_level = _level(exception_count=7)
    data = {
        "hypothetical": {
            "ok": {"levels": [ok_level]},
            "degraded": {"levels": [degraded_level]},
        },
        "ladder": {"ok": {"levels": [ok_level]}, "degraded": {"levels": [degraded_level]}},
    }
    panel_shown = build_panel(
        data, selected_confidence_bp=[9500], pnl_basis="hypothetical", hide_degraded=False
    )
    panel_hidden = build_panel(
        data, selected_confidence_bp=[9500], pnl_basis="hypothetical", hide_degraded=True
    )
    assert "7" in _text(panel_shown)
    assert "3" in _text(panel_hidden)


def test_pnl_basis_selects_the_matching_result() -> None:
    hyp_level = _level(exception_count=1)
    ladder_level = _level(exception_count=9)
    data = _backtest_by_basis_quality(hyp_level)
    data["ladder"] = {"ok": {"levels": [ladder_level]}, "degraded": {"levels": [ladder_level]}}

    panel = build_panel(
        data, selected_confidence_bp=[9500], pnl_basis="ladder", hide_degraded=False
    )
    assert "9" in _text(panel)


def test_renders_exception_count_expected_pvalues_zone_mean_var_stability() -> None:
    data = _backtest_by_basis_quality(_level())
    panel = build_panel(
        data, selected_confidence_bp=[9500], pnl_basis="hypothetical", hide_degraded=False
    )
    text = _text(panel)
    for expected in ("6", "12.5", "0.27", "0.47", "Pass", "100", "0.02"):
        assert expected in text


def test_insufficient_observations_shows_not_enough_observations_message() -> None:
    level = _level(
        observation_count=1,
        kupiec_lr=None,
        kupiec_p_value=None,
        christoffersen_independence_lr=None,
        christoffersen_independence_p_value=None,
        conditional_coverage_lr=None,
        conditional_coverage_p_value=None,
        var_stability=None,
        zone=None,
    )
    data = _backtest_by_basis_quality(level)
    panel = build_panel(
        data, selected_confidence_bp=[9500], pnl_basis="hypothetical", hide_degraded=False
    )
    text = _text(panel)
    assert "not enough observations" in text.lower()


def test_returns_a_div() -> None:
    panel = build_panel(
        _backtest_by_basis_quality(_level()),
        selected_confidence_bp=[9500],
        pnl_basis="hypothetical",
        hide_degraded=False,
    )
    assert isinstance(panel, html.Div)
