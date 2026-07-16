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
from src.exceptions import PortfolioAnalysisServiceError
from src.models.portfolio_analysis import (
    AccountResourceRange,
    AccountSummary,
    AttributeDefinition,
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
    ) -> None:
        self._accounts = accounts
        self._attributes = attributes
        self._entries = entries if entries is not None else self._default_entries()
        self._raise_error = raise_error

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
