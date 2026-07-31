"""Step definitions for the Performance page BDD feature files (020).

No real portfolio-analysis-service instance is used: every scenario
monkeypatches `src.pages.performance._get_client` with an in-memory fake
before the Dash server starts, mirroring
tests/bdd/steps/test_overview_steps.py's own `_FakeClient` pattern.
"""

from __future__ import annotations

import time
from datetime import date, timedelta
from typing import Any

from pytest_bdd import given, parsers, scenarios, then, when
from selenium.webdriver.support.ui import Select

# Imported at module level, before any step imports `src.pages.performance`
# directly — `app`'s own import constructs the Dash app via
# `Dash(use_pages=True, ...)`, which is what lets `dash.register_page()`
# inside performance.py succeed.
import app as app_module
import src.pages.performance as performance_module
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
    TimeSeriesEntry,
    TimeSeriesResponse,
)

scenarios("../features/performance_default_view.feature")
scenarios("../features/performance_account_and_date_controls.feature")
scenarios("../features/performance_measure_toggles.feature")

_ATTRIBUTES = [
    AttributeDefinition(
        name="ITD", description="Inception to Date return.", source="position_ladder"
    ),
    AttributeDefinition(
        name="ITD (Ann.)", description="ITD, annualized.", source="position_ladder"
    ),
    AttributeDefinition(name="1Y", description="Trailing 1-year return.", source="position_ladder"),
    AttributeDefinition(name="3Y", description="Trailing 3-year return.", source="position_ladder"),
    AttributeDefinition(name="5Y", description="Trailing 5-year return.", source="position_ladder"),
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


class _FakePerformanceClient:
    """In-memory PortfolioAnalysisClient double used by every scenario here."""

    def __init__(
        self,
        accounts: list[AccountSummary],
        attributes: list[AttributeDefinition],
        entries: list[dict[str, Any]] | None = None,
        raise_on_mount: bool = False,
        raise_on_chart: bool = False,
        delay_seconds: float = 0.0,
    ) -> None:
        self._accounts = accounts
        self._attributes = attributes
        self._entries = entries if entries is not None else self._default_entries()
        self._raise_on_mount = raise_on_mount
        self._raise_on_chart = raise_on_chart
        self._delay_seconds = delay_seconds

    @staticmethod
    def _default_entries() -> list[dict[str, Any]]:
        base = date(2024, 1, 2)
        return [
            {"date": base + timedelta(days=i), "ITD": 0.10 + i * 0.01, "1Y": 0.05 + i * 0.005}
            for i in range(5)
        ]

    def list_accounts(self) -> list[AccountSummary]:
        if self._raise_on_mount:
            raise PortfolioAnalysisServiceError("stubbed failure")
        return self._accounts

    def list_performance_attributes(self) -> list[AttributeDefinition]:
        if self._raise_on_mount:
            raise PortfolioAnalysisServiceError("stubbed failure")
        return self._attributes

    def get_performance(
        self, account_name: str, attributes: list[str], start: date, end: date
    ) -> TimeSeriesResponse:
        if self._delay_seconds:
            time.sleep(self._delay_seconds)
        if self._raise_on_chart:
            raise PortfolioAnalysisServiceError("stubbed failure")
        entries = [
            TimeSeriesEntry.model_validate(
                {"date": e["date"], **{a: e[a] for a in attributes if a in e}}
            )
            for e in self._entries
        ]
        return TimeSeriesResponse(
            account_name=account_name,
            attributes=attributes,
            from_date=start,
            to_date=end,
            entries=entries,
        )


def _install_stub_client(monkeypatch: Any, client: _FakePerformanceClient) -> None:
    monkeypatch.setattr(performance_module, "_get_client", lambda: client)


@given(
    "portfolio-analysis-service has multiple accounts with recorded performance history",
    target_fixture="stub_client",
)
def stub_client_with_data(monkeypatch):
    client = _FakePerformanceClient(_ACCOUNTS, _ATTRIBUTES)
    _install_stub_client(monkeypatch, client)
    return client


@given(
    "portfolio-analysis-service has an account with no recorded performance data",
    target_fixture="stub_client",
)
def stub_client_with_no_entries(monkeypatch):
    client = _FakePerformanceClient(_ACCOUNTS, _ATTRIBUTES, entries=[])
    _install_stub_client(monkeypatch, client)
    return client


@given(
    "portfolio-analysis-service is unavailable for account/measure lookups",
    target_fixture="stub_client",
)
def stub_client_mount_unavailable(monkeypatch):
    client = _FakePerformanceClient(_ACCOUNTS, _ATTRIBUTES, raise_on_mount=True)
    _install_stub_client(monkeypatch, client)
    return client


@given(
    "portfolio-analysis-service is unavailable for performance data",
    target_fixture="stub_client",
)
def stub_client_chart_unavailable(monkeypatch):
    client = _FakePerformanceClient(_ACCOUNTS, _ATTRIBUTES, raise_on_chart=True)
    _install_stub_client(monkeypatch, client)
    return client


def _ensure_default_stub(monkeypatch) -> None:
    """Install a default stub if no Given step has already installed one."""
    if performance_module._get_client.__module__ == "src.pages.performance":
        stub_client_with_data(monkeypatch)


@when(
    "the browser loads the Performance page and its chart finishes loading",
    target_fixture="dash_app",
)
def load_performance_page_with_data(dash_duo, monkeypatch):
    _ensure_default_stub(monkeypatch)
    dash_duo.start_server(app_module.app)
    dash_duo.driver.get(f"{dash_duo.server_url}/performance")
    dash_duo.wait_for_element("#performance-chart-container", timeout=_TIMEOUT)
    # One of the three end states must appear — success, empty, or error —
    # rather than the initial "Loading account performance…" placeholder.
    dash_duo.wait_for_element(
        "#performance-chart, #performance-empty-state, #performance-error-state",
        timeout=_TIMEOUT,
    )
    return app_module.app


@given(
    "the Performance page has finished loading its default chart", target_fixture="dash_app"
)
def performance_finished_loading(dash_duo, monkeypatch):
    app = load_performance_page_with_data(dash_duo, monkeypatch)
    dash_duo.wait_for_element("#performance-chart", timeout=_TIMEOUT)
    return app


@then("the Account selector shows the alphabetically-first account selected")
def account_selector_shows_first_account(dash_duo):
    select = Select(dash_duo.find_element("#app-parameters-account"))
    assert select.first_selected_option.get_attribute("value") == "AAA-ISA"


@then("the date range covers that account's full recorded history")
def date_range_covers_full_history(dash_duo, stub_client):
    from_date_value = dash_duo.driver.execute_script(
        "return document.querySelector('#app-parameters-from-date input').value;"
    )
    account = next(a for a in stub_client._accounts if a.account_name == "AAA-ISA")
    assert from_date_value == account.capital_ledger.from_date.isoformat()


@then("a line chart is displayed automatically showing the first returned performance measure")
def chart_shows_first_measure(dash_duo):
    dash_duo.wait_for_element("#performance-chart", timeout=_TIMEOUT)
    toggle = dash_duo.find_element("#performance-attribute-toggle-ITD input")
    assert toggle.is_selected()


@then('a "no data" message is shown instead of a broken chart')
def no_data_message_shown(dash_duo):
    dash_duo.wait_for_element("#performance-empty-state", timeout=_TIMEOUT)


@then("an error-state message is shown instead of a chart or an indefinite loading spinner")
def error_state_shown(dash_duo):
    dash_duo.wait_for_element("#performance-error-state", timeout=_TIMEOUT)


# --- US2: explore a different account or time period -----------------------


@when("the user selects a different account")
def select_different_account(dash_duo):
    select = Select(dash_duo.find_element("#app-parameters-account"))
    select.select_by_value("ZZZ-SIPP")
    dash_duo.wait_for_element("#performance-chart", timeout=_TIMEOUT)


@then("the chart updates to show that account's performance data")
def chart_updates_for_account(dash_duo):
    select = Select(dash_duo.find_element("#app-parameters-account"))
    assert select.first_selected_option.get_attribute("value") == "ZZZ-SIPP"
    dash_duo.wait_for_element("#performance-chart", timeout=_TIMEOUT)


@then("the \"from\" date defaults to that account's earliest recorded date")
def from_date_defaults_to_account_earliest(dash_duo, stub_client):
    account_select = Select(dash_duo.find_element("#app-parameters-account"))
    selected_name = account_select.first_selected_option.get_attribute("value")
    selected_account = next(a for a in stub_client._accounts if a.account_name == selected_name)
    from_date_value = dash_duo.driver.execute_script(
        "return document.querySelector('#app-parameters-from-date input').value;"
    )
    assert from_date_value == _earliest_from_date(selected_account).isoformat()


_SHORTCUT_BUTTON_IDS = {
    "ITD": "overview-shortcut-ytd",
    "1Y": "overview-shortcut-1y",
    "3Y": "overview-shortcut-3y",
    "5Y": "overview-shortcut-5y",
    "All": "overview-shortcut-all",
}


@when(parsers.parse('the user clicks the "{label}" shortcut button'))
def click_shortcut_button(dash_duo, label):
    button_id = _SHORTCUT_BUTTON_IDS[label]
    dash_duo.find_element(f"#{button_id}").click()
    dash_duo.wait_for_element("#performance-chart", timeout=_TIMEOUT)


@then("the \"from\" date is set to that account's earliest recorded date")
def from_date_matches_account_earliest(dash_duo, stub_client):
    account_select = Select(dash_duo.find_element("#app-parameters-account"))
    selected_name = account_select.first_selected_option.get_attribute("value")
    selected_account = next(a for a in stub_client._accounts if a.account_name == selected_name)
    from_date_value = dash_duo.driver.execute_script(
        "return document.querySelector('#app-parameters-from-date input').value;"
    )
    assert from_date_value == _earliest_from_date(selected_account).isoformat()


@then(parsers.parse('the "from" date is set to exactly {years:d} years before today'))
def from_date_is_years_before_today(dash_duo, years):
    from_date_value = dash_duo.driver.execute_script(
        "return document.querySelector('#app-parameters-from-date input').value;"
    )
    assert from_date_value == _years_before(date.today(), years).isoformat()


@then("the \"to\" date is set to the most recently completed business day")
def to_date_is_set_to_last_business_day(dash_duo):
    to_date_value = dash_duo.driver.execute_script(
        "return document.querySelector('#app-parameters-to-date input').value;"
    )
    assert to_date_value == _last_business_day(date.today()).isoformat()


@then("the chart refreshes to show only data within that range")
def chart_refreshes_to_range(dash_duo):
    dash_duo.wait_for_element("#performance-chart", timeout=_TIMEOUT)


@given(
    "portfolio-analysis-service takes a moment to respond with performance data",
    target_fixture="stub_client",
)
def stub_client_with_delay(monkeypatch):
    client = _FakePerformanceClient(_ACCOUNTS, _ATTRIBUTES, delay_seconds=1.0)
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
    dash_duo.wait_for_element("#performance-chart", timeout=_TIMEOUT)
    for button_id in _SHORTCUT_BUTTON_IDS.values():
        button = dash_duo.find_element(f"#{button_id}")
        assert button.get_attribute("disabled") is None


# --- US3: choose which return measures to display ---------------------------


def _turn_on_measure(dash_duo, measure: str) -> None:
    toggle = dash_duo.find_element(f"#performance-attribute-toggle-{measure} input")
    if not toggle.is_selected():
        toggle.click()
    dash_duo.wait_for_element("#performance-chart", timeout=_TIMEOUT)


@when(parsers.parse('the user turns on the "{measure}" measure toggle'))
def turn_on_measure(dash_duo, measure):
    _turn_on_measure(dash_duo, measure)


@when(parsers.parse('the user turns off the "{measure}" measure toggle'))
def turn_off_measure(dash_duo, measure):
    toggle = dash_duo.find_element(f"#performance-attribute-toggle-{measure} input")
    if toggle.is_selected():
        toggle.click()


@when("the user turns off every measure toggle")
def turn_off_every_measure(dash_duo):
    for switch in dash_duo.find_elements(
        "#performance-attribute-toggles input[type='checkbox']"
    ):
        if switch.is_selected():
            switch.click()
    dash_duo.wait_for_element("#performance-empty-state", timeout=_TIMEOUT)


@then(
    parsers.parse('the chart shows a line for "{second}" in a distinct color from "{first}"')
)
def chart_shows_distinct_colors(dash_duo, second, first):
    colors = dash_duo.driver.execute_script(
        "var gd = document.querySelector('#performance-chart .js-plotly-plot');"
        "return gd.data.map(function(t) { return [t.name, t.line.color]; });"
    )
    color_map = dict(colors)
    assert first in color_map and second in color_map
    assert color_map[first] != color_map[second]


@then(parsers.parse('the legend lists both "{first}" and "{second}"'))
def legend_lists_both(dash_duo, first, second):
    legend_text = dash_duo.driver.execute_script(
        "var el = document.querySelector('#performance-chart .legend');"
        "return el ? el.textContent : '';"
    )
    assert first in legend_text
    assert second in legend_text


@then(parsers.parse('the chart no longer shows a line for "{measure}"'))
def chart_no_longer_shows_measure(dash_duo, measure):
    names = dash_duo.driver.execute_script(
        "var gd = document.querySelector('#performance-chart .js-plotly-plot');"
        "return gd.data.map(function(t) { return t.name; });"
    )
    assert measure not in names


@then(parsers.parse('the chart still shows a line for "{measure}"'))
def chart_still_shows_measure(dash_duo, measure):
    names = dash_duo.driver.execute_script(
        "var gd = document.querySelector('#performance-chart .js-plotly-plot');"
        "return gd.data.map(function(t) { return t.name; });"
    )
    assert measure in names


@then("a prompt to select at least one measure is shown instead of a chart")
def prompt_to_select_measure_shown(dash_duo):
    dash_duo.wait_for_element("#performance-empty-state", timeout=_TIMEOUT)
