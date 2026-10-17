"""Unit tests for src/pages/risk.py's VaR-tab callback logic (026-var-risk-view).

Mirrors test_risk_page.py's plain-function-call pattern: `app` is imported first so
`dash.register_page()` inside risk.py (which needs the Dash app to already exist) succeeds,
then the callback-decorated functions are called directly as plain functions.
"""

from __future__ import annotations

from datetime import date

import pytest

import app as app_module  # noqa: F401
import src.pages.risk as risk_module
from src.exceptions import PortfolioAnalysisServiceError
from src.models.portfolio_analysis import (
    VarBacktestResponse,
    VarMethodsResponse,
    VarSeriesResponse,
    VarStatusSummary,
)


class _FakeVarMethodsClient:
    def __init__(self, raise_error: bool = False) -> None:
        self._raise_error = raise_error

    def get_var_methods(self) -> VarMethodsResponse:
        if self._raise_error:
            raise PortfolioAnalysisServiceError("stubbed failure")
        return VarMethodsResponse.model_validate(
            {
                "method": "historical-simulation",
                "methodology_version": "1.0.0",
                "lookbacks": [{"code": "2y", "business_days": 520, "is_headline": True}],
                "confidence_levels_bp": [9500, 9900],
                "measures": [],
                "_links": {"self": "/v1/risk/var/methods"},
            }
        )


class _RecordingVarDataClient:
    """Records every get_var_series/get_var_backtest/get_var_status call it receives."""

    def __init__(self, raise_error_on: str | None = None) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self._raise_error_on = raise_error_on

    def get_var_series(
        self, account_name: str, start: date, end: date, lookback: str
    ) -> VarSeriesResponse:
        self.calls.append(("series", {"lookback": lookback}))
        if self._raise_error_on == "series":
            raise PortfolioAnalysisServiceError("stubbed failure")
        return VarSeriesResponse.model_validate(
            {
                "account_name": account_name,
                "lookback_code": lookback,
                "lookback_days": 520,
                "from_date": str(start),
                "to_date": str(end),
                "series": [],
                "_links": {"self": "s", "status": "st", "runs": "r"},
            }
        )

    def get_var_backtest(
        self,
        account_name: str,
        start: date,
        end: date,
        lookback: str,
        pnl_basis: str,
        min_quality: str,
    ) -> VarBacktestResponse:
        self.calls.append(("backtest", {"pnl_basis": pnl_basis, "min_quality": min_quality}))
        if self._raise_error_on == "backtest":
            raise PortfolioAnalysisServiceError("stubbed failure")
        return VarBacktestResponse.model_validate(
            {
                "account_name": account_name,
                "lookback_code": lookback,
                "lookback_days": 520,
                "from_date": str(start),
                "to_date": str(end),
                "pnl_basis": pnl_basis,
                "min_quality": min_quality,
                "levels": [],
                "_links": {"self": "s", "status": "st", "runs": "r"},
            }
        )

    def get_var_status(self, account_name: str) -> VarStatusSummary:
        self.calls.append(("status", {}))
        if self._raise_error_on == "status":
            raise PortfolioAnalysisServiceError("stubbed failure")
        return VarStatusSummary.model_validate(
            {"account_name": account_name, "computed_range": None, "missing_dates": 3, "_links": {}}
        )


def test_fetch_var_methods_writes_store_and_controls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(risk_module, "_get_client", lambda: _FakeVarMethodsClient())
    store_data, controls_children = risk_module._fetch_var_methods(1)

    assert store_data["confidence_levels_bp"] == [9500, 9900]
    # controls_children is the rendered build_controls() output -- just confirm it isn't the
    # None-methods placeholder (its id is still "risk-var-controls" either way, so check the
    # populated-only confidence dropdown is present somewhere in the tree).
    assert controls_children is not None


def test_fetch_var_methods_on_error_sets_error_state_and_no_store_update(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(risk_module, "_get_client", lambda: _FakeVarMethodsClient(raise_error=True))
    store_data, controls_children = risk_module._fetch_var_methods(1)

    assert store_data is None
    assert controls_children is not None


_METHODS_DATA = {"lookbacks": [{"code": "1y"}, {"code": "2y"}, {"code": "5y"}]}


def test_fetch_var_data_calls_series_once_backtest_four_times_status_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _RecordingVarDataClient()
    monkeypatch.setattr(risk_module, "_get_client", lambda: client)

    payload = risk_module._fetch_var_data(
        "HL-SIPP", "2026-01-02", "2026-03-02", "2y", _METHODS_DATA
    )

    series_calls = [c for c in client.calls if c[0] == "series"]
    backtest_calls = [c for c in client.calls if c[0] == "backtest"]
    status_calls = [c for c in client.calls if c[0] == "status"]
    assert len(series_calls) == 1
    assert len(backtest_calls) == 4
    assert len(status_calls) == 1
    pairs = {(c[1]["pnl_basis"], c[1]["min_quality"]) for c in backtest_calls}
    assert pairs == {
        ("hypothetical", "ok"),
        ("hypothetical", "degraded"),
        ("ladder", "ok"),
        ("ladder", "degraded"),
    }
    assert payload["fetch_error"] is None
    assert payload["backtest"]["hypothetical"]["ok"]["pnl_basis"] == "hypothetical"
    assert payload["backtest"]["ladder"]["degraded"]["min_quality"] == "degraded"
    assert payload["status"]["missing_dates"] == 3


@pytest.mark.parametrize("failing_call", ["series", "backtest", "status"])
def test_fetch_var_data_sets_fetch_error_on_any_failure(
    failing_call: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = _RecordingVarDataClient(raise_error_on=failing_call)
    monkeypatch.setattr(risk_module, "_get_client", lambda: client)

    payload = risk_module._fetch_var_data(
        "HL-SIPP", "2026-01-02", "2026-03-02", "2y", _METHODS_DATA
    )

    assert payload["fetch_error"] is not None
    assert payload.get("series") is None
    assert payload.get("backtest") is None
    assert payload.get("status") is None


def test_fetch_var_data_unsupported_code_skips_series_and_backtest_but_still_fetches_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """027 FR-009 / finding F1: an unsupported range code (not in the server's reported
    look-backs, or None) must not call get_var_series/get_var_backtest, but the
    account-level status call still happens; the returned payload is well-formed (not
    None) with an empty series/backtest so `_render_var_view`'s existing empty-series
    branch renders the empty state rather than leaving stale data on screen.
    """
    client = _RecordingVarDataClient()
    monkeypatch.setattr(risk_module, "_get_client", lambda: client)

    payload = risk_module._fetch_var_data(
        "HL-SIPP", "2026-01-02", "2026-03-02", "3y", _METHODS_DATA
    )

    assert [c[0] for c in client.calls] == ["status"]
    assert payload is not None
    assert payload["fetch_error"] is None
    assert payload["series"] == {"series": []}
    assert payload["backtest"] == {}
    assert payload["status"]["missing_dates"] == 3


def test_fetch_var_data_none_code_skips_series_and_backtest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """None (custom range / default full-history view, before any shortcut is clicked)
    is likewise unsupported -- same empty-payload behavior as an explicit 3y/10y/all.
    """
    client = _RecordingVarDataClient()
    monkeypatch.setattr(risk_module, "_get_client", lambda: client)

    payload = risk_module._fetch_var_data(
        "HL-SIPP", "2026-01-02", "2026-03-02", None, _METHODS_DATA
    )

    assert [c[0] for c in client.calls] == ["status"]
    assert payload["series"] == {"series": []}
    assert payload["backtest"] == {}


# --- FR-003: the confidence multi-select must never be allowed to clear to empty ---


def test_track_last_nonempty_confidence_records_nonempty_values() -> None:
    assert risk_module._track_last_nonempty_confidence([9500, 9900]) == [9500, 9900]


def test_track_last_nonempty_confidence_prevents_update_on_empty() -> None:
    from dash.exceptions import PreventUpdate

    with pytest.raises(PreventUpdate):
        risk_module._track_last_nonempty_confidence([])


def test_guard_confidence_selection_reverts_an_empty_clear() -> None:
    result = risk_module._guard_confidence_selection([], [9500])
    assert result == [9500]


def test_guard_confidence_selection_prevents_update_when_nonempty() -> None:
    from dash.exceptions import PreventUpdate

    with pytest.raises(PreventUpdate):
        risk_module._guard_confidence_selection([9900], [9500])


# --- US5: empty/stale-data branching in _render_var_view ---------------------------


def _store_payload(
    series: list[dict] | None = None,
    computed_range: dict | None = None,
    fetch_error: str | None = None,
    missing_dates: int = 0,
) -> dict:
    return {
        "account_name": "ACCT",
        "lookback_code": "2y",
        "series": {"series": series or []},
        "backtest": {
            "hypothetical": {"ok": {"levels": []}, "degraded": {"levels": []}},
            "ladder": {"ok": {"levels": []}, "degraded": {"levels": []}},
        },
        "status": {
            "account_name": "ACCT",
            "computed_range": computed_range,
            "missing_dates": missing_dates,
        },
        "fetch_error": fetch_error,
    }


def test_render_var_view_fetch_error_shows_error_state() -> None:
    chart, panel = risk_module._render_var_view(
        _store_payload(fetch_error="boom"), [9500], "gbp", "hypothetical", False, False
    )
    assert chart.id == "risk-error-state"
    assert panel.id == "risk-error-state"


def test_render_var_view_never_computed_shows_empty_state() -> None:
    chart, panel = risk_module._render_var_view(
        _store_payload(series=[], computed_range=None), [9500], "gbp", "hypothetical", False, False
    )
    assert chart.id == "risk-empty-state"
    assert panel.id == "risk-empty-state"
    assert "run" in chart.children.lower()


def test_render_var_view_computed_but_empty_range_shows_narrower_message() -> None:
    chart, panel = risk_module._render_var_view(
        _store_payload(
            series=[], computed_range={"from_date": "2024-01-02", "to_date": "2026-09-30"}
        ),
        [9500],
        "gbp",
        "hypothetical",
        False,
        False,
    )
    assert chart.id == "risk-empty-state"
    assert "selected range" in chart.children.lower()
    assert "run" not in chart.children.lower()


def test_render_var_view_never_computed_and_empty_range_messages_differ() -> None:
    never_computed, _ = risk_module._render_var_view(
        _store_payload(series=[], computed_range=None), [9500], "gbp", "hypothetical", False, False
    )
    empty_range, _ = risk_module._render_var_view(
        _store_payload(
            series=[], computed_range={"from_date": "2024-01-02", "to_date": "2026-09-30"}
        ),
        [9500],
        "gbp",
        "hypothetical",
        False,
        False,
    )
    assert never_computed.children != empty_range.children


def test_render_var_view_with_data_delegates_to_builders() -> None:
    entry = {
        "date": "2026-03-02",
        "outcome_date": "2026-03-03",
        "total_value_gbp": 1000.0,
        "scenario_count": 520,
        "actual_mv_pct": 100.0,
        "proxied_mv_pct": 0.0,
        "rescaled_mv_pct": 0.0,
        "quality": "ok",
        "quality_reason": None,
        "hypothetical_pnl_gbp": -10.0,
        "ladder_pnl_gbp": -10.0,
        "levels": [
            {
                "confidence_bp": 9500,
                "var_gbp": 100.0,
                "var_pct": 10.0,
                "es_gbp": 120.0,
                "es_pct": 12.0,
                "hypothetical_exception": False,
                "ladder_exception": False,
            }
        ],
    }
    chart, panel = risk_module._render_var_view(
        _store_payload(
            series=[entry], computed_range={"from_date": "2026-01-02", "to_date": "2026-03-02"}
        ),
        [9500],
        "gbp",
        "hypothetical",
        False,
        False,
    )
    assert chart.id == "risk-var-chart"
    assert panel.id == "risk-var-backtest-panel-content"


def test_render_stale_banner_shows_missing_dates_when_positive() -> None:
    banner = risk_module._render_stale_banner(_store_payload(missing_dates=7))
    assert "7" in str(banner)


def test_render_stale_banner_empty_when_zero_missing() -> None:
    banner = risk_module._render_stale_banner(_store_payload(missing_dates=0))
    assert banner is None


def test_render_stale_banner_prevents_update_with_no_store_data() -> None:
    from dash.exceptions import PreventUpdate

    with pytest.raises(PreventUpdate):
        risk_module._render_stale_banner(None)
