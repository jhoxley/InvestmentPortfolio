"""Step definitions for the Value at Risk tab's BDD feature files (026-var-risk-view).

No real portfolio-analysis-service instance is used: every scenario monkeypatches
`src.pages.risk._get_client` with an in-memory fake implementing the full
`PortfolioAnalysisClient` Protocol, mirroring `test_risk_steps.py`'s own `_FakeRiskClient`
pattern.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from pytest_bdd import given, parsers, scenarios, then, when

import app as app_module
import src.pages.risk as risk_module
from src.exceptions import PortfolioAnalysisServiceError
from src.models.portfolio_analysis import (
    AccountResourceRange,
    AccountSummary,
    BacktestConfidenceResult,
    ConfidenceLevelEstimate,
    MethodLookback,
    VarBacktestResponse,
    VarMethodsResponse,
    VarSeriesEntry,
    VarSeriesResponse,
    VarStatusSummary,
)

scenarios("../features/var_risk_tab_shell.feature")
scenarios("../features/var_risk_chart.feature")
scenarios("../features/var_risk_backtest_panel.feature")
scenarios("../features/var_risk_instant_controls.feature")
scenarios("../features/var_risk_refetch_controls.feature")
scenarios("../features/var_risk_empty_and_stale.feature")
scenarios("../features/var_risk_hide_degraded.feature")

_TIMEOUT = 10

_ACCOUNT = AccountSummary(
    account_name="AAA-VAR-ACCT",
    capital_ledger=AccountResourceRange(from_date=date(2024, 1, 2), to_date=date(2026, 9, 30)),
    position_ladder=AccountResourceRange(from_date=date(2024, 1, 2), to_date=date(2026, 10, 1)),
)
_SECOND_ACCOUNT = AccountSummary(
    account_name="ZZZ-VAR-ACCT",
    capital_ledger=AccountResourceRange(from_date=date(2024, 1, 2), to_date=date(2026, 9, 30)),
    position_ladder=AccountResourceRange(from_date=date(2024, 1, 2), to_date=date(2026, 10, 1)),
)


def _default_methods() -> VarMethodsResponse:
    return VarMethodsResponse(
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


def _default_entry(
    on: date,
    quality: str = "ok",
    hypothetical_pnl_gbp: float = -50.0,
    ladder_pnl_gbp: float = -50.0,
    var_9500_gbp: float = 100.0,
) -> VarSeriesEntry:
    insufficient = quality == "insufficient"
    return VarSeriesEntry(
        date=on,
        outcome_date=date.fromordinal(on.toordinal() + 1),
        total_value_gbp=1000.0,
        scenario_count=0 if insufficient else 520,
        actual_mv_pct=100.0,
        proxied_mv_pct=0.0,
        rescaled_mv_pct=0.0,
        quality=quality,  # type: ignore[arg-type]
        quality_reason=None if quality == "ok" else quality,
        hypothetical_pnl_gbp=hypothetical_pnl_gbp,
        ladder_pnl_gbp=ladder_pnl_gbp,
        levels=[
            ConfidenceLevelEstimate(
                confidence_bp=9500,
                var_gbp=None if insufficient else var_9500_gbp,
                var_pct=None if insufficient else var_9500_gbp / 10,
                es_gbp=None if insufficient else var_9500_gbp * 1.2,
                es_pct=None if insufficient else var_9500_gbp * 1.2 / 10,
                hypothetical_exception=None
                if insufficient
                else hypothetical_pnl_gbp < -var_9500_gbp,
                ladder_exception=None if insufficient else ladder_pnl_gbp < -var_9500_gbp,
            )
        ],
    )


def _default_backtest_level() -> BacktestConfidenceResult:
    return BacktestConfidenceResult(
        confidence_bp=9500,
        observation_count=250,
        exception_count=6,
        expected_exceptions=12.5,
        exception_rate=0.024,
        kupiec_lr=1.2,
        kupiec_p_value=0.27,
        christoffersen_independence_lr=0.3,
        christoffersen_independence_p_value=0.58,
        conditional_coverage_lr=1.5,
        conditional_coverage_p_value=0.47,
        zone="green",
        exception_dates=[],
        mean_var_gbp=100.0,
        var_stability=0.02,
        rolling_exceptions=None,
    )


class _FakeVarRiskClient:
    """Full PortfolioAnalysisClient double for the Value at Risk tab's scenarios."""

    def __init__(
        self,
        accounts: list[AccountSummary] | None = None,
        series_entries: list[VarSeriesEntry] | None = None,
        methods: VarMethodsResponse | None = None,
        missing_dates: int = 0,
        computed_range: Any = None,
        raise_on_methods: bool = False,
        raise_on_series: bool = False,
    ) -> None:
        self._accounts = accounts if accounts is not None else [_ACCOUNT, _SECOND_ACCOUNT]
        self._series_entries = (
            series_entries if series_entries is not None else [_default_entry(date(2026, 3, 2))]
        )
        self._methods = methods if methods is not None else _default_methods()
        self._missing_dates = missing_dates
        self._computed_range = computed_range
        self._raise_on_methods = raise_on_methods
        self._raise_on_series = raise_on_series
        self.series_calls: list[dict[str, Any]] = []
        self.backtest_calls: list[dict[str, Any]] = []
        self.series_calls_after_initial_load = 0
        self.backtest_calls_after_initial_load = 0
        self.overlay_y_before_lookback_change: list[float | None] | None = None

    def list_accounts(self) -> list[AccountSummary]:
        return self._accounts

    def get_return_histogram(self, account_name: str, start: date, end: date) -> Any:
        raise NotImplementedError("the VaR tab's scenarios don't exercise the histogram tab")

    def get_var_methods(self) -> VarMethodsResponse:
        if self._raise_on_methods:
            raise PortfolioAnalysisServiceError("stubbed failure")
        return self._methods

    def get_var_series(
        self, account_name: str, start: date, end: date, lookback: str
    ) -> VarSeriesResponse:
        self.series_calls.append({"lookback": lookback, "account_name": account_name})
        if self._raise_on_series:
            raise PortfolioAnalysisServiceError("stubbed failure")
        # Scale each entry's VaR by look-back so a BDD scenario switching look-backs can
        # assert the chart's rendered data actually changed (not left over from before).
        scale = 1.0 if lookback == "2y" else 0.5
        scaled_series = [
            {
                **entry,
                "levels": [
                    {**level, "var_gbp": level["var_gbp"] * scale}
                    if level["var_gbp"] is not None
                    else level
                    for level in entry["levels"]
                ],
            }
            for entry in [e.model_dump(mode="json") for e in self._series_entries]
        ]
        return VarSeriesResponse.model_validate(
            {
                "account_name": account_name,
                "lookback_code": lookback,
                "lookback_days": 520,
                "from_date": str(start),
                "to_date": str(end),
                "series": scaled_series,
                "_links": {
                    "self": f"/v1/accounts/{account_name}/risk/var",
                    "status": f"/v1/accounts/{account_name}/risk/var/status",
                    "runs": f"/v1/accounts/{account_name}/risk/var/runs",
                },
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
        self.backtest_calls.append({"pnl_basis": pnl_basis, "min_quality": min_quality})
        return VarBacktestResponse(
            account_name=account_name,
            lookback_code=lookback,
            lookback_days=520,
            from_date=start,
            to_date=end,
            pnl_basis=pnl_basis,  # type: ignore[arg-type]
            min_quality=min_quality,  # type: ignore[arg-type]
            levels=[_default_backtest_level()],
            _links={
                "self": f"/v1/accounts/{account_name}/risk/var/backtest",
                "status": f"/v1/accounts/{account_name}/risk/var/status",
                "runs": f"/v1/accounts/{account_name}/risk/var/runs",
            },
        )

    def get_var_status(self, account_name: str) -> VarStatusSummary:
        return VarStatusSummary(
            account_name=account_name,
            computed_range=self._computed_range,
            missing_dates=self._missing_dates,
        )


def _install_stub_client(monkeypatch: Any, client: _FakeVarRiskClient) -> None:
    monkeypatch.setattr(risk_module, "_get_client", lambda: client)


@given(
    "portfolio-analysis-service has an account with a completed VaR calculation",
    target_fixture="stub_client",
)
def stub_client_with_completed_calculation(monkeypatch: Any) -> _FakeVarRiskClient:
    client = _FakeVarRiskClient(computed_range={"from_date": "2024-01-02", "to_date": "2026-09-30"})
    _install_stub_client(monkeypatch, client)
    return client


@when(
    "the browser loads the Risk page and its content finishes loading",
    target_fixture="dash_app",
)
def load_risk_page(dash_duo: Any, monkeypatch: Any) -> Any:
    if risk_module._get_client.__module__ == "src.pages.risk":
        stub_client_with_completed_calculation(monkeypatch)
    dash_duo.start_server(app_module.app)
    dash_duo.driver.get(f"{dash_duo.server_url}/risk")
    dash_duo.wait_for_element("#risk-tabs", timeout=_TIMEOUT)
    return app_module.app


@given(
    "the browser has loaded the Risk page and its content finished loading",
    target_fixture="dash_app",
)
def risk_page_loaded(dash_duo: Any, monkeypatch: Any) -> Any:
    return load_risk_page(dash_duo, monkeypatch)


@then(parsers.parse('there is a "{var_label}" tab next to the "{histogram_label}" tab'))
def assert_both_tabs_present(dash_duo: Any, var_label: str, histogram_label: str) -> None:
    tabs_text = dash_duo.find_element("#risk-tabs").text
    assert histogram_label in tabs_text
    assert var_label in tabs_text


@when(parsers.parse('I select the "{tab_label}" tab'))
def select_tab(dash_duo: Any, tab_label: str, stub_client: _FakeVarRiskClient) -> None:
    tab_link = dash_duo.find_element("#risk-tabs a[role='tab']:not([aria-selected='true'])")
    if tab_label in tab_link.text:
        tab_link.click()
    # Either way, wait for the VaR tab's initial fetch to complete -- one of the chart or
    # the empty/error state -- then snapshot the call counts so later "instant control"
    # steps can assert no further calls were made.
    dash_duo.wait_for_element(
        "#risk-var-chart .js-plotly-plot, "
        "#risk-var-chart-container #risk-empty-state, "
        "#risk-var-chart-container #risk-error-state",
        timeout=_TIMEOUT,
    )
    stub_client.series_calls_after_initial_load = len(stub_client.series_calls)
    stub_client.backtest_calls_after_initial_load = len(stub_client.backtest_calls)


@then(
    parsers.parse(
        "the account selector, date range and shortcut buttons are the same DOM elements "
        'as on the "{other_tab_label}" tab'
    )
)
def assert_shared_controls_unchanged(dash_duo: Any, other_tab_label: str) -> None:
    # The shared parameters bar lives in shell.py above the tabs, outside either dbc.Tab's
    # children -- asserting its ids exist once (not duplicated per tab) proves this.
    accounts = dash_duo.driver.find_elements("css selector", "#app-parameters-account")
    assert len(accounts) == 1


# --- User Story 1: main chart -----------------------------------------------------


@given(
    "portfolio-analysis-service has a VaR series with an exceedance day",
    target_fixture="stub_client",
)
def stub_client_with_exceedance(monkeypatch: Any) -> _FakeVarRiskClient:
    entries = [
        _default_entry(date(2026, 3, 2), hypothetical_pnl_gbp=-200.0, var_9500_gbp=100.0),
        _default_entry(date(2026, 3, 3), hypothetical_pnl_gbp=-10.0, var_9500_gbp=100.0),
    ]
    client = _FakeVarRiskClient(series_entries=entries)
    _install_stub_client(monkeypatch, client)
    return client


@then("the chart, the linked market-value chart and the backtest panel are all present")
def assert_chart_and_panel_present(dash_duo: Any) -> None:
    dash_duo.wait_for_element("#risk-var-chart .js-plotly-plot", timeout=_TIMEOUT)
    panel_text = dash_duo.find_element("#risk-var-backtest-panel").text
    assert panel_text.strip() != ""


@then("the exceedance day's bar is coloured differently from non-exceeding days")
def assert_exceedance_bar_colored(dash_duo: Any) -> None:
    colors = dash_duo.driver.execute_script(
        "var gd = document.querySelector('#risk-var-chart .js-plotly-plot');"
        "var bar = gd.data.find(function(t) { return t.type === 'bar'; });"
        "return bar.marker.color;"
    )
    assert len(set(colors)) > 1


@when("I turn on the Expected Shortfall display")
def turn_on_show_es(dash_duo: Any) -> None:
    toggle = dash_duo.find_element("#risk-var-show-es input")
    if not toggle.is_selected():
        toggle.click()


@then("a dashed Expected Shortfall overlay line appears on the chart")
def assert_es_overlay_present(dash_duo: Any) -> None:
    dashed_names = dash_duo.driver.execute_script(
        "var gd = document.querySelector('#risk-var-chart .js-plotly-plot');"
        "return gd.data.filter(function(t) { return t.line && t.line.dash === 'dash'; })"
        ".map(function(t) { return t.name; });"
    )
    assert any("ES" in name for name in dashed_names)


# --- User Story 2: backtest panel -------------------------------------------------


@then(
    "the backtest panel shows exceedances observed and expected, both p-values, a "
    "pass/fail rating, mean VaR and stability"
)
def assert_backtest_panel_headline_figures(dash_duo: Any) -> None:
    panel_text = dash_duo.find_element("#risk-var-backtest-panel").text
    for expected in ("6", "12.5", "0.27", "0.47", "Pass", "100", "0.02"):
        assert expected in panel_text


@when(parsers.parse("I select only the {pct} confidence level"))
def select_only_confidence_level(dash_duo: Any, pct: str) -> None:
    checkboxes = dash_duo.driver.find_elements(
        "css selector", "#risk-var-confidence input[type='checkbox']"
    )
    labels = dash_duo.driver.find_elements("css selector", "#risk-var-confidence label")
    for checkbox, label in zip(checkboxes, labels, strict=True):
        should_be_checked = pct in label.text
        if checkbox.is_selected() != should_be_checked:
            checkbox.click()


@then(parsers.parse("the backtest panel shows figures for the {pct} confidence level only"))
def assert_backtest_panel_single_level(dash_duo: Any, pct: str) -> None:
    panel_text = dash_duo.find_element("#risk-var-backtest-panel").text
    assert pct in panel_text


# --- User Story 3: instant confidence/units/PnL-basis controls ---------------------


@when("I switch units to percentage")
def switch_units_to_pct(dash_duo: Any) -> None:
    option = dash_duo.find_element("#risk-var-units input[value='pct']")
    option.click()


@when("I switch PnL basis to ladder")
def switch_pnl_basis_to_ladder(dash_duo: Any) -> None:
    option = dash_duo.find_element("#risk-var-pnl-basis input[value='ladder']")
    option.click()


@then("no new VaR series or backtest request was made")
def assert_no_new_var_requests(dash_duo: Any, stub_client: _FakeVarRiskClient) -> None:
    # Give any (incorrectly) triggered fetch callback a moment to fire before asserting
    # its absence -- the chart/panel re-render from the instant controls is itself
    # synchronous and already visible by the time this step runs.
    dash_duo.wait_for_element("#risk-var-chart .js-plotly-plot", timeout=_TIMEOUT)
    assert len(stub_client.series_calls) == stub_client.series_calls_after_initial_load
    assert len(stub_client.backtest_calls) == stub_client.backtest_calls_after_initial_load


# --- User Story 4: account/date/look-back refetch ---------------------------------


@when("I select a different account")
def select_different_account(dash_duo: Any) -> None:
    select = dash_duo.find_element("#app-parameters-account")
    from selenium.webdriver.support.ui import Select as SeleniumSelect

    current = select.get_attribute("value")
    options = SeleniumSelect(select)
    other = next(o for o in options.options if o.get_attribute("value") != current)
    options.select_by_value(other.get_attribute("value"))


@then(parsers.parse("a new VaR series request was made for the newly selected account"))
def assert_series_request_for_new_account(dash_duo: Any, stub_client: _FakeVarRiskClient) -> None:
    dash_duo.wait_for_element("#risk-var-chart .js-plotly-plot", timeout=_TIMEOUT)
    assert len(stub_client.series_calls) > stub_client.series_calls_after_initial_load
    selected_account = dash_duo.find_element("#app-parameters-account").get_attribute("value")
    assert stub_client.series_calls[-1]["account_name"] == selected_account


@when("I change the date range")
def change_date_range(dash_duo: Any) -> None:
    dash_duo.driver.execute_script(
        "var el = document.querySelector('#app-parameters-from-date input');"
        "el.value = '2025-01-02';"
        "el.dispatchEvent(new Event('change', {bubbles: true}));"
        "el.blur();"
    )


@then("a new VaR series request was made")
def assert_new_series_request(dash_duo: Any, stub_client: _FakeVarRiskClient) -> None:
    dash_duo.wait_for_element("#risk-var-chart .js-plotly-plot", timeout=_TIMEOUT)
    assert len(stub_client.series_calls) > stub_client.series_calls_after_initial_load


@when(parsers.parse('I change the look-back to "{code}"'))
def change_lookback(dash_duo: Any, code: str, stub_client: _FakeVarRiskClient) -> None:
    from selenium.webdriver.support.ui import Select as SeleniumSelect

    stub_client.overlay_y_before_lookback_change = dash_duo.driver.execute_script(
        "var gd = document.querySelector('#risk-var-chart .js-plotly-plot');"
        "var t = gd.data.find(function(t) { return t.name && t.name.indexOf('VaR') !== -1; });"
        "return t ? t.y : null;"
    )
    select = SeleniumSelect(dash_duo.find_element("#risk-var-lookback"))
    select.select_by_value(code)


@then(parsers.parse('a new VaR series request was made with look-back "{code}"'))
def assert_series_request_with_lookback(
    dash_duo: Any, code: str, stub_client: _FakeVarRiskClient
) -> None:
    dash_duo.wait_for_element("#risk-var-chart .js-plotly-plot", timeout=_TIMEOUT)
    assert stub_client.series_calls[-1]["lookback"] == code


@then("the chart no longer shows the previous selection's data")
def assert_previous_lookback_data_gone(dash_duo: Any, stub_client: _FakeVarRiskClient) -> None:
    overlay_y_after = dash_duo.driver.execute_script(
        "var gd = document.querySelector('#risk-var-chart .js-plotly-plot');"
        "var t = gd.data.find(function(t) { return t.name && t.name.indexOf('VaR') !== -1; });"
        "return t ? t.y : null;"
    )
    assert overlay_y_after != stub_client.overlay_y_before_lookback_change


@then("no periodicity control is shown")
def assert_no_periodicity_control(dash_duo: Any) -> None:
    controls = dash_duo.driver.find_elements("css selector", "#risk-tab-var [id*='periodicity']")
    assert controls == []


# --- User Story 5: empty and stale states -----------------------------------------


@given(
    "portfolio-analysis-service has an account with no calculated VaR data",
    target_fixture="stub_client",
)
def stub_client_never_computed(monkeypatch: Any) -> _FakeVarRiskClient:
    client = _FakeVarRiskClient(series_entries=[], computed_range=None, missing_dates=0)
    _install_stub_client(monkeypatch, client)
    return client


@given(
    "portfolio-analysis-service has an account whose VaR data is behind its trading activity",
    target_fixture="stub_client",
)
def stub_client_stale(monkeypatch: Any) -> _FakeVarRiskClient:
    client = _FakeVarRiskClient(
        computed_range={"from_date": "2024-01-02", "to_date": "2026-09-30"}, missing_dates=5
    )
    _install_stub_client(monkeypatch, client)
    return client


@then("no chart or backtest panel is shown")
def assert_no_chart_or_panel(dash_duo: Any) -> None:
    dash_duo.wait_for_element("#risk-var-chart-container #risk-empty-state", timeout=_TIMEOUT)
    assert dash_duo.driver.find_elements("css selector", "#risk-var-chart") == []


@then("an explanatory message describing how to run a calculation is shown")
def assert_explanatory_empty_message(dash_duo: Any) -> None:
    message = dash_duo.find_element("#risk-var-chart-container").text
    assert "run" in message.lower()


@then("a banner states how many dates are missing")
def assert_banner_states_missing_dates(dash_duo: Any) -> None:
    banner_text = dash_duo.find_element("#risk-var-stale-banner").text
    assert "5" in banner_text


@then("the chart and panel still render")
def assert_chart_and_panel_still_render(dash_duo: Any) -> None:
    dash_duo.wait_for_element("#risk-var-chart .js-plotly-plot", timeout=_TIMEOUT)
    panel_text = dash_duo.find_element("#risk-var-backtest-panel").text
    assert panel_text.strip() != ""


# --- User Story 6: hide degraded-quality dates -------------------------------------


@given(
    "portfolio-analysis-service has a VaR series with a degraded-quality day",
    target_fixture="stub_client",
)
def stub_client_with_degraded_day(monkeypatch: Any) -> _FakeVarRiskClient:
    entries = [
        _default_entry(date(2026, 3, 2), quality="ok"),
        _default_entry(date(2026, 3, 3), quality="degraded"),
    ]
    client = _FakeVarRiskClient(series_entries=entries)
    _install_stub_client(monkeypatch, client)
    return client


def _toggle_switch(dash_duo: Any, dom_id: str, turn_on: bool) -> None:
    toggle = dash_duo.find_element(f"#{dom_id} input")
    if toggle.is_selected() != turn_on:
        toggle.click()


@when(parsers.parse('I turn on "hide degraded-quality dates"'))
def turn_on_hide_degraded(dash_duo: Any) -> None:
    _toggle_switch(dash_duo, "risk-var-hide-degraded", turn_on=True)


@when(parsers.parse('I turn off "hide degraded-quality dates"'))
def turn_off_hide_degraded(dash_duo: Any) -> None:
    _toggle_switch(dash_duo, "risk-var-hide-degraded", turn_on=False)


def _bar_count(dash_duo: Any) -> int:
    return dash_duo.driver.execute_script(
        "var gd = document.querySelector('#risk-var-chart .js-plotly-plot');"
        "var bar = gd.data.find(function(t) { return t.type === 'bar'; });"
        "return bar.x.length;"
    )


@then("the degraded-quality date's bar and overlay point no longer appear on the chart")
def assert_degraded_day_hidden(dash_duo: Any) -> None:
    assert _bar_count(dash_duo) == 1


@then("the degraded-quality date's bar reappears on the chart")
def assert_degraded_day_restored(dash_duo: Any) -> None:
    assert _bar_count(dash_duo) == 2
