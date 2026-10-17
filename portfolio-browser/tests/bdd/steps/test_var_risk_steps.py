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

scenarios("../features/risk_single_page.feature")
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
    # 027: the merged single-page layout has no "#risk-tabs" shell to wait for -- the
    # histogram's chart container is always mounted, so wait for that instead.
    dash_duo.wait_for_element("#risk-chart-container", timeout=_TIMEOUT)
    return app_module.app


@given(
    "the browser has loaded the Risk page and its content finished loading",
    target_fixture="dash_app",
)
def risk_page_loaded(dash_duo: Any, monkeypatch: Any) -> Any:
    return load_risk_page(dash_duo, monkeypatch)


@then("there is no tab control on the page")
def assert_no_tab_control(dash_duo: Any) -> None:
    """027 FR-001: the dbc.Tabs/dbc.Tab shell is gone from the merged single page."""
    assert dash_duo.driver.find_elements("css selector", "#risk-tabs") == []
    assert dash_duo.driver.find_elements("css selector", "[role='tablist']") == []


@then("the return histogram chart and statistics table are visible")
def assert_histogram_visible_without_interaction(dash_duo: Any) -> None:
    """027 FR-002: the histogram renders without any click, as soon as the page loads."""
    chart_container = dash_duo.wait_for_element(
        "#risk-chart-container .js-plotly-plot, #risk-chart-container #risk-empty-state, "
        "#risk-chart-container #risk-error-state",
        timeout=_TIMEOUT,
    )
    assert chart_container.is_displayed()
    table_container = dash_duo.find_element("#risk-table-container")
    assert table_container.is_displayed()


@then(
    "the Value at Risk controls, chart and backtest panel are visible below the histogram "
    "section"
)
def assert_var_section_visible_below_histogram(dash_duo: Any) -> None:
    """027 FR-001/FR-002: both sections are mounted on one page, histogram first."""
    histogram_y = dash_duo.find_element("#risk-chart-container").location["y"]
    var_controls = dash_duo.wait_for_element("#risk-var-controls-container", timeout=_TIMEOUT)
    assert var_controls.is_displayed()
    assert var_controls.location["y"] > histogram_y
    assert dash_duo.find_element("#risk-var-chart-container").is_displayed()
    assert dash_duo.find_element("#risk-var-backtest-panel").is_displayed()


@then("the shared account selector, date range and shortcut buttons appear exactly once")
def assert_shared_controls_not_duplicated(dash_duo: Any) -> None:
    """027: merging the two former tab panels must not duplicate the shared parameters bar."""
    accounts = dash_duo.driver.find_elements("css selector", "#app-parameters-account")
    assert len(accounts) == 1


@given("the Value at Risk section finishes loading")
@when("the Value at Risk section finishes loading")
def var_section_loaded(dash_duo: Any, stub_client: _FakeVarRiskClient) -> None:
    """027: supersedes the old tab-click step -- the VaR section is already mounted on page
    load (no tab to select), so this only waits for its first render and snapshots call
    counts for later "instant control" steps to assert no further calls were made.
    """
    dash_duo.wait_for_element(
        "#risk-var-chart .js-plotly-plot, "
        "#risk-var-chart-container #risk-empty-state, "
        "#risk-var-chart-container #risk-error-state",
        timeout=_TIMEOUT,
    )
    stub_client.series_calls_after_initial_load = len(stub_client.series_calls)
    stub_client.backtest_calls_after_initial_load = len(stub_client.backtest_calls)


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


@then("the chart's legend renders below the chart's plotting area")
def assert_legend_below_chart(dash_duo: Any) -> None:
    """028 FR-001: legend.orientation/y must place it below the plot, not inside it."""
    legend = dash_duo.driver.execute_script(
        "var gd = document.querySelector('#risk-var-chart .js-plotly-plot');"
        "return gd.layout.legend;"
    )
    assert legend["orientation"] == "h"
    assert legend["y"] < 0


@then("the backtest summary panel is fully visible within the viewport")
def assert_backtest_panel_fully_visible(dash_duo: Any) -> None:
    """028 FR-002/SC-001: the panel must not be pushed off-screen by the legend."""
    panel = dash_duo.find_element("#risk-var-backtest-panel")
    window_width = dash_duo.driver.execute_script("return window.innerWidth;")
    assert panel.location["x"] + panel.size["width"] <= window_width


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


def _assert_backtest_panel_is_one_table(dash_duo: Any) -> None:
    """028 FR-003: up to three per-level tables collapse into one combined table."""
    tables = dash_duo.driver.find_elements("css selector", "#risk-var-backtest-panel table")
    assert len(tables) == 1


@then("the backtest panel is exactly one table")
def assert_backtest_panel_is_one_table(dash_duo: Any) -> None:
    _assert_backtest_panel_is_one_table(dash_duo)


@then("the backtest panel is still exactly one table")
def assert_backtest_panel_is_still_one_table(dash_duo: Any) -> None:
    _assert_backtest_panel_is_one_table(dash_duo)


@then(parsers.parse("it has exactly {count:d} value column"))
def assert_backtest_panel_column_count(dash_duo: Any, count: int) -> None:
    """028 FR-004: column count tracks the current confidence-level selection."""
    header_cells = dash_duo.driver.find_elements(
        "css selector", "#risk-var-backtest-panel table th"
    )
    # One header cell is the leading "statistic" column; the rest are value columns.
    assert len(header_cells) - 1 == count


@then(
    "the backtest panel is rendered as a labelled table/grid matching the histogram's "
    "statistics table style"
)
def assert_backtest_panel_matches_histogram_table_style(dash_duo: Any) -> None:
    """027 FR-010/SC-005: both must use the same bordered, labelled table/grid treatment."""
    dash_duo.wait_for_element("#risk-statistics-table", timeout=_TIMEOUT)
    panel_table = dash_duo.find_element("#risk-var-backtest-panel table")
    histogram_table = dash_duo.find_element("#risk-statistics-table table")
    assert panel_table.tag_name == histogram_table.tag_name == "table"
    # Both render via dash_table.DataTable with the same style_cell/style_header dicts
    # (src/pages/_var_backtest_panel.py's STYLE_CELL/STYLE_HEADER, imported by risk.py) --
    # cell padding is the most visible, directly comparable artifact of that shared style.
    panel_cell = dash_duo.find_element("#risk-var-backtest-panel td")
    histogram_cell = dash_duo.find_element("#risk-statistics-table td")
    assert panel_cell.value_of_css_property("padding") == histogram_cell.value_of_css_property(
        "padding"
    )


# --- User Story 3: instant confidence/units/PnL-basis controls ---------------------


@when("I switch units to percentage")
def switch_units_to_pct(dash_duo: Any) -> None:
    option = dash_duo.find_element("#risk-var-units input[value='pct']")
    option.click()


@when("I switch units to money")
def switch_units_to_gbp(dash_duo: Any) -> None:
    option = dash_duo.find_element("#risk-var-units input[value='gbp']")
    option.click()


def _bar_trace_count(dash_duo: Any) -> int:
    return dash_duo.driver.execute_script(
        "var gd = document.querySelector('#risk-var-chart .js-plotly-plot');"
        "return gd.data.filter(function(t) { return t.type === 'bar'; }).length;"
    )


@then("no realised PnL bars are shown on the chart")
def assert_no_pnl_bars(dash_duo: Any) -> None:
    """028 FR-005: the bar trace is omitted entirely in percentage mode."""
    assert _bar_trace_count(dash_duo) == 0


@then("the realised PnL bars reappear on the chart")
def assert_pnl_bars_reappear(dash_duo: Any) -> None:
    """028 FR-006: switching back to money restores the bar trace."""
    assert _bar_trace_count(dash_duo) == 1


def _subplot_title_annotations(dash_duo: Any) -> list[str]:
    return dash_duo.driver.execute_script(
        "var gd = document.querySelector('#risk-var-chart .js-plotly-plot');"
        "return gd.layout.annotations.map(function(a) { return a.text; });"
    )


@then("a caption is visible above the main chart")
def assert_main_chart_caption_visible(dash_duo: Any) -> None:
    """028 FR-007: a caption explaining the main chart, rendered via subplot_titles."""
    titles = _subplot_title_annotations(dash_duo)
    assert len(titles) == 2
    assert "pnl" in titles[0].lower()


@then("a different caption is visible above the linked market-value chart")
def assert_linked_chart_caption_visible(dash_duo: Any) -> None:
    """028 FR-008: a distinct caption explaining the linked market-value chart."""
    titles = _subplot_title_annotations(dash_duo)
    assert "market value" in titles[1].lower()
    assert titles[0] != titles[1]


@then("the VaR forecast line is still shown on the chart")
def assert_var_forecast_line_still_shown(dash_duo: Any) -> None:
    overlays = dash_duo.driver.execute_script(
        "var gd = document.querySelector('#risk-var-chart .js-plotly-plot');"
        "return gd.data.filter(function(t) { return t.name && t.name.indexOf('VaR') !== -1; });"
    )
    assert len(overlays) >= 1


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


# 027: the VaR tab's own "Look-back" dropdown is gone -- changing the look-back now means
# clicking one of the page's shared shortcut buttons (the same ones that drive the
# histogram), identified by their visible label.
_SHORTCUT_BUTTON_IDS_FOR_VAR = {
    "10Y": "overview-shortcut-ytd",
    "1Y": "overview-shortcut-1y",
    "2Y": "risk-shortcut-2y",
    "3Y": "overview-shortcut-3y",
    "5Y": "overview-shortcut-5y",
    "All": "overview-shortcut-all",
}


@when(parsers.parse('I click the "{label}" shortcut button'))
def click_shared_shortcut_button(dash_duo: Any, label: str) -> None:
    button_id = _SHORTCUT_BUTTON_IDS_FOR_VAR[label]
    dash_duo.find_element(f"#{button_id}").click()
    dash_duo.wait_for_element("#risk-chart-container", timeout=_TIMEOUT)


@then(parsers.parse('a new VaR series request was made with look-back "{code}"'))
def assert_series_request_with_lookback(
    dash_duo: Any, code: str, stub_client: _FakeVarRiskClient
) -> None:
    dash_duo.wait_for_element("#risk-var-chart .js-plotly-plot", timeout=_TIMEOUT)
    assert stub_client.series_calls[-1]["lookback"] == code


@then("the histogram section still renders normally")
def assert_histogram_still_renders(dash_duo: Any) -> None:
    """027 FR-009: a range unsupported by VaR must not affect the histogram section."""
    dash_duo.wait_for_element(
        "#risk-chart-container .js-plotly-plot, #risk-chart-container #risk-empty-state, "
        "#risk-chart-container #risk-error-state",
        timeout=_TIMEOUT,
    )


@then(parsers.parse('the Value at Risk section shows "{message}"'))
def assert_var_section_shows_message(dash_duo: Any, message: str) -> None:
    empty_state = dash_duo.wait_for_element(
        "#risk-var-chart-container #risk-empty-state", timeout=_TIMEOUT
    )
    assert message in empty_state.text


@then('no "Look-back" control is shown in the Value at Risk section')
def assert_no_lookback_control_in_dom(dash_duo: Any) -> None:
    assert dash_duo.driver.find_elements("css selector", "#risk-var-lookback") == []


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
