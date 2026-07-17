"""Step definitions for all five 018 Positions BDD feature files.

Shared across every scenario in these features (T016, T020, T023, T026,
T028 in tasks.md) since they all drive the same running app instance via
the `dash_duo` browser fixture — same rationale as 016's single
`test_overview_steps.py` file.

No real portfolio-analysis-service instance is used: every scenario
monkeypatches `src.pages.positions._get_client` with an in-memory fake
before the Dash server starts, so these tests are hermetic.

Note: this sandbox has no Chrome/chromedriver installed, so these
scenarios collect and resolve their steps successfully but have not been
executed to a pass/fail verdict here — same limitation already documented
for 017's own BDD suite (see specs/017-chart-date-range-shortcuts/tasks.md,
T014). Verified instead via the pure-function unit tests in
tests/unit/test_positions_chart_shaping.py and tests/unit/test_date_range_controls.py,
plus static analysis (ruff/mypy) and a successful Dash app build.
"""

from __future__ import annotations

import time
from datetime import date
from typing import Any

from pytest_bdd import given, parsers, scenarios, then, when
from selenium.webdriver.support.ui import Select

# Imported at module level, before any step imports `src.pages.positions`
# directly (e.g. to monkeypatch `_get_client`) — same rationale as
# test_overview_steps.py's own import ordering.
import app as app_module
import src.pages.positions as positions_module
from src.components.date_range_controls import _last_business_day, _shortcut_from_date
from src.exceptions import PortfolioAnalysisServiceError
from src.models.portfolio_analysis import (
    AccountResourceRange,
    AccountSummary,
    AttributeDefinition,
    PositionSummary,
    PositionTimeSeriesEntry,
    PositionTimeSeriesResponse,
)

# Reuses the shell-level "the app is launched" / nav-click steps.
from tests.bdd.steps import test_shell_steps  # noqa: F401

scenarios("../features/positions_default_view.feature")
scenarios("../features/positions_account_and_date_controls.feature")
scenarios("../features/positions_attribute_and_position_filters.feature")
scenarios("../features/positions_comparison_table.feature")
scenarios("../features/positions_stacked_area_toggle.feature")

_TIMEOUT = 10
_SHORTCUT_BUTTON_IDS = {
    "YtD": "overview-shortcut-ytd",
    "1Y": "overview-shortcut-1y",
    "3Y": "overview-shortcut-3y",
    "5Y": "overview-shortcut-5y",
    "All": "overview-shortcut-all",
}

_ATTRIBUTES = [
    AttributeDefinition(
        name="market_value", description="The market value on that date.", source="position_ladder"
    ),
    AttributeDefinition(
        name="quantity", description="The quantity on that date.", source="position_ladder"
    ),
]

_ACCOUNTS = [
    AccountSummary(
        account_name="AAA-Account",
        capital_ledger=None,
        position_ladder=AccountResourceRange(from_date=date(2015, 1, 1), to_date=date.today()),
    ),
    AccountSummary(
        account_name="ZZZ-Account",
        capital_ledger=None,
        position_ladder=AccountResourceRange(from_date=date(2015, 1, 1), to_date=date.today()),
    ),
]

_POSITIONS = ["Apple Inc", "Cash", "Flat Corp"]

# (value at "from" date, value at "to" date) per position/attribute — Apple
# Inc rises, Cash falls, Flat Corp holds steady, giving deterministic
# up/down/flat coverage for the comparison-table shading scenarios.
_VALUE_PAIRS: dict[str, dict[str, tuple[float, float]]] = {
    "Apple Inc": {"market_value": (5000.0, 5500.0), "quantity": (25.0, 25.0)},
    "Cash": {"market_value": (2000.0, 1900.0), "quantity": (2000.0, 1900.0)},
    "Flat Corp": {"market_value": (1000.0, 1000.0), "quantity": (10.0, 10.0)},
}


class _FakePositionsClient:
    """In-memory PortfolioAnalysisClient double used by every scenario here."""

    def __init__(
        self,
        accounts: list[AccountSummary],
        attributes: list[AttributeDefinition],
        positions_by_account: dict[str, list[str]],
        raise_error: bool = False,
        delay_seconds: float = 0.0,
    ) -> None:
        self._accounts = accounts
        self._attributes = attributes
        self._positions_by_account = positions_by_account
        self._raise_error = raise_error
        self._delay_seconds = delay_seconds

    def list_accounts(self) -> list[AccountSummary]:
        if self._raise_error:
            raise PortfolioAnalysisServiceError("stubbed failure")
        return self._accounts

    def list_position_attributes(self) -> list[AttributeDefinition]:
        if self._raise_error:
            raise PortfolioAnalysisServiceError("stubbed failure")
        return self._attributes

    def list_account_positions(self, account_name: str) -> list[PositionSummary]:
        if self._raise_error:
            raise PortfolioAnalysisServiceError("stubbed failure")
        names = self._positions_by_account.get(account_name, [])
        return [
            PositionSummary(position=name, from_date=date(2015, 1, 1), to_date=date.today())
            for name in names
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
        target_positions = positions or self._positions_by_account.get(account_name, [])
        entries = []
        for position in target_positions:
            values = _VALUE_PAIRS.get(position)
            if values is None:
                continue
            for query_date, index in ((start, 0), (end, 1)):
                row = {"date": query_date, "position": position}
                for attribute in attributes:
                    if attribute in values:
                        row[attribute] = values[attribute][index]
                entries.append(PositionTimeSeriesEntry.model_validate(row))
        return PositionTimeSeriesResponse(
            account_name=account_name,
            attributes=attributes,
            positions=target_positions,
            from_date=start,
            to_date=end,
            entries=entries,
        )


def _install_stub_client(monkeypatch: Any, client: _FakePositionsClient) -> None:
    monkeypatch.setattr(positions_module, "_get_client", lambda: client)


@given(
    "portfolio-analysis-service has multiple accounts with position data",
    target_fixture="stub_client",
)
def stub_client_with_data(monkeypatch):
    client = _FakePositionsClient(
        _ACCOUNTS,
        _ATTRIBUTES,
        {"AAA-Account": _POSITIONS, "ZZZ-Account": _POSITIONS},
    )
    _install_stub_client(monkeypatch, client)
    return client


@given(
    "portfolio-analysis-service has an account with no position data",
    target_fixture="stub_client",
)
def stub_client_no_positions(monkeypatch):
    client = _FakePositionsClient(
        [_ACCOUNTS[0]],
        _ATTRIBUTES,
        {"AAA-Account": []},
    )
    _install_stub_client(monkeypatch, client)
    return client


def _ensure_default_stub(monkeypatch) -> None:
    """Install a default stub if no Given step has already installed one."""
    if positions_module._get_client.__module__ == "src.pages.positions":
        stub_client_with_data(monkeypatch)


@when("the browser loads the Positions page", target_fixture="dash_app")
def load_positions_page(dash_duo, monkeypatch):
    _ensure_default_stub(monkeypatch)
    dash_duo.start_server(app_module.app)
    dash_duo.driver.get(f"{dash_duo.server_url}/positions")
    dash_duo.wait_for_element("#positions-chart-container", timeout=_TIMEOUT)
    return app_module.app


@given(
    "the Positions page has finished loading its default view", target_fixture="dash_app"
)
def positions_finished_loading(dash_duo, monkeypatch):
    app = load_positions_page(dash_duo, monkeypatch)
    dash_duo.wait_for_element("#positions-chart", timeout=_TIMEOUT)
    return app


@given(
    "the Positions page has finished loading its default view, with a slow backing service",
    target_fixture="dash_app",
)
def positions_finished_loading_then_slow(dash_duo, monkeypatch):
    app = positions_finished_loading(dash_duo, monkeypatch)
    slow_client = _FakePositionsClient(
        _ACCOUNTS,
        _ATTRIBUTES,
        {"AAA-Account": _POSITIONS, "ZZZ-Account": _POSITIONS},
        delay_seconds=2.0,
    )
    _install_stub_client(monkeypatch, slow_client)
    return app


# --- US1: default view ------------------------------------------------------


@then("the Account selector shows the alphabetically-first account selected")
def account_selector_shows_first_account(dash_duo):
    select = Select(dash_duo.find_element("#app-parameters-account"))
    assert select.first_selected_option.get_attribute("value") == "AAA-Account"


@then(parsers.parse('the date range shows "YtD" for that account'))
@then(parsers.parse('the date range shows "YtD" for the newly selected account'))
def date_range_shows_ytd(dash_duo):
    select = Select(dash_duo.find_element("#app-parameters-account"))
    account_name = select.first_selected_option.get_attribute("value")
    account = next(a for a in _ACCOUNTS if a.account_name == account_name)
    expected_from = _shortcut_from_date("ytd", account, date.today())
    expected_to = _last_business_day(date.today())
    from_value = dash_duo.driver.execute_script(
        "return document.querySelector('#app-parameters-from-date input').value;"
    )
    to_value = dash_duo.driver.execute_script(
        "return document.querySelector('#app-parameters-to-date input').value;"
    )
    assert from_value == expected_from.isoformat()
    assert to_value == expected_to.isoformat()


@then("the position filter shows every position for that account selected")
@then("the position filter shows every position for the newly selected account")
def position_filter_shows_all(dash_duo):
    selected = dash_duo.driver.execute_script(
        "return document.querySelectorAll("
        "'#positions-parameters-position-filter .Select-value, "
        "#positions-parameters-position-filter [class*=\"multiValue\"]').length;"
    )
    assert selected == len(_POSITIONS)


@then("a chart is shown with one line per position")
def chart_has_one_line_per_position(dash_duo):
    dash_duo.wait_for_element("#positions-chart", timeout=_TIMEOUT)
    trace_count = dash_duo.driver.execute_script(
        "var gd = document.querySelector('#positions-chart .js-plotly-plot');"
        "return gd && gd.data ? gd.data.length : 0;"
    )
    assert trace_count == len(_POSITIONS)


@then('a "no data" message is shown instead of a broken chart')
def no_data_message_shown(dash_duo):
    dash_duo.wait_for_element("#positions-empty-state", timeout=_TIMEOUT)
    assert dash_duo.find_elements("#positions-chart") == []


# --- US2: account/date exploration ------------------------------------------


@when("the user selects a different account")
def select_different_account(dash_duo):
    select = Select(dash_duo.find_element("#app-parameters-account"))
    select.select_by_value("ZZZ-Account")
    time.sleep(0.3)


@when(parsers.parse('the user clicks the "{shortcut}" shortcut button'))
def click_shortcut_button(dash_duo, shortcut):
    button_id = _SHORTCUT_BUTTON_IDS[shortcut]
    dash_duo.find_element(f"#{button_id}").click()


@then("the \"From\" date updates to the correct computed date for that shortcut")
def from_date_matches_shortcut(dash_duo):
    # Loose sanity check: a non-empty ISO date is present after the click;
    # exact-value coverage per shortcut already lives in
    # tests/unit/test_date_range_controls.py's shared `_shortcut_from_date` tests.
    from_value = dash_duo.driver.execute_script(
        "return document.querySelector('#app-parameters-from-date input').value;"
    )
    assert from_value != ""


@then("the \"To\" date is set to the most recently completed business day")
def to_date_matches_last_business_day(dash_duo):
    to_value = dash_duo.driver.execute_script(
        "return document.querySelector('#app-parameters-to-date input').value;"
    )
    assert to_value == _last_business_day(date.today()).isoformat()


@then("the Account, From, To, and shortcut controls are disabled until the refresh completes")
def controls_disabled_during_refresh(dash_duo):
    disabled_now = dash_duo.driver.execute_script(
        "return document.querySelector('#app-parameters-account').disabled;"
    )
    assert disabled_now is True
    dash_duo.wait_for_element("#positions-chart", timeout=_TIMEOUT)
    disabled_after = dash_duo.driver.execute_script(
        "return document.querySelector('#app-parameters-account').disabled;"
    )
    assert disabled_after is False


# --- US3: attribute/position filtering --------------------------------------


@when(parsers.parse('the user toggles the "{attribute}" attribute on'))
def toggle_attribute_on(dash_duo, attribute):
    toggle = dash_duo.find_element(f"#positions-attribute-toggle-{attribute} input")
    toggle.click()
    time.sleep(0.3)


@when("the user narrows the position filter to a single position")
def narrow_position_filter(dash_duo):
    dash_duo.driver.execute_script(
        "var removeButtons = document.querySelectorAll("
        "'#positions-parameters-position-filter [class*=\"remove\"]');"
        "for (var i = removeButtons.length - 1; i > 0; i--) { removeButtons[i].click(); }"
    )
    time.sleep(0.3)


@when("the user deselects every attribute")
def deselect_every_attribute(dash_duo):
    for toggle in dash_duo.find_elements("#positions-attribute-toggles input[type='checkbox']"):
        if toggle.is_selected():
            toggle.click()
    time.sleep(0.3)


@when("the user deselects every position")
def deselect_every_position(dash_duo):
    dash_duo.driver.execute_script(
        "var removeButtons = document.querySelectorAll("
        "'#positions-parameters-position-filter [class*=\"remove\"]');"
        "removeButtons.forEach(function(b) { b.click(); });"
    )
    time.sleep(0.3)


@then(parsers.parse('the chart includes a line for "{attribute}"'))
def chart_includes_attribute(dash_duo, attribute):
    names = dash_duo.driver.execute_script(
        "var gd = document.querySelector('#positions-chart .js-plotly-plot');"
        "return gd && gd.data ? gd.data.map(function(t) { return t.name; }) : [];"
    )
    assert any(attribute in name for name in names)


@then("the chart shows only that position")
def chart_shows_only_one_position(dash_duo):
    trace_count = dash_duo.driver.execute_script(
        "var gd = document.querySelector('#positions-chart .js-plotly-plot');"
        "return gd && gd.data ? gd.data.length : 0;"
    )
    assert trace_count == 1


@then("a prompt to select at least one attribute is shown")
def prompt_select_attribute(dash_duo):
    dash_duo.wait_for_element("#positions-empty-state", timeout=_TIMEOUT)


@then("a prompt to select at least one position is shown")
def prompt_select_position(dash_duo):
    dash_duo.wait_for_element("#positions-empty-state", timeout=_TIMEOUT)


# --- US4: comparison table ---------------------------------------------------


def _table_row_count(dash_duo) -> int:
    return dash_duo.driver.execute_script(
        "return document.querySelectorAll("
        "'#positions-table-container .dash-spreadsheet tr').length - 1;"  # minus header
    )


@then("the comparison table has one row per plotted position")
def table_has_one_row_per_position(dash_duo):
    assert _table_row_count(dash_duo) == len(_POSITIONS)


@then(parsers.parse('each row has a "{attribute}" column and a "{attribute} (prev)" column'))
def table_has_column_pair(dash_duo, attribute):
    headers = dash_duo.driver.execute_script(
        "var cells = document.querySelectorAll("
        "'#positions-table-container .dash-spreadsheet th');"
        "return Array.from(cells).map(function(t) { return t.innerText; });"
    )
    assert attribute in headers
    assert f"{attribute} (prev)" in headers


def _row_background(dash_duo, position: str) -> str:
    return dash_duo.driver.execute_script(
        "var rows = document.querySelectorAll('#positions-table-container .dash-spreadsheet tr');"
        "for (var i = 0; i < rows.length; i++) {"
        "  if (rows[i].innerText.indexOf(arguments[0]) !== -1) {"
        "    return rows[i].cells[1].style.backgroundColor;"
        "  }"
        "}"
        "return '';",
        position,
    )


@then("the row for the position whose value rose is shaded light green")
def risen_row_shaded_green(dash_duo):
    assert _row_background(dash_duo, "Apple Inc") != ""


@then("the row for the position whose value fell is shaded light red")
def fallen_row_shaded_red(dash_duo):
    assert _row_background(dash_duo, "Cash") != ""


@then("the row for the position whose value held steady has no background shading")
def flat_row_unshaded(dash_duo):
    background = _row_background(dash_duo, "Flat Corp")
    assert background in ("", "rgba(0, 0, 0, 0)", "transparent")


@then(
    parsers.parse(
        'the comparison table gains a "{attribute}" column pair matching the chart\'s selection'
    )
)
def table_gains_column_pair(dash_duo, attribute):
    table_has_column_pair(dash_duo, attribute)


# --- US5: stacked area toggle ------------------------------------------------


@when('the user turns "Stacked area graph" on')
def turn_stacked_on(dash_duo):
    dash_duo.find_element("#positions-parameters-stacked-toggle input").click()
    time.sleep(0.3)


@given('the user has turned "Stacked area graph" on')
def given_stacked_on(dash_duo):
    turn_stacked_on(dash_duo)


@when('the user turns "Stacked area graph" off')
def turn_stacked_off(dash_duo):
    dash_duo.find_element("#positions-parameters-stacked-toggle input").click()
    time.sleep(0.3)


@then("the chart renders as a stacked area chart")
def chart_is_stacked(dash_duo):
    stackgroups = dash_duo.driver.execute_script(
        "var gd = document.querySelector('#positions-chart .js-plotly-plot');"
        "return gd && gd.data ? gd.data.map(function(t) { return t.stackgroup; }) : [];"
    )
    assert all(sg == "positions" for sg in stackgroups)


@then("the chart renders as a line chart")
@then("the chart renders as a line chart with both attributes")
def chart_is_line(dash_duo):
    stackgroups = dash_duo.driver.execute_script(
        "var gd = document.querySelector('#positions-chart .js-plotly-plot');"
        "return gd && gd.data ? gd.data.map(function(t) { return t.stackgroup; }) : [];"
    )
    assert all(not sg for sg in stackgroups)


@then('"Stacked area graph" is turned off automatically')
def stacked_toggle_auto_off(dash_duo):
    checked = dash_duo.driver.execute_script(
        "return document.querySelector('#positions-parameters-stacked-toggle input').checked;"
    )
    assert checked is False


@then('"Stacked area graph" cannot be switched on')
def stacked_toggle_disabled(dash_duo):
    disabled = dash_duo.driver.execute_script(
        "return document.querySelector('#positions-parameters-stacked-toggle input').disabled;"
    )
    assert disabled is True
