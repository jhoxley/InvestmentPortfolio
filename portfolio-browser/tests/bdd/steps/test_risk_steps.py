"""Step definitions for the Risk page BDD feature files (024).

No real portfolio-analysis-service instance is used: every scenario
monkeypatches `src.pages.risk._get_client` with an in-memory fake before the
Dash server starts, mirroring tests/bdd/steps/test_performance_steps.py's own
`_FakeClient` pattern.
"""

from __future__ import annotations

import time
from datetime import date
from typing import Any

from pytest_bdd import given, parsers, scenarios, then, when
from selenium.webdriver.support.ui import Select

# Imported at module level, before any step imports `src.pages.risk`
# directly — `app`'s own import constructs the Dash app via
# `Dash(use_pages=True, ...)`, which is what lets `dash.register_page()`
# inside risk.py succeed.
import app as app_module
import src.pages.risk as risk_module
from src.components.date_range_controls import _earliest_from_date, _years_before
from src.exceptions import PortfolioAnalysisServiceError
from src.models.portfolio_analysis import (
    AccountResourceRange,
    AccountSummary,
    HistogramStatistics,
    ReturnHistogramResponse,
)

scenarios("../features/risk_view_histogram.feature")
scenarios("../features/risk_shortcut_buttons.feature")
scenarios("../features/risk_manual_date_range.feature")

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

_STATISTIC_LABELS = [
    "Count",
    "Mean",
    "Median",
    "Mode",
    "Minimum",
    "Maximum",
    "Std Dev",
    "Skewness",
    "Kurtosis",
]


def _default_statistics() -> HistogramStatistics:
    return HistogramStatistics.model_validate(
        {
            "count": 27,
            "mean": 4.1,
            "median": 3.0,
            "mode": 0,
            "minimum": -25,
            "maximum": 65,
            "std_dev": 14.2,
            "std_dev_bands": [
                {"sigma": 1, "multiple": 14.2, "lower": -10.1, "upper": 18.3},
                {"sigma": 2, "multiple": 28.4, "lower": -24.3, "upper": 32.5},
                {"sigma": 3, "multiple": 42.6, "lower": -38.5, "upper": 46.7},
            ],
            "skewness": 1.8,
            "kurtosis": 6.2,
        }
    )


def _empty_statistics() -> HistogramStatistics:
    return HistogramStatistics.model_validate(
        {
            "count": 0,
            "mean": None,
            "median": None,
            "mode": None,
            "minimum": None,
            "maximum": None,
            "std_dev": None,
            "std_dev_bands": [],
            "skewness": None,
            "kurtosis": None,
        }
    )


class _FakeRiskClient:
    """In-memory PortfolioAnalysisClient double used by every scenario here."""

    def __init__(
        self,
        accounts: list[AccountSummary],
        histogram: list[tuple[int, int]] | None = None,
        statistics: HistogramStatistics | None = None,
        raise_on_mount: bool = False,
        raise_on_chart: bool = False,
        delay_seconds: float = 0.0,
    ) -> None:
        self._accounts = accounts
        self._histogram = histogram if histogram is not None else [(-25, 1), (0, 12), (65, 1)]
        self._statistics = statistics if statistics is not None else _default_statistics()
        self._raise_on_mount = raise_on_mount
        self._raise_on_chart = raise_on_chart
        self._delay_seconds = delay_seconds
        self.calls: list[dict[str, Any]] = []

    def list_accounts(self) -> list[AccountSummary]:
        if self._raise_on_mount:
            raise PortfolioAnalysisServiceError("stubbed failure")
        return self._accounts

    def get_return_histogram(
        self, account_name: str, start: date, end: date
    ) -> ReturnHistogramResponse:
        self.calls.append({"account_name": account_name, "start": start, "end": end})
        if self._delay_seconds:
            time.sleep(self._delay_seconds)
        if self._raise_on_chart:
            raise PortfolioAnalysisServiceError("stubbed failure")
        return ReturnHistogramResponse(
            account_name=account_name,
            from_date=start,
            to_date=end,
            histogram=self._histogram,
            statistics=self._statistics,
            _links={},
        )


def _install_stub_client(monkeypatch: Any, client: _FakeRiskClient) -> None:
    monkeypatch.setattr(risk_module, "_get_client", lambda: client)


@given(
    "portfolio-analysis-service has multiple accounts with recorded return history",
    target_fixture="stub_client",
)
def stub_client_with_data(monkeypatch):
    client = _FakeRiskClient(_ACCOUNTS)
    _install_stub_client(monkeypatch, client)
    return client


@given(
    "portfolio-analysis-service has an account with no recorded return observations",
    target_fixture="stub_client",
)
def stub_client_with_no_observations(monkeypatch):
    client = _FakeRiskClient(_ACCOUNTS, histogram=[], statistics=_empty_statistics())
    _install_stub_client(monkeypatch, client)
    return client


@given(
    "portfolio-analysis-service is unavailable for account lookups",
    target_fixture="stub_client",
)
def stub_client_mount_unavailable(monkeypatch):
    client = _FakeRiskClient(_ACCOUNTS, raise_on_mount=True)
    _install_stub_client(monkeypatch, client)
    return client


@given(
    "portfolio-analysis-service is unavailable for return histogram data",
    target_fixture="stub_client",
)
def stub_client_chart_unavailable(monkeypatch):
    client = _FakeRiskClient(_ACCOUNTS, raise_on_chart=True)
    _install_stub_client(monkeypatch, client)
    return client


@given(
    "portfolio-analysis-service has an account with over ten years of recorded return history",
    target_fixture="stub_client",
)
def stub_client_long_history(monkeypatch):
    account = AccountSummary(
        account_name="LONG-HISTORY",
        capital_ledger=AccountResourceRange(from_date=date(2010, 1, 4), to_date=date(2026, 6, 1)),
        position_ladder=AccountResourceRange(from_date=date(2010, 1, 4), to_date=date(2026, 7, 8)),
    )
    client = _FakeRiskClient([account])
    _install_stub_client(monkeypatch, client)
    return client


@given(
    "portfolio-analysis-service has an account with two years of recorded return history",
    target_fixture="stub_client",
)
def stub_client_short_history(monkeypatch):
    account = AccountSummary(
        account_name="SHORT-HISTORY",
        capital_ledger=AccountResourceRange(from_date=date(2024, 6, 1), to_date=date(2026, 6, 1)),
        position_ladder=AccountResourceRange(from_date=date(2024, 6, 1), to_date=date(2026, 7, 8)),
    )
    client = _FakeRiskClient([account])
    _install_stub_client(monkeypatch, client)
    return client


def _ensure_default_stub(monkeypatch) -> None:
    """Install a default stub if no Given step has already installed one."""
    if risk_module._get_client.__module__ == "src.pages.risk":
        stub_client_with_data(monkeypatch)


@when(
    "the browser loads the Risk page and its content finishes loading",
    target_fixture="dash_app",
)
def load_risk_page_with_data(dash_duo, monkeypatch):
    _ensure_default_stub(monkeypatch)
    dash_duo.start_server(app_module.app)
    dash_duo.driver.get(f"{dash_duo.server_url}/risk")
    dash_duo.wait_for_element("#risk-chart-container", timeout=_TIMEOUT)
    # One of the three end states must appear — success, empty, or error —
    # rather than the initial loading placeholder.
    dash_duo.wait_for_element(
        "#risk-histogram-chart, #risk-empty-state, #risk-error-state",
        timeout=_TIMEOUT,
    )
    return app_module.app


@given("the Risk page has finished loading its default view", target_fixture="dash_app")
def risk_finished_loading(dash_duo, monkeypatch):
    app = load_risk_page_with_data(dash_duo, monkeypatch)
    dash_duo.wait_for_element("#risk-histogram-chart", timeout=_TIMEOUT)
    return app


# --- US1: view histogram and statistics table --------------------------------


@then('the sidebar shows a "Risk" navigation entry')
def sidebar_shows_risk_entry(dash_duo):
    dash_duo.wait_for_element("#app-sidebar-nav-risk", timeout=_TIMEOUT)


@then("a bar chart is displayed with basis-point buckets on the X-axis")
def bar_chart_displayed(dash_duo, stub_client):
    dash_duo.wait_for_element("#risk-histogram-chart", timeout=_TIMEOUT)
    x_values = dash_duo.driver.execute_script(
        "var gd = document.querySelector('#risk-histogram-chart .js-plotly-plot');"
        "return gd.data[0].x;"
    )
    assert [int(v) for v in x_values] == [pair[0] for pair in stub_client._histogram]


@then('a statistics table is displayed with columns headed "statistic" and "value"')
def statistics_table_displayed(dash_duo):
    dash_duo.wait_for_element("#risk-statistics-table", timeout=_TIMEOUT)
    headers = dash_duo.driver.execute_script(
        "return Array.from(document.querySelectorAll("
        "'#risk-statistics-table th')).map(function(th) { return th.textContent.trim(); });"
    )
    assert headers == ["statistic", "value"]


_TABLE_ROW_LABELS_SCRIPT = (
    "return Array.from(document.querySelectorAll('#risk-statistics-table td:first-child'))"
    ".map(function(td) { return td.textContent.trim(); });"
)


@then(
    "the table's rows are exactly count, mean, median, mode, minimum, maximum, std_dev, "
    "skewness, kurtosis in that order"
)
def table_rows_in_order(dash_duo):
    labels = dash_duo.driver.execute_script(_TABLE_ROW_LABELS_SCRIPT)
    assert labels == _STATISTIC_LABELS


@then('the table has no "std_dev_bands" row')
def table_has_no_std_dev_bands_row(dash_duo):
    labels = dash_duo.driver.execute_script(_TABLE_ROW_LABELS_SCRIPT)
    assert not any("std_dev_bands" in label.lower().replace(" ", "_") for label in labels)


@then("the bar chart and the statistics table appear in the same row")
def chart_and_table_in_same_row(dash_duo):
    chart = dash_duo.find_element("#risk-histogram-chart")
    table = dash_duo.find_element("#risk-statistics-table")
    assert abs(chart.location["y"] - table.location["y"]) < 20


@then("the bar chart occupies the majority of that row's width")
def chart_occupies_majority_width(dash_duo):
    chart = dash_duo.find_element("#risk-histogram-chart")
    table = dash_duo.find_element("#risk-statistics-table")
    assert chart.size["width"] > table.size["width"]


@then('a "no data" message is shown instead of a chart or table')
def no_data_message_shown(dash_duo):
    dash_duo.wait_for_element("#risk-empty-state", timeout=_TIMEOUT)


@then("an error-state message is shown instead of a chart or an indefinite loading spinner")
def error_state_shown(dash_duo):
    dash_duo.wait_for_element("#risk-error-state", timeout=_TIMEOUT)


# --- US2: preset range shortcut buttons --------------------------------------

_SHORTCUT_BUTTON_IDS = {
    "10Y": "overview-shortcut-ytd",
    "1Y": "overview-shortcut-1y",
    "3Y": "overview-shortcut-3y",
    "5Y": "overview-shortcut-5y",
    "All": "overview-shortcut-all",
}


@when(parsers.parse('the user clicks the "{label}" shortcut button on the Risk page'))
def click_shortcut_button(dash_duo, label):
    button_id = _SHORTCUT_BUTTON_IDS[label]
    dash_duo.find_element(f"#{button_id}").click()
    dash_duo.wait_for_element("#risk-histogram-chart", timeout=_TIMEOUT)


def _current_from_date(dash_duo) -> str:
    return dash_duo.driver.execute_script(
        "return document.querySelector('#app-parameters-from-date input').value;"
    )


@then(
    parsers.parse('the "from" date on the Risk page is set to exactly {years:d} years before today')
)
def from_date_years_before_today(dash_duo, years):
    assert _current_from_date(dash_duo) == _years_before(date.today(), years).isoformat()


@then("the \"from\" date on the Risk page is set to that account's earliest recorded date")
def from_date_matches_earliest(dash_duo, stub_client):
    account = stub_client._accounts[0]
    assert _current_from_date(dash_duo) == _earliest_from_date(account).isoformat()


@then("the chart and table on the Risk page refresh")
def chart_and_table_refresh(dash_duo):
    dash_duo.wait_for_element("#risk-histogram-chart", timeout=_TIMEOUT)
    dash_duo.wait_for_element("#risk-statistics-table", timeout=_TIMEOUT)


@then("the chart and table on the Risk page refresh with no error shown")
def chart_and_table_refresh_no_error(dash_duo):
    chart_and_table_refresh(dash_duo)
    assert dash_duo.find_elements("#risk-error-state") == []


# --- US3: manual date range editing ------------------------------------------


def _set_date_picker(dash_duo, picker_id: str, value: str) -> None:
    dash_duo.driver.execute_script(
        "var el = document.querySelector(arguments[0]); el.value = arguments[1];"
        "el.dispatchEvent(new Event('change', {bubbles: true}));",
        f"#{picker_id} input",
        value,
    )


@when("the user sets a custom date range on the Risk page")
def set_custom_date_range(dash_duo):
    _set_date_picker(dash_duo, "app-parameters-from-date", "2024-01-02")
    _set_date_picker(dash_duo, "app-parameters-to-date", "2024-06-28")
    dash_duo.wait_for_element("#risk-histogram-chart", timeout=_TIMEOUT)


@then("the chart and table on the Risk page refresh to reflect exactly that custom range")
def chart_and_table_reflect_custom_range(dash_duo, stub_client):
    dash_duo.wait_for_element("#risk-histogram-chart", timeout=_TIMEOUT)
    last_call = stub_client.calls[-1]
    assert last_call["start"] == date(2024, 1, 2)
    assert last_call["end"] == date(2024, 6, 28)


@when("the user selects a different account on the Risk page")
def select_different_account(dash_duo):
    select = Select(dash_duo.find_element("#app-parameters-account"))
    select.select_by_value("ZZZ-SIPP")
    dash_duo.wait_for_element("#risk-histogram-chart", timeout=_TIMEOUT)


@then("the date range on the Risk page resets to that account's own default range")
def date_range_resets_to_default(dash_duo, stub_client):
    account = next(a for a in stub_client._accounts if a.account_name == "ZZZ-SIPP")
    assert _current_from_date(dash_duo) == _earliest_from_date(account).isoformat()


@then("the chart and table on the Risk page refresh for the newly selected account")
def chart_and_table_refresh_for_new_account(dash_duo, stub_client):
    dash_duo.wait_for_element("#risk-histogram-chart", timeout=_TIMEOUT)
    assert stub_client.calls[-1]["account_name"] == "ZZZ-SIPP"


@when("the user sets an end date that is not after the start date on the Risk page")
def set_invalid_date_range(dash_duo):
    _set_date_picker(dash_duo, "app-parameters-from-date", "2024-06-28")
    _set_date_picker(dash_duo, "app-parameters-to-date", "2024-01-02")


@then("an inline validation message is shown on the Risk page")
def inline_validation_message_shown(dash_duo):
    dash_duo.wait_for_element("#risk-date-validation", timeout=_TIMEOUT)
    message = dash_duo.driver.execute_script(
        "var el = document.querySelector('#risk-date-validation'); return el ? el.textContent : '';"
    )
    assert message.strip() != ""


@then("the chart and table on the Risk page continue showing the most recently valid data")
def chart_and_table_show_last_valid_data(dash_duo):
    dash_duo.wait_for_element("#risk-histogram-chart", timeout=_TIMEOUT)
    dash_duo.wait_for_element("#risk-statistics-table", timeout=_TIMEOUT)
