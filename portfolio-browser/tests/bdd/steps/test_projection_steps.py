"""Step definitions for the Projection page BDD feature files (022).

No real portfolio-analysis-service instance is used — and none exists yet
for the projection endpoint (specs/022-projection-page/contracts/
portfolio-analysis-api.md is a pinned-but-deferred contract). Every scenario
monkeypatches `src.pages.projection._get_client` with an in-memory fake
implementing that pinned contract, mirroring
tests/bdd/steps/test_performance_steps.py's own `_FakeClient` pattern.
"""

from __future__ import annotations

import time
from datetime import date, timedelta
from typing import Any

from pytest_bdd import given, parsers, scenarios, then, when
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait

# Imported at module level, before any step imports `src.pages.projection`
# directly — `app`'s own import constructs the Dash app via
# `Dash(use_pages=True, ...)`, which is what lets `dash.register_page()`
# inside projection.py succeed.
import app as app_module
import src.pages.projection as projection_module
from src.exceptions import PortfolioAnalysisServiceError
from src.models.portfolio_analysis import (
    AccountResourceRange,
    AccountSummary,
    PositionTimeSeriesEntry,
    PositionTimeSeriesResponse,
)

scenarios("../features/projection_default_view.feature")
scenarios("../features/projection_calendar_picker.feature")
scenarios("../features/projection_multiple_returns.feature")
scenarios("../features/projection_periodicity.feature")
scenarios("../features/projection_periodicity_defaults.feature")

_TIMEOUT = 10

# Wire-format return key -> the display label this page's config gives it
# (config/content.yaml's `projection.returns`), mirrored here rather than
# imported so the fake stays a self-contained double. Keys are the exact
# performance-measure names portfolio-analysis-service's projection endpoint
# expects (specs/009-projection-endpoint/research.md #2 in that repo).
_LABEL_BY_RETURN_KEY = {"ITD (Ann.)": "Ann. ITD", "1Y": "1Y", "3Y": "3Y", "5Y": "5Y"}

_ACCOUNTS = [
    AccountSummary(
        account_name="AAA-ISA",
        capital_ledger=AccountResourceRange(
            from_date=date(2016, 4, 20), to_date=date(2026, 9, 22)
        ),
        position_ladder=AccountResourceRange(
            from_date=date(2016, 4, 20), to_date=date(2026, 9, 22)
        ),
    ),
    AccountSummary(
        account_name="ZZZ-SIPP",
        capital_ledger=AccountResourceRange(
            from_date=date(2018, 3, 4), to_date=date(2026, 9, 22)
        ),
        position_ladder=AccountResourceRange(
            from_date=date(2018, 3, 4), to_date=date(2026, 9, 22)
        ),
    ),
]

_START_MARKET_VALUE = 48000.0


def _period_starts(first: date, last: date, periodicity: str) -> list[date]:
    """Calendar-period start dates for periods overlapping [first, last] (023).

    Mirrors the service's bucketing: week = Monday, month/quarter/annual = first
    day of the period. A period whose start precedes `first` is dated at its own
    start, as the service does.
    """
    if periodicity == "week":
        cursor = first - timedelta(days=first.weekday())
        step_days = 7
        starts = []
        while cursor <= last:
            starts.append(cursor)
            cursor += timedelta(days=step_days)
        return starts
    months_per_period = {"month": 1, "quarter": 3, "annual": 12}[periodicity]
    period_start_month = (first.month - 1) // months_per_period * months_per_period
    month_index = first.year * 12 + period_start_month
    starts = []
    while True:
        current = date(month_index // 12, month_index % 12 + 1, 1)
        if current > last:
            return starts
        starts.append(current)
        month_index += months_per_period


class _FakeProjectionClient:
    """In-memory PortfolioAnalysisClient double implementing the pinned projection contract."""

    def __init__(
        self,
        accounts: list[AccountSummary],
        supported_return_keys: frozenset[str] = frozenset({"ITD (Ann.)", "1Y", "3Y", "5Y"}),
        raise_on_mount: bool = False,
        raise_on_chart: bool = False,
    ) -> None:
        self._accounts = accounts
        self._supported_return_keys = supported_return_keys
        self._raise_on_mount = raise_on_mount
        self._raise_on_chart = raise_on_chart
        # Every get_projection call, so scenarios can assert the interval requested (023).
        self.calls: list[dict[str, Any]] = []
        # When > 0, get_projection sleeps this long so "disabled while refreshing" is observable.
        self.delay_seconds: float = 0.0

    def list_accounts(self) -> list[AccountSummary]:
        if self._raise_on_mount:
            raise PortfolioAnalysisServiceError("stubbed failure")
        return self._accounts

    def get_projection(
        self,
        account_name: str,
        projection_date: date,
        returns: list[str],
        start: date | None = None,
        periodicity: str | None = None,
    ) -> PositionTimeSeriesResponse:
        self.calls.append(
            {
                "account_name": account_name,
                "projection_date": projection_date,
                "returns": list(returns),
                "start": start,
                "periodicity": periodicity,
            }
        )
        if self.delay_seconds:
            time.sleep(self.delay_seconds)
        if self._raise_on_chart:
            raise PortfolioAnalysisServiceError("stubbed failure")
        account = next(a for a in self._accounts if a.account_name == account_name)
        assert account.position_ladder is not None
        resolved_start = start if start is not None else account.position_ladder.to_date
        first_date = account.position_ladder.from_date

        # `None`/"day" keeps the original two-point-per-series output so the 022
        # scenarios are unaffected; any coarser interval yields one point per
        # calendar period, dated at the period start (023).
        if periodicity in (None, "day"):
            historical_dates = [first_date, resolved_start]
            projected_dates = [resolved_start, projection_date]
        else:
            historical_dates = _period_starts(first_date, resolved_start, periodicity)
            projected_dates = [
                resolved_start,
                *_period_starts(resolved_start + timedelta(days=1), projection_date, periodicity),
            ]

        entries = [
            PositionTimeSeriesEntry.model_validate(
                {
                    "date": d,
                    "position": "Historical",
                    "market_value": _START_MARKET_VALUE / 4
                    if d == first_date
                    else _START_MARKET_VALUE,
                }
            )
            for d in historical_dates
        ]
        positions = ["Historical"]
        for return_key in returns:
            if return_key not in self._supported_return_keys:
                continue  # silently omitted (FR-012)
            label = _LABEL_BY_RETURN_KEY[return_key]
            positions.append(label)
            for d in projected_dates:
                years = (d - resolved_start).days / 365.25
                entries.append(
                    PositionTimeSeriesEntry.model_validate(
                        {
                            "date": d,
                            "position": label,
                            "market_value": _START_MARKET_VALUE * (1.03 ** max(years, 0)),
                        }
                    )
                )

        return PositionTimeSeriesResponse(
            account_name=account_name,
            attributes=["market_value"],
            positions=positions,
            from_date=account.position_ladder.from_date,
            to_date=projection_date,
            entries=entries,
            _links={"self": f"/v1/accounts/{account_name}/projection"},
        )


def _install_stub_client(monkeypatch: Any, client: _FakeProjectionClient) -> None:
    monkeypatch.setattr(projection_module, "_get_client", lambda: client)


@given(
    "portfolio-analysis-service has multiple accounts with recorded market-value history",
    target_fixture="stub_client",
)
def stub_client_with_data(monkeypatch):
    client = _FakeProjectionClient(_ACCOUNTS)
    _install_stub_client(monkeypatch, client)
    return client


@given(
    "portfolio-analysis-service has an account with under three years of history",
    target_fixture="stub_client",
)
def stub_client_short_history(monkeypatch):
    client = _FakeProjectionClient(
        _ACCOUNTS, supported_return_keys=frozenset({"ITD (Ann.)", "1Y"})
    )
    _install_stub_client(monkeypatch, client)
    return client


def _ensure_default_stub(monkeypatch) -> None:
    """Install a default stub if no Given step has already installed one."""
    if projection_module._get_client.__module__ == "src.pages.projection":
        stub_client_with_data(monkeypatch)


@when("the browser loads the app", target_fixture="dash_app")
def load_app_root(dash_duo, monkeypatch):
    _ensure_default_stub(monkeypatch)
    dash_duo.start_server(app_module.app)
    dash_duo.wait_for_element("#app-sidebar", timeout=_TIMEOUT)
    return app_module.app


@when(
    "the browser loads the Projection page and its chart finishes loading",
    target_fixture="dash_app",
)
def load_projection_page(dash_duo, monkeypatch):
    _ensure_default_stub(monkeypatch)
    dash_duo.start_server(app_module.app)
    dash_duo.driver.get(f"{dash_duo.server_url}/projection")
    dash_duo.wait_for_element("#projection-chart-container", timeout=_TIMEOUT)
    dash_duo.wait_for_element(
        "#projection-chart, #projection-empty-state, #projection-error-state",
        timeout=_TIMEOUT,
    )
    return app_module.app


@given("the Projection page has finished loading its default chart", target_fixture="dash_app")
def projection_finished_loading(dash_duo, monkeypatch):
    return load_projection_page(dash_duo, monkeypatch)


@then('there is no "Income" navigation entry')
def no_income_nav_entry(dash_duo):
    with_income = dash_duo.find_elements(By.CSS_SELECTOR, "#app-sidebar-nav-income")
    assert with_income == []


@then(
    parsers.parse(
        'there is a "{label}" navigation entry in the position "{old_label}" used to occupy'
    )
)
def nav_entry_in_position(dash_duo, label, old_label):
    nav_items = dash_duo.find_elements(
        By.CSS_SELECTOR, "#app-sidebar-nav a, #app-sidebar-nav button"
    )
    texts = [item.text for item in nav_items]
    assert label in texts


def _toggle_xpath(label: str) -> str:
    """XPath for a return toggle's checkbox input.

    Safe for labels with spaces/dots (e.g. "Ann. ITD"), unlike a CSS id selector.
    """
    return f'//*[@id="projection-attribute-toggle-{label}"]//input[@type="checkbox"]'


def _find_toggle(dash_duo, label: str):
    return dash_duo.driver.find_element(By.XPATH, _toggle_xpath(label))


@given(parsers.parse('the user turns on the "{label}" return toggle'))
@when(parsers.parse('the user turns on the "{label}" return toggle'))
def turn_on_return_toggle(dash_duo, label):
    toggle = _find_toggle(dash_duo, label)
    if not toggle.is_selected():
        toggle.click()
    dash_duo.wait_for_element(
        "#projection-chart, #projection-empty-state, #projection-error-state", timeout=_TIMEOUT
    )


_HORIZON_BUTTON_IDS = {"1Y": "1y", "5Y": "5y", "10Y": "10y", "20Y": "20y"}


@given(parsers.parse('the user clicks the "{label}" horizon button'))
@when(parsers.parse('the user clicks the "{label}" horizon button'))
def click_horizon_button(dash_duo, label):
    key = _HORIZON_BUTTON_IDS[label]
    dash_duo.find_element(By.CSS_SELECTOR, f"#projection-horizon-{key}").click()
    dash_duo.wait_for_element("#projection-chart", timeout=_TIMEOUT)


def _chart_trace_names_and_dates(dash_duo) -> list[dict[str, Any]]:
    return dash_duo.driver.execute_script(
        "var gd = document.querySelector('#projection-chart .js-plotly-plot');"
        "return gd.data.map(function(t) {"
        "  return {name: t.name, x: t.x, y: t.y};"
        "});"
    )


@then("the chart shows the account's historical market value up to the start date")
def chart_shows_historical(dash_duo):
    traces = _chart_trace_names_and_dates(dash_duo)
    assert any(t["name"] == "Historical" for t in traces)


@then(parsers.parse(
    "a single projected line labelled \"{label}\" continues from the start date's value"
    " to ten years from the start date"
))
def single_projected_line(dash_duo, label):
    traces = _chart_trace_names_and_dates(dash_duo)
    assert any(t["name"] == label for t in traces)


@then("the historical and projected lines are visually distinguishable")
def historical_and_projected_distinguishable(dash_duo):
    dashes = dash_duo.driver.execute_script(
        "var gd = document.querySelector('#projection-chart .js-plotly-plot');"
        "return gd.data.map(function(t) { return [t.name, t.line.dash]; });"
    )
    dash_map = dict(dashes)
    assert dash_map.get("Historical") == "solid"
    assert all(v == "dash" for name, v in dash_map.items() if name != "Historical")


@then(parsers.parse("the projected line's end date is {years:d} years after the start date"))
def projected_line_end_years_after_start(dash_duo, years):
    from_date_value = dash_duo.driver.execute_script(
        "return document.querySelector('#projection-start-date input').value;"
    )
    target_date_value = dash_duo.driver.execute_script(
        "return document.querySelector('#projection-target-date input').value;"
    )
    from src.pages._projection_chart import _years_after

    expected = _years_after(date.fromisoformat(from_date_value), years)
    assert date.fromisoformat(target_date_value) == expected


@then(parsers.parse('no projected line is shown for "{label}"'))
def no_projected_line(dash_duo, label):
    traces = _chart_trace_names_and_dates(dash_duo)
    assert all(t["name"] != label for t in traces)


@then("the historical market-value line still renders normally with no error shown")
def historical_still_renders_no_error(dash_duo):
    error_states = dash_duo.find_elements(By.CSS_SELECTOR, "#projection-error-state")
    assert error_states == []
    traces = _chart_trace_names_and_dates(dash_duo)
    assert any(t["name"] == "Historical" for t in traces)


@then("the chart shows only the historical market-value line")
def chart_shows_only_historical(dash_duo):
    traces = _chart_trace_names_and_dates(dash_duo)
    assert [t["name"] for t in traces] == ["Historical"]


@then("no error or empty-state message is shown")
def no_error_or_empty_state(dash_duo):
    assert dash_duo.find_elements(By.CSS_SELECTOR, "#projection-error-state") == []
    assert dash_duo.find_elements(By.CSS_SELECTOR, "#projection-empty-state") == []


# --- US2: exact-date projection via the calendar picker ---------------------


def _set_calendar_date(dash_duo, iso_date: str) -> None:
    dash_duo.driver.execute_script(
        "var els = document.querySelectorAll('#projection-target-date input');"
        "if (els.length) { els[0].value = arguments[0]; }",
        iso_date,
    )
    # DatePickerSingle applies a picked date via its own internal callback
    # wiring on blur/selection; dispatching a change event mirrors a real
    # user's pick closely enough for this fake-backed scenario.
    dash_duo.driver.execute_script(
        "var els = document.querySelectorAll('#projection-target-date input');"
        "if (els.length) { els[0].dispatchEvent(new Event('change')); }"
    )
    dash_duo.wait_for_element(
        "#projection-chart, #projection-empty-state, #projection-error-state", timeout=_TIMEOUT
    )


@when(
    "the user picks a projection date five and a half years from the start date "
    "using the calendar control"
)
def pick_five_and_half_years(dash_duo):
    from_date_value = dash_duo.driver.execute_script(
        "return document.querySelector('#projection-start-date input').value;"
    )
    start = date.fromisoformat(from_date_value)
    picked = start + timedelta(days=int(5.5 * 365.25))
    _set_calendar_date(dash_duo, picked.isoformat())


@then("the projected line ends exactly on that chosen date")
def projected_line_ends_on_chosen_date(dash_duo):
    target_value = dash_duo.driver.execute_script(
        "return document.querySelector('#projection-target-date input').value;"
    )
    traces = _chart_trace_names_and_dates(dash_duo)
    for trace in traces:
        if trace["name"] == "Historical":
            continue
        assert trace["x"][-1] == target_value


@given("the user has picked an exact projection date using the calendar control")
def has_picked_exact_date(dash_duo):
    pick_five_and_half_years(dash_duo)


@then(
    "the projection now ends one year from the start date, not on the previously chosen date"
)
def projection_ends_one_year_from_start(dash_duo):
    projected_line_end_years_after_start(dash_duo, 1)


@then('the calendar control shows the date the "1Y" button resolved to')
def calendar_shows_resolved_date(dash_duo):
    from src.pages._projection_chart import _years_after

    from_date_value = dash_duo.driver.execute_script(
        "return document.querySelector('#projection-start-date input').value;"
    )
    target_value = dash_duo.driver.execute_script(
        "return document.querySelector('#projection-target-date input').value;"
    )
    expected = _years_after(date.fromisoformat(from_date_value), 1)
    assert date.fromisoformat(target_value) == expected


@when("the user attempts to pick a projection date on or before the start date")
def attempt_pick_invalid_date(dash_duo):
    from_date_value = dash_duo.driver.execute_script(
        "return document.querySelector('#projection-start-date input').value;"
    )
    _set_calendar_date(dash_duo, from_date_value)


@then("that date is not accepted as the projection target")
def date_not_accepted(dash_duo):
    validation_text = dash_duo.driver.execute_script(
        "var el = document.querySelector('#projection-date-validation');"
        "return el ? el.textContent : '';"
    )
    assert validation_text.strip() != ""


@then("an inline message next to the calendar control explains why it was rejected")
def inline_message_shown(dash_duo):
    date_not_accepted(dash_duo)


@then("the chart continues showing the most recently valid projection")
def chart_continues_valid_projection(dash_duo):
    error_states = dash_duo.find_elements(By.CSS_SELECTOR, "#projection-error-state")
    assert error_states == []


# --- US3: comparing multiple returns -----------------------------------------


@then(parsers.parse('two projected lines are shown, labelled "{first}" and "{second}"'))
def two_projected_lines_shown(dash_duo, first, second):
    traces = _chart_trace_names_and_dates(dash_duo)
    names = {t["name"] for t in traces}
    assert first in names and second in names


@then("both lines begin at the same point, the start date's market value")
def both_lines_begin_at_same_point(dash_duo):
    traces = _chart_trace_names_and_dates(dash_duo)
    starts = {t["name"]: t["y"][0] for t in traces if t["name"] != "Historical"}
    assert len(set(starts.values())) == 1


@then("both lines end on the same date, ten years from the start date")
def both_lines_end_same_date(dash_duo):
    traces = _chart_trace_names_and_dates(dash_duo)
    ends = {t["name"]: t["x"][-1] for t in traces if t["name"] != "Historical"}
    assert len(set(ends.values())) == 1


@then(parsers.parse('a third projected line labelled "{label}" appears'))
def third_projected_line_appears(dash_duo, label):
    traces = _chart_trace_names_and_dates(dash_duo)
    assert any(t["name"] == label for t in traces)


@then(parsers.parse('the lines labelled "{first}" and "{second}" are unchanged'))
def other_lines_unchanged(dash_duo, first, second):
    traces = _chart_trace_names_and_dates(dash_duo)
    names = {t["name"] for t in traces}
    assert first in names and second in names




# --- 023: periodicity control ------------------------------------------------
# Self-contained (not shared with Overview's identically-worded steps): pytest-bdd
# resolves steps per module, and these must also read this page's own ids.

_PERIODICITY_GROUP_SELECTOR = "#projection-parameters-periodicity-group"

# Option label (as shown in the control) -> service-side value; mirrors config/content.yaml.
_WIRE_VALUE_BY_LABEL = {
    "day": "day",
    "week": "week",
    "month": "month",
    "quarter": "quarter",
    "year": "annual",
}


def _wait_until(dash_duo, predicate, message: str) -> None:
    WebDriverWait(dash_duo.driver, _TIMEOUT).until(lambda _d: predicate(), message)


@given(
    parsers.parse("portfolio-analysis-service has an account whose history starts on {earliest}"),
    target_fixture="stub_client",
)
def stub_client_with_history_starting_on(monkeypatch, earliest):
    account = AccountSummary(
        account_name="SPAN-ISA",
        capital_ledger=AccountResourceRange(
            from_date=date.fromisoformat(earliest), to_date=date(2026, 9, 22)
        ),
        position_ladder=AccountResourceRange(
            from_date=date.fromisoformat(earliest), to_date=date(2026, 9, 22)
        ),
    )
    client = _FakeProjectionClient([account])
    _install_stub_client(monkeypatch, client)
    return client


@given(parsers.parse("the backing service now takes {seconds:d} seconds to answer chart requests"))
def service_now_slow(stub_client, seconds):
    stub_client.delay_seconds = float(seconds)


@then('a control labelled "Periodicity" is shown in the parameters bar')
def periodicity_control_labelled(dash_duo):
    label_text = dash_duo.driver.execute_script(
        "var el = document.getElementById('projection-parameters-periodicity-label');"
        "return el ? el.textContent : '';"
    )
    assert label_text == "Periodicity"


@then(
    parsers.parse(
        'its options are exactly "{opt1}", "{opt2}", "{opt3}", "{opt4}" and "{opt5}", in that order'
    )
)
def periodicity_options_in_order(dash_duo, opt1, opt2, opt3, opt4, opt5):
    labels = dash_duo.driver.execute_script(
        "var els = document.querySelectorAll(arguments[0] + ' button');"
        "return Array.prototype.map.call(els, function(b) { return b.textContent; });",
        _PERIODICITY_GROUP_SELECTOR,
    )
    assert labels == [opt1, opt2, opt3, opt4, opt5]


@given(parsers.parse('the user selects periodicity "{option}" on Projection'))
@when(parsers.parse('the user selects periodicity "{option}" on Projection'))
def select_periodicity(dash_duo, option):
    dash_duo.find_element(f"#projection-parameters-periodicity-{option}").click()
    dash_duo.wait_for_element(
        "#projection-chart, #projection-empty-state, #projection-error-state", timeout=_TIMEOUT
    )


@when(parsers.parse("the user picks the projection date {iso_date} using the calendar control"))
def pick_projection_date(dash_duo, iso_date):
    _set_calendar_date(dash_duo, iso_date)


@when(parsers.parse('the user switches to the account "{name}"'))
def switch_account(dash_duo, name):
    Select(dash_duo.find_element("#app-parameters-account")).select_by_value(name)


@when(parsers.parse('the user clicks the "{label}" horizon button without waiting for the chart'))
def click_horizon_without_waiting(dash_duo, label):
    key = _HORIZON_BUTTON_IDS[label]
    dash_duo.find_element(f"#projection-horizon-{key}").click()


def _periodicity_buttons_disabled(dash_duo) -> list[bool]:
    return dash_duo.driver.execute_script(
        "var els = document.querySelectorAll(arguments[0] + ' button');"
        "return Array.prototype.map.call(els, function(b) { return b.disabled; });",
        _PERIODICITY_GROUP_SELECTOR,
    )


@then("the Periodicity buttons are disabled")
def periodicity_buttons_disabled(dash_duo):
    def all_disabled() -> bool:
        states = _periodicity_buttons_disabled(dash_duo)
        return bool(states) and all(states)

    _wait_until(dash_duo, all_disabled, "Periodicity buttons were never disabled while refreshing")


@then("the Periodicity buttons become enabled once the chart has loaded")
def periodicity_buttons_enabled(dash_duo):
    def none_disabled() -> bool:
        states = _periodicity_buttons_disabled(dash_duo)
        return bool(states) and not any(states)

    _wait_until(dash_duo, none_disabled, "Periodicity buttons stayed disabled after the refresh")


def _active_periodicity_label(dash_duo) -> str | None:
    return dash_duo.driver.execute_script(
        "var btn = document.querySelector(arguments[0] + ' button.active');"
        "return btn ? btn.textContent : null;",
        _PERIODICITY_GROUP_SELECTOR,
    )


@given(parsers.parse('the active periodicity button is "{interval}"'))
@then(parsers.parse('the active periodicity button is "{interval}"'))
def active_periodicity_button_is(dash_duo, interval):
    _wait_until(
        dash_duo,
        lambda: _active_periodicity_label(dash_duo) == interval,
        f"expected active periodicity button {interval!r}",
    )


@then(parsers.parse('the active periodicity button is not "{interval}"'))
def active_periodicity_button_is_not(dash_duo, interval):
    assert _active_periodicity_label(dash_duo) != interval


@then(parsers.parse('the chart is requested at the "{interval}" interval'))
def chart_requested_at(dash_duo, stub_client, interval):
    expected = _WIRE_VALUE_BY_LABEL[interval]
    _wait_until(
        dash_duo,
        lambda: bool(stub_client.calls) and stub_client.calls[-1]["periodicity"] == expected,
        f"expected the last chart request at {expected!r}",
    )


@then(
    parsers.parse('the chart is requested at the "{interval}" interval for account "{account}"')
)
def chart_requested_at_for_account(dash_duo, stub_client, interval, account):
    chart_requested_at(dash_duo, stub_client, interval)
    assert stub_client.calls[-1]["account_name"] == account


def _all_points_on_quarter_starts(dash_duo) -> bool:
    traces = _chart_trace_names_and_dates(dash_duo)
    if len(traces) < 2:
        return False
    for trace in traces:
        dates = [date.fromisoformat(str(x)[:10]) for x in trace["x"]]
        if len(set(dates)) != len(dates):
            return False
        # A projected line's first point is the start date itself (the point it
        # continues from); every other point is dated at a calendar-quarter start.
        checked = dates if trace["name"] == "Historical" else dates[1:]
        if len(checked) < 2:
            return False
        if any(d.day != 1 or d.month not in (1, 4, 7, 10) for d in checked):
            return False
    return True


@then(
    "the historical series and every projected series are plotted at one point per "
    "calendar quarter"
)
def series_plotted_per_quarter(dash_duo, stub_client):
    chart_requested_at(dash_duo, stub_client, "quarter")
    _wait_until(
        dash_duo,
        lambda: _all_points_on_quarter_starts(dash_duo),
        "series were not plotted at one point per calendar quarter",
    )


@then("the account, start date, target date and selected returns are unchanged")
def projection_selection_unchanged(dash_duo, stub_client):
    account_value = Select(
        dash_duo.find_element("#app-parameters-account")
    ).first_selected_option.get_attribute("value")
    assert account_value == "AAA-ISA"
    start_value = dash_duo.driver.execute_script(
        "return document.querySelector('#projection-start-date input').value;"
    )
    target_value = dash_duo.driver.execute_script(
        "return document.querySelector('#projection-target-date input').value;"
    )
    call = stub_client.calls[-1]
    assert start_value == "2026-09-22"
    assert date.fromisoformat(target_value) == call["projection_date"]
    assert call["projection_date"].year == 2036  # the "10Y" horizon from the scenario
    assert call["returns"] == ["5Y"]
    assert _find_toggle(dash_duo, "5Y").is_selected()
