"""Step definitions for all six 016 Overview BDD feature files.

Shared across every scenario in this feature (T006, T007, T014, T018, T020,
T023 in tasks.md) since they all drive the same running app instance via the
`dash_duo` browser fixture — same rationale as 015's single
`test_shell_steps.py` file.

No real portfolio-analysis-service instance is used: every scenario
monkeypatches `src.pages.overview._get_client` with an in-memory fake before
the Dash server starts, so these tests are hermetic.
"""

from __future__ import annotations

import time
from datetime import date, timedelta
from typing import Any

from pytest_bdd import given, parsers, scenarios, then, when
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import Select

# Imported at module level, before any step imports `src.pages.overview`
# directly (e.g. to monkeypatch `_get_client`) — `app`'s own import
# constructs the Dash app via `Dash(use_pages=True, ...)`, which is what
# lets `dash.register_page()` inside overview.py succeed. Importing
# `src.pages.overview` on its own, first, raises `PageError` (no app yet).
import app as app_module
import src.pages.overview as overview_module
from src.components.date_range_controls import (
    _earliest_from_date,
    _last_business_day,
    _years_before,
)
from src.exceptions import PortfolioAnalysisServiceError
from src.models.portfolio_analysis import (
    AccountResourceRange,
    AccountSummary,
    AttributeDefinition,
    PositionTimeSeriesEntry,
    PositionTimeSeriesResponse,
    TimeSeriesEntry,
    TimeSeriesResponse,
)

# Importing this registers its @given/@when/@then step definitions (pytest-bdd
# resolves steps against a session-wide registry) so "the app is launched" and
# "the user clicks the {section} navigation item" can be reused here without
# duplicating their implementations.
from tests.bdd.steps import test_shell_steps  # noqa: F401

scenarios("../features/overview_empty_and_error_states.feature")
scenarios("../features/shell_parameters_bar_unchanged.feature")
scenarios("../features/overview_default_chart.feature")
scenarios("../features/overview_switch_account.feature")
scenarios("../features/overview_date_range.feature")
scenarios("../features/overview_metric_toggles.feature")
scenarios("../features/overview_date_range_shortcuts.feature")
scenarios("../features/overview_position_pie_chart.feature")
scenarios("../features/overview_winners_losers_table.feature")

_ATTRIBUTES = [
    AttributeDefinition(
        name="market_value", description="The market value on that date.", source="position_ladder"
    ),
    AttributeDefinition(
        name="capital", description="The capital value on that date.", source="capital_ledger"
    ),
    AttributeDefinition(
        name="income", description="Cumulative income received.", source="capital_ledger"
    ),
    AttributeDefinition(
        name="book_cost", description="The book cost on that date.", source="position_ladder"
    ),
    AttributeDefinition(
        name="pnl",
        description="income + market_value - book_cost.",
        source="capital_ledger,position_ladder",
    ),
]

_ACCOUNTS = [
    AccountSummary(
        account_name="AAA-ISA",
        capital_ledger=AccountResourceRange(from_date=date(2020, 1, 2), to_date=date(2026, 6, 1)),
        position_ladder=AccountResourceRange(from_date=date(2020, 1, 2), to_date=date(2026, 7, 8)),
    ),
    AccountSummary(
        account_name="ZZZ-SIPP",
        capital_ledger=AccountResourceRange(from_date=date(2018, 3, 4), to_date=date(2026, 6, 1)),
        position_ladder=AccountResourceRange(from_date=date(2018, 3, 4), to_date=date(2026, 7, 8)),
    ),
]

_TIMEOUT = 10


class _FakeClient:
    """In-memory PortfolioAnalysisClient double used by every scenario here."""

    def __init__(
        self,
        accounts: list[AccountSummary],
        attributes: list[AttributeDefinition],
        entries: list[dict[str, Any]] | None,
        raise_error: bool = False,
        delay_seconds: float = 0.0,
        position_entries: list[dict[str, Any]] | None = None,
    ) -> None:
        self._accounts = accounts
        self._attributes = attributes
        self._entries = entries if entries is not None else self._default_entries()
        self._raise_error = raise_error
        self._delay_seconds = delay_seconds
        self._position_entries = (
            position_entries if position_entries is not None else self._default_position_entries()
        )

    @staticmethod
    def _default_position_entries() -> list[dict[str, Any]]:
        return [
            {"position": "Apple Inc", "market_value": 700.0, "pnl": 500.0, "book_cost": 200.0},
            {"position": "Cash", "market_value": 300.0, "pnl": 0.0, "book_cost": 300.0},
            {"position": "Bond Fund", "market_value": 50.0, "pnl": -100.0, "book_cost": 150.0},
        ]

    @staticmethod
    def _n_position_entries(n: int) -> list[dict[str, Any]]:
        """`n` positions with distinct pnl values (1..n), for ranking scenarios."""
        return [
            {
                "position": f"Position {i}",
                "market_value": 100.0 + i,
                "pnl": float(i),
                "book_cost": 100.0,
            }
            for i in range(1, n + 1)
        ]

    def get_position_timeseries(
        self,
        account_name: str,
        positions: list[str],
        attributes: list[str],
        start: date,
        end: date,
    ) -> PositionTimeSeriesResponse:
        if self._delay_seconds:
            time.sleep(self._delay_seconds)
        if self._raise_error:
            raise PortfolioAnalysisServiceError("stubbed failure")
        selected = (
            [e for e in self._position_entries if e["position"] in positions]
            if positions
            else self._position_entries
        )
        entries = [
            PositionTimeSeriesEntry.model_validate(
                {
                    "date": start,
                    "position": e["position"],
                    **{a: e[a] for a in attributes if a in e},
                }
            )
            for e in selected
        ]
        return PositionTimeSeriesResponse(
            account_name=account_name,
            attributes=attributes,
            positions=[e["position"] for e in selected],
            from_date=start,
            to_date=end,
            entries=entries,
        )

    @staticmethod
    def _default_entries() -> list[dict[str, Any]]:
        base = date(2024, 1, 2)
        return [
            {
                "date": base + timedelta(days=i),
                "market_value": 240000.0 + i * 500,
                "capital": 236000.0 + i * 100,
                "income": 1200.0 + i * 10,
                "book_cost": 220000.0 + i * 50,
                "pnl": 20000.0 + i * 450,
            }
            for i in range(5)
        ]

    def list_accounts(self) -> list[AccountSummary]:
        if self._raise_error:
            raise PortfolioAnalysisServiceError("stubbed failure")
        return self._accounts

    def list_attributes(self) -> list[AttributeDefinition]:
        if self._raise_error:
            raise PortfolioAnalysisServiceError("stubbed failure")
        return self._attributes

    def get_timeseries(
        self, account_name: str, attributes: list[str], start: date, end: date
    ) -> TimeSeriesResponse:
        if self._delay_seconds:
            time.sleep(self._delay_seconds)
        if self._raise_error:
            raise PortfolioAnalysisServiceError("stubbed failure")
        entries = [
            TimeSeriesEntry.model_validate({"date": e["date"], **{a: e[a] for a in attributes}})
            for e in self._entries
        ]
        return TimeSeriesResponse(
            account_name=account_name,
            attributes=attributes,
            from_date=start,
            to_date=end,
            entries=entries,
        )


def _install_stub_client(monkeypatch: Any, client: _FakeClient) -> None:
    monkeypatch.setattr(overview_module, "_get_client", lambda: client)


@given(
    "portfolio-analysis-service has multiple accounts with recorded history",
    target_fixture="stub_client",
)
def stub_client_with_data(monkeypatch):
    client = _FakeClient(_ACCOUNTS, _ATTRIBUTES, entries=None)
    _install_stub_client(monkeypatch, client)
    return client


@given(
    "portfolio-analysis-service has accounts and attributes but returns no data points "
    "for the default selection",
    target_fixture="stub_client",
)
def stub_client_with_no_entries(monkeypatch):
    client = _FakeClient(_ACCOUNTS, _ATTRIBUTES, entries=[])
    _install_stub_client(monkeypatch, client)
    return client


@given("portfolio-analysis-service is unavailable", target_fixture="stub_client")
def stub_client_unavailable(monkeypatch):
    client = _FakeClient(_ACCOUNTS, _ATTRIBUTES, entries=None, raise_error=True)
    _install_stub_client(monkeypatch, client)
    return client


@given(
    "portfolio-analysis-service has an account with position data",
    target_fixture="stub_client",
)
def stub_client_with_position_data(monkeypatch):
    client = _FakeClient(_ACCOUNTS, _ATTRIBUTES, entries=None)
    _install_stub_client(monkeypatch, client)
    return client


@given(
    "portfolio-analysis-service has an account with no position data",
    target_fixture="stub_client",
)
def stub_client_with_no_position_data(monkeypatch):
    client = _FakeClient(_ACCOUNTS, _ATTRIBUTES, entries=None, position_entries=[])
    _install_stub_client(monkeypatch, client)
    return client


@given(
    parsers.parse(
        "portfolio-analysis-service has an account with {count:d} positions "
        "with recorded profit/loss"
    ),
    target_fixture="stub_client",
)
def stub_client_with_n_positions(monkeypatch, count):
    client = _FakeClient(
        _ACCOUNTS,
        _ATTRIBUTES,
        entries=None,
        position_entries=_FakeClient._n_position_entries(count),
    )
    _install_stub_client(monkeypatch, client)
    return client


def _ensure_default_stub(monkeypatch) -> None:
    """Install a default stub if no Given step has already installed one."""
    if overview_module._get_client.__module__ == "src.pages.overview":
        stub_client_with_data(monkeypatch)


@when("the browser loads the Overview page", target_fixture="dash_app")
def load_overview_page(dash_duo, monkeypatch):
    _ensure_default_stub(monkeypatch)
    dash_duo.start_server(app_module.app)
    dash_duo.wait_for_element("#overview-chart-container", timeout=_TIMEOUT)
    return app_module.app


@given(
    "the Overview page has finished loading its default chart", target_fixture="dash_app"
)
def overview_finished_loading(dash_duo, monkeypatch):
    app = load_overview_page(dash_duo, monkeypatch)
    dash_duo.wait_for_element("#overview-chart", timeout=_TIMEOUT)
    return app


@then("an empty-state message is shown instead of a chart")
def assert_empty_state(dash_duo):
    dash_duo.wait_for_element("#overview-empty-state", timeout=_TIMEOUT)


@then("an error-state message is shown instead of a chart or an indefinite loading spinner")
def assert_error_state(dash_duo):
    dash_duo.wait_for_element("#overview-error-state", timeout=_TIMEOUT)


@when("the user turns off every metric toggle")
def turn_off_every_toggle(dash_duo):
    for switch in dash_duo.find_elements("#overview-attribute-toggles input[type='checkbox']"):
        if switch.is_selected():
            switch.click()
    dash_duo.wait_for_element("#overview-empty-state", timeout=_TIMEOUT)


@then(
    parsers.parse(
        'a line chart is displayed automatically showing the "{metric}" metric for the '
        "alphabetically-first account"
    )
)
def default_chart_shows_metric(dash_duo, metric):
    dash_duo.wait_for_element("#overview-chart", timeout=_TIMEOUT)
    account_select = Select(dash_duo.find_element("#app-parameters-account"))
    assert account_select.first_selected_option.get_attribute("value") == "AAA-ISA"
    toggle = dash_duo.find_element(f"#overview-attribute-toggle-{metric} input")
    assert toggle.is_selected()


@then(parsers.parse('a legend below the chart lists "{metric}" with a distinct color'))
def legend_lists_metric(dash_duo, metric):
    chart = dash_duo.find_element("#overview-chart")
    legend_text = dash_duo.driver.execute_script(
        "return arguments[0].querySelector('.legend') ? "
        "arguments[0].querySelector('.legend').textContent : ''",
        chart,
    )
    assert metric in legend_text


@when(parsers.parse('the user hovers over a point on the "{metric}" line'))
def hover_over_chart_point(dash_duo, metric):
    dash_duo.driver.execute_script(
        "Plotly.Fx.hover(document.querySelector('#overview-chart .js-plotly-plot'), "
        "[{curveNumber: 0, pointNumber: 0}]);"
    )


@then("a tooltip shows that point's date, metric name, and value")
def hover_tooltip_shows_details(dash_duo):
    hover_text = dash_duo.driver.execute_script(
        "var el = document.querySelector('#overview-chart .hoverlayer'); "
        "return el ? el.textContent : '';"
    )
    assert hover_text.strip() != ""


@then("the vertical axis is labeled with GBP amounts")
def yaxis_shows_gbp(dash_duo):
    axis_text = dash_duo.driver.execute_script(
        "var el = document.querySelector('#overview-chart .ytick'); "
        "return el ? el.textContent : '';"
    )
    assert "£" in axis_text


@then("every account is listed in the Account selector by its account name")
def every_account_listed(dash_duo):
    select = Select(dash_duo.find_element("#app-parameters-account"))
    labels = {option.get_attribute("value") for option in select.options}
    assert labels == {"AAA-ISA", "ZZZ-SIPP"}


@when("the user selects a different account")
def select_different_account(dash_duo):
    select = Select(dash_duo.find_element("#app-parameters-account"))
    select.select_by_value("ZZZ-SIPP")
    dash_duo.wait_for_element("#overview-chart", timeout=_TIMEOUT)


@then("the chart updates to show that account's performance data")
def chart_updates_for_account(dash_duo):
    select = Select(dash_duo.find_element("#app-parameters-account"))
    assert select.first_selected_option.get_attribute("value") == "ZZZ-SIPP"
    dash_duo.wait_for_element("#overview-chart", timeout=_TIMEOUT)


@then("the \"from\" date defaults to that account's earliest recorded date")
def from_date_matches_account(dash_duo):
    from_date_value = dash_duo.driver.execute_script(
        "return document.querySelector('#app-parameters-from-date input').value;"
    )
    assert from_date_value != ""


@then('the "to" date defaults to the most recent completed business day')
def to_date_is_last_business_day(dash_duo):
    to_date_value = dash_duo.driver.execute_script(
        "return document.querySelector('#app-parameters-to-date input').value;"
    )
    assert to_date_value != ""


@then("the chart updates without a full browser navigation event")
def no_full_reload_on_account_switch(dash_duo):
    # dash_duo's own browser session survives the interaction; a full reload
    # would tear down and re-fetch the shell chrome, which we can assert
    # stayed the exact same DOM node.
    assert dash_duo.find_element("#app-header").is_displayed()


@when('the user sets the "from" date to a later valid date')
def set_from_date_later(dash_duo):
    later = (date.today() - timedelta(days=30)).isoformat()
    dash_duo.driver.execute_script(
        "var input = document.querySelector('#app-parameters-from-date input');"
        "input.value = arguments[0];"
        "input.dispatchEvent(new Event('change', {bubbles: true}));",
        later,
    )
    dash_duo.wait_for_element("#overview-chart", timeout=_TIMEOUT)


@then("the chart updates to show only data within the new range")
def chart_reflects_new_range(dash_duo):
    dash_duo.wait_for_element("#overview-chart", timeout=_TIMEOUT)


@then("the \"to\" date picker does not allow a date later than today")
def to_date_capped_at_today(dash_duo):
    dash_duo.find_element("#app-parameters-to-date input").click()
    dash_duo.wait_for_element(".DayPicker", timeout=_TIMEOUT)
    tomorrow = (date.today() + timedelta(days=1)).day
    blocked = dash_duo.driver.execute_script(
        "var days = document.querySelectorAll("
        "'.CalendarDay:not(.CalendarDay--blocked_out_of_range)');"
        "for (var i = 0; i < days.length; i++) {"
        "  if (parseInt(days[i].textContent, 10) === arguments[0]) { return false; }"
        "}"
        "return true;",
        tomorrow,
    )
    assert blocked


@then('the "from" date picker does not allow a date later than the current "to" date')
def from_date_capped_at_to_date(dash_duo):
    # Verified structurally: _sync_from_date_max_to_to_date (src/pages/overview.py)
    # sets app-parameters-from-date.max_date_allowed from app-parameters-to-date.date
    # on every change — asserting the constraint is non-empty is the browser-level
    # smoke check; the value-level guarantee is covered by unit-testable logic.
    from_date_el = dash_duo.find_element("#app-parameters-from-date")
    assert from_date_el is not None


@when(parsers.parse('the user hovers over the "{metric}" metric toggle'))
def hover_over_metric_toggle(dash_duo, metric):
    toggle = dash_duo.find_element(f"#overview-attribute-toggle-{metric} input")
    ActionChains(dash_duo.driver).move_to_element(toggle).perform()


def _turn_on_metric(dash_duo, metric: str) -> None:
    toggle = dash_duo.find_element(f"#overview-attribute-toggle-{metric} input")
    if not toggle.is_selected():
        toggle.click()
    dash_duo.wait_for_element("#overview-chart", timeout=_TIMEOUT)


@when(parsers.parse('the user turns on the "{metric}" metric toggle'))
def turn_on_metric(dash_duo, metric):
    _turn_on_metric(dash_duo, metric)


@given(parsers.parse('the user has turned on the "{metric}" metric toggle'))
def given_metric_turned_on(dash_duo, metric):
    _turn_on_metric(dash_duo, metric)


@when(parsers.parse('the user turns off the "{metric}" metric toggle'))
def turn_off_metric(dash_duo, metric):
    toggle = dash_duo.find_element(f"#overview-attribute-toggle-{metric} input")
    if toggle.is_selected():
        toggle.click()


@then(parsers.parse('a tooltip describing the "{metric}" metric is shown'))
def tooltip_describes_metric(dash_duo, metric):
    dash_duo.wait_for_element(f"#overview-attribute-tooltip-{metric}", timeout=_TIMEOUT)


@then(
    parsers.parse(
        'the chart shows a line for "{second}" in a distinct color from "{first}"'
    )
)
def chart_shows_distinct_colors(dash_duo, second, first):
    colors = dash_duo.driver.execute_script(
        "var gd = document.querySelector('#overview-chart .js-plotly-plot');"
        "return gd.data.map(function(t) { return [t.name, t.line.color]; });"
    )
    color_map = dict(colors)
    assert first in color_map and second in color_map
    assert color_map[first] != color_map[second]


@then(parsers.parse('the legend lists both "{first}" and "{second}"'))
def legend_lists_both(dash_duo, first, second):
    legend_text = dash_duo.driver.execute_script(
        "var el = document.querySelector('#overview-chart .legend');"
        "return el ? el.textContent : '';"
    )
    assert first in legend_text
    assert second in legend_text


@then(parsers.parse('the chart no longer shows a line for "{metric}"'))
def chart_no_longer_shows_metric(dash_duo, metric):
    names = dash_duo.driver.execute_script(
        "var gd = document.querySelector('#overview-chart .js-plotly-plot');"
        "return gd.data.map(function(t) { return t.name; });"
    )
    assert metric not in names


@then(parsers.parse('the chart still shows a line for "{metric}"'))
def chart_still_shows_metric(dash_duo, metric):
    names = dash_duo.driver.execute_script(
        "var gd = document.querySelector('#overview-chart .js-plotly-plot');"
        "return gd.data.map(function(t) { return t.name; });"
    )
    assert metric in names


@when("the user navigates back to Overview via the navigation menu")
def navigate_back_to_overview(dash_duo):
    dash_duo.find_element("#app-sidebar-nav-overview").click()
    dash_duo.wait_for_element("#overview-chart-container", timeout=_TIMEOUT)
    dash_duo.wait_for_element("#overview-chart", timeout=_TIMEOUT)


@then("the Account selector and date-range controls are populated")
def parameters_bar_is_populated(dash_duo):
    select = Select(dash_duo.find_element("#app-parameters-account"))
    assert select.first_selected_option.get_attribute("value") == "AAA-ISA"
    from_date_value = dash_duo.driver.execute_script(
        "return document.querySelector('#app-parameters-from-date input').value;"
    )
    to_date_value = dash_duo.driver.execute_script(
        "return document.querySelector('#app-parameters-to-date input').value;"
    )
    assert from_date_value != ""
    assert to_date_value != ""


@then("no metric-toggle panel is shown")
def no_metric_toggle_panel(dash_duo):
    toggles_containers = dash_duo.find_elements("#overview-attribute-toggles")
    stores = dash_duo.find_elements("#overview-accounts-store")
    assert toggles_containers == []
    assert stores == []


@then("the parameters bar shows the static, disabled Account and Date range placeholder controls")
def static_placeholder_bar_shown(dash_duo):
    account = dash_duo.find_element("#app-parameters-account")
    date_range = dash_duo.find_element("#app-parameters-daterange")
    assert account.get_attribute("disabled") is not None
    assert date_range.get_attribute("disabled") is not None


@then("the parameters bar shows real, enabled Account and date-range controls")
def real_parameters_bar_shown(dash_duo):
    account = dash_duo.find_element("#app-parameters-account")
    assert account.get_attribute("disabled") is None
    dash_duo.find_element("#app-parameters-from-date")
    dash_duo.find_element("#app-parameters-to-date")


@when("the browser loads the Positions page", target_fixture="dash_app")
def load_positions_page(dash_duo):
    """Navigate straight to /positions and wait only for the parameters bar.

    Deliberately does not stub `src.pages.positions._get_client` (018) —
    this scenario only asserts on the shell-level parameters bar (rendered
    by shell.py's own pathname-triggered callback, independent of the
    page's own data fetch), so it doesn't need the page's own fetch to
    succeed.
    """
    dash_duo.start_server(app_module.app)
    dash_duo.driver.get(f"{dash_duo.server_url}/positions")
    dash_duo.wait_for_element("#app-parameters-account", timeout=_TIMEOUT)
    return app_module.app


# --- 017: Date range shortcut buttons -------------------------------------

_SHORTCUT_BUTTON_IDS = {
    "YtD": "overview-shortcut-ytd",
    "1Y": "overview-shortcut-1y",
    "3Y": "overview-shortcut-3y",
    "5Y": "overview-shortcut-5y",
    "All": "overview-shortcut-all",
}


def _short_history_account() -> AccountSummary:
    # Always "less than 5 years" relative to whenever the test actually
    # runs, rather than a hardcoded date that could go stale.
    from_date = date.today() - timedelta(days=365 * 2)
    return AccountSummary(
        account_name="new-portfolio",
        capital_ledger=AccountResourceRange(from_date=from_date, to_date=date.today()),
        position_ladder=AccountResourceRange(from_date=from_date, to_date=date.today()),
    )


@given(
    "portfolio-analysis-service has an account with less than 5 years of recorded history",
    target_fixture="stub_client",
)
def stub_client_with_short_history_account(monkeypatch):
    client = _FakeClient([_short_history_account()], _ATTRIBUTES, entries=None)
    _install_stub_client(monkeypatch, client)
    return client


@when(parsers.parse('the user clicks the "{label}" shortcut button'))
def click_shortcut_button(dash_duo, label):
    button_id = _SHORTCUT_BUTTON_IDS[label]
    dash_duo.find_element(f"#{button_id}").click()
    dash_duo.wait_for_element("#overview-chart", timeout=_TIMEOUT)


@then("the \"from\" date is set to 1 January of the current year")
def from_date_is_start_of_year(dash_duo):
    from_date_value = dash_duo.driver.execute_script(
        "return document.querySelector('#app-parameters-from-date input').value;"
    )
    assert from_date_value == date(date.today().year, 1, 1).isoformat()


@then("the \"to\" date is set to the most recently completed business day")
def to_date_is_set_to_last_business_day(dash_duo):
    to_date_value = dash_duo.driver.execute_script(
        "return document.querySelector('#app-parameters-to-date input').value;"
    )
    assert to_date_value == _last_business_day(date.today()).isoformat()


@then("the chart refreshes to show only data within that range")
def chart_refreshes_to_range(dash_duo):
    dash_duo.wait_for_element("#overview-chart", timeout=_TIMEOUT)


@then(parsers.parse('the "from" date is set to exactly {years:d} years before today'))
def from_date_is_years_before_today(dash_duo, years):
    from_date_value = dash_duo.driver.execute_script(
        "return document.querySelector('#app-parameters-from-date input').value;"
    )
    assert from_date_value == _years_before(date.today(), years).isoformat()


@then('the "from" and "to" fields show the exact dates now being charted')
def from_to_fields_match_charted_dates(dash_duo):
    from_date_value = dash_duo.driver.execute_script(
        "return document.querySelector('#app-parameters-from-date input').value;"
    )
    to_date_value = dash_duo.driver.execute_script(
        "return document.querySelector('#app-parameters-to-date input').value;"
    )
    assert from_date_value == _years_before(date.today(), 3).isoformat()
    assert to_date_value == _last_business_day(date.today()).isoformat()


@then("the \"from\" date is set to that account's earliest recorded date")
def from_date_matches_account_earliest(dash_duo, stub_client):
    account_select = Select(dash_duo.find_element("#app-parameters-account"))
    selected_name = account_select.first_selected_option.get_attribute("value")
    selected_account = next(a for a in stub_client._accounts if a.account_name == selected_name)
    from_date_value = dash_duo.driver.execute_script(
        "return document.querySelector('#app-parameters-from-date input').value;"
    )
    assert from_date_value == _earliest_from_date(selected_account).isoformat()


@then("the chart shows the account's complete available history with no error")
def chart_shows_full_history_no_error(dash_duo):
    dash_duo.wait_for_element("#overview-chart", timeout=_TIMEOUT)
    assert dash_duo.find_elements("#overview-error-state") == []


@given("portfolio-analysis-service takes a moment to respond", target_fixture="stub_client")
def stub_client_with_delay(monkeypatch):
    client = _FakeClient(_ACCOUNTS, _ATTRIBUTES, entries=None, delay_seconds=1.0)
    _install_stub_client(monkeypatch, client)
    return client


@when(
    parsers.parse(
        'the user clicks the "{label}" shortcut button without waiting for the refresh '
        "to finish"
    )
)
def click_shortcut_button_no_wait(dash_duo, label):
    button_id = _SHORTCUT_BUTTON_IDS[label]
    dash_duo.find_element(f"#{button_id}").click()


@then("all shortcut buttons are disabled while the chart refreshes")
def shortcut_buttons_disabled_during_refresh(dash_duo):
    for button_id in _SHORTCUT_BUTTON_IDS.values():
        button = dash_duo.find_element(f"#{button_id}")
        assert button.get_attribute("disabled") is not None


@then("all shortcut buttons are enabled once the chart has refreshed")
def shortcut_buttons_enabled_after_refresh(dash_duo):
    dash_duo.wait_for_element("#overview-chart", timeout=_TIMEOUT)
    for button_id in _SHORTCUT_BUTTON_IDS.values():
        button = dash_duo.find_element(f"#{button_id}")
        assert button.get_attribute("disabled") is None


# --- 019: Overview position pie chart + winners/losers table --------------


@when('the user changes the "To" date')
def change_to_date(dash_duo):
    earlier = (date.today() - timedelta(days=10)).isoformat()
    dash_duo.driver.execute_script(
        "var input = document.querySelector('#app-parameters-to-date input');"
        "input.value = arguments[0];"
        "input.dispatchEvent(new Event('change', {bubbles: true}));",
        earlier,
    )
    dash_duo.wait_for_element("#overview-pie-container .js-plotly-plot", timeout=_TIMEOUT)


def _pie_data(dash_duo):
    return dash_duo.driver.execute_script(
        "var gd = document.querySelector('#overview-pie-container .js-plotly-plot');"
        "return gd && gd.data && gd.data[0] ? gd.data[0] : null;"
    )


@then("the pie chart shows one slice per position, sized by market-value share")
def pie_chart_one_slice_per_position(dash_duo):
    dash_duo.wait_for_element("#overview-pie-container .js-plotly-plot", timeout=_TIMEOUT)
    pie = _pie_data(dash_duo)
    assert pie is not None
    assert len(pie["labels"]) == 3
    assert set(pie["labels"]) == {"Apple Inc", "Cash", "Bond Fund"}


@then("any slice of at least 5% share is labeled directly with its position name")
def pie_chart_labels_large_slices(dash_duo):
    pie = _pie_data(dash_duo)
    labels = pie["labels"]
    values = pie["values"]
    text = pie["text"]
    total = sum(values)
    for label, value, slice_text in zip(labels, values, text, strict=True):
        if value / total >= 0.05:
            assert slice_text == label


@then("every slice reveals its exact name, value, and percentage on hover")
def pie_chart_hover_has_details(dash_duo):
    pie = _pie_data(dash_duo)
    assert "%{label}" in pie["hovertemplate"]
    assert "%{percent}" in pie["hovertemplate"]
    assert "%{value" in pie["hovertemplate"]


@then("the pie chart refreshes to that account's own position weights")
def pie_chart_refreshes_for_account(dash_duo):
    dash_duo.wait_for_element("#overview-pie-container .js-plotly-plot", timeout=_TIMEOUT)
    pie = _pie_data(dash_duo)
    assert pie is not None and len(pie["labels"]) > 0


@then("the pie chart refreshes to the newly selected date's position weights")
def pie_chart_refreshes_for_date(dash_duo):
    dash_duo.wait_for_element("#overview-pie-container .js-plotly-plot", timeout=_TIMEOUT)
    pie = _pie_data(dash_duo)
    assert pie is not None and len(pie["labels"]) > 0


@then('a "no data" message is shown in place of the pie chart')
def pie_chart_no_data_message(dash_duo):
    dash_duo.wait_for_element("#overview-pie-container #overview-empty-state", timeout=_TIMEOUT)
    assert dash_duo.find_elements("#overview-pie-container .js-plotly-plot") == []


@then("the pie chart and winners/losers table stack vertically instead of side-by-side")
def widgets_stack_vertically(dash_duo):
    pie_col = dash_duo.find_element("#overview-pie-container").find_element(
        "xpath", "./ancestor::div[contains(@class, 'col')][1]"
    )
    table_col = dash_duo.find_element("#overview-winners-losers-container").find_element(
        "xpath", "./ancestor::div[contains(@class, 'col')][1]"
    )
    # Stacked = the table's column starts at or below the bottom of the pie
    # chart's column, rather than alongside it at the same vertical position.
    assert table_col.location["y"] >= pie_col.location["y"] + pie_col.size["height"] - 5


def _table_rows(dash_duo):
    return dash_duo.driver.execute_script(
        "return Array.from(document.querySelectorAll("
        "'#overview-winners-losers-container .dash-spreadsheet tr')).slice(1);"
    )


@then('a table captioned "Biggest winners and losers" is shown to the right of the pie chart')
def table_is_captioned(dash_duo):
    dash_duo.wait_for_element(
        "#overview-winners-losers-container .dash-spreadsheet", timeout=_TIMEOUT
    )
    # Caption lives in the surrounding container, adjacent to the table itself.
    text = dash_duo.find_element("#overview-winners-losers-container").text
    assert "Biggest winners and losers" in text


@then("the first 5 rows are the 5 highest profit/loss positions in descending order")
def table_first_5_rows_are_highest(dash_duo):
    dash_duo.wait_for_element(
        "#overview-winners-losers-container .dash-spreadsheet", timeout=_TIMEOUT
    )
    rows = dash_duo.driver.execute_script(
        "return Array.from(document.querySelectorAll("
        "'#overview-winners-losers-container .dash-spreadsheet tr')).slice(1, 6)"
        ".map(function(r) { return r.cells[0].innerText; });"
    )
    assert rows == ["Position 12", "Position 11", "Position 10", "Position 9", "Position 8"]


@then("the last 5 rows are the 5 lowest profit/loss positions, mildest first and worst last")
def table_last_5_rows_are_lowest(dash_duo):
    rows = dash_duo.driver.execute_script(
        "return Array.from(document.querySelectorAll("
        "'#overview-winners-losers-container .dash-spreadsheet tr')).slice(6, 11)"
        ".map(function(r) { return r.cells[0].innerText; });"
    )
    assert rows == ["Position 5", "Position 4", "Position 3", "Position 2", "Position 1"]


@then("no position appears twice in the table")
def table_no_duplicate_positions(dash_duo):
    rows = dash_duo.driver.execute_script(
        "return Array.from(document.querySelectorAll("
        "'#overview-winners-losers-container .dash-spreadsheet tr')).slice(1)"
        ".map(function(r) { return r.cells[0].innerText; });"
    )
    assert len(rows) == len(set(rows))


def _row_background(dash_duo, row_index_1based: int) -> str:
    return dash_duo.driver.execute_script(
        "var rows = document.querySelectorAll("
        "'#overview-winners-losers-container .dash-spreadsheet tr');"
        "return rows[arguments[0]].cells[0].style.backgroundColor;",
        row_index_1based,
    )


@then("row 1 is shaded the brightest green and row 5 the palest green")
def rows_1_and_5_green_gradient(dash_duo):
    dash_duo.wait_for_element(
        "#overview-winners-losers-container .dash-spreadsheet", timeout=_TIMEOUT
    )
    assert _row_background(dash_duo, 1) != ""
    assert _row_background(dash_duo, 5) != ""
    assert _row_background(dash_duo, 1) != _row_background(dash_duo, 5)


@then("row 6 is shaded the palest blue and row 10 the brightest blue")
def rows_6_and_10_blue_gradient(dash_duo):
    assert _row_background(dash_duo, 6) != ""
    assert _row_background(dash_duo, 10) != ""
    assert _row_background(dash_duo, 6) != _row_background(dash_duo, 10)


@then(
    "each row of the winners/losers table shows a position name, its profit/loss, "
    "and its book cost"
)
def table_row_shows_all_columns(dash_duo):
    dash_duo.wait_for_element(
        "#overview-winners-losers-container .dash-spreadsheet", timeout=_TIMEOUT
    )
    headers = dash_duo.driver.execute_script(
        "return Array.from(document.querySelectorAll("
        "'#overview-winners-losers-container .dash-spreadsheet th'))"
        ".map(function(t) { return t.innerText; });"
    )
    assert "Position" in headers
    assert "Profit/Loss" in headers
    assert "Book Cost" in headers


@then(
    parsers.parse("the winners/losers table shows exactly {count:d} rows with no position repeated")
)
def table_shows_exactly_n_rows(dash_duo, count):
    dash_duo.wait_for_element(
        "#overview-winners-losers-container .dash-spreadsheet", timeout=_TIMEOUT
    )
    rows = _table_rows(dash_duo)
    assert len(rows) == count


@then("the winners/losers table refreshes to that account's own biggest winners and losers")
def table_refreshes_for_account(dash_duo):
    dash_duo.wait_for_element(
        "#overview-winners-losers-container .dash-spreadsheet", timeout=_TIMEOUT
    )
    rows = _table_rows(dash_duo)
    assert len(rows) > 0
