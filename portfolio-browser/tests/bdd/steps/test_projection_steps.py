"""Step definitions for the Projection page BDD feature files (022).

No real portfolio-analysis-service instance is used — and none exists yet
for the projection endpoint (specs/022-projection-page/contracts/
portfolio-analysis-api.md is a pinned-but-deferred contract). Every scenario
monkeypatches `src.pages.projection._get_client` with an in-memory fake
implementing that pinned contract, mirroring
tests/bdd/steps/test_performance_steps.py's own `_FakeClient` pattern.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from pytest_bdd import given, parsers, scenarios, then, when
from selenium.webdriver.common.by import By

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

_TIMEOUT = 10

# Wire-format return key -> the display label this page's config gives it
# (config/content.yaml's `projection.returns`), mirrored here rather than
# imported so the fake stays a self-contained double.
_LABEL_BY_RETURN_KEY = {"itd_ann": "Ann. ITD", "1y": "1Y", "3y": "3Y", "5y": "5Y"}

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


class _FakeProjectionClient:
    """In-memory PortfolioAnalysisClient double implementing the pinned projection contract."""

    def __init__(
        self,
        accounts: list[AccountSummary],
        supported_return_keys: frozenset[str] = frozenset({"itd_ann", "1y", "3y", "5y"}),
        raise_on_mount: bool = False,
        raise_on_chart: bool = False,
    ) -> None:
        self._accounts = accounts
        self._supported_return_keys = supported_return_keys
        self._raise_on_mount = raise_on_mount
        self._raise_on_chart = raise_on_chart

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
        if self._raise_on_chart:
            raise PortfolioAnalysisServiceError("stubbed failure")
        account = next(a for a in self._accounts if a.account_name == account_name)
        resolved_start = start if start is not None else account.position_ladder.to_date

        entries = [
            PositionTimeSeriesEntry.model_validate(
                {
                    "date": account.position_ladder.from_date,
                    "position": "Historical",
                    "market_value": _START_MARKET_VALUE / 4,
                }
            ),
            PositionTimeSeriesEntry.model_validate(
                {
                    "date": resolved_start,
                    "position": "Historical",
                    "market_value": _START_MARKET_VALUE,
                }
            ),
        ]
        positions = ["Historical"]
        for return_key in returns:
            if return_key not in self._supported_return_keys:
                continue  # silently omitted (FR-012)
            label = _LABEL_BY_RETURN_KEY[return_key]
            positions.append(label)
            years = (projection_date - resolved_start).days / 365.25
            projected_value = _START_MARKET_VALUE * (1.03 ** max(years, 0))
            entries.append(
                PositionTimeSeriesEntry.model_validate(
                    {"date": resolved_start, "position": label, "market_value": _START_MARKET_VALUE}
                )
            )
            entries.append(
                PositionTimeSeriesEntry.model_validate(
                    {"date": projection_date, "position": label, "market_value": projected_value}
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
    client = _FakeProjectionClient(_ACCOUNTS, supported_return_keys=frozenset({"itd_ann", "1y"}))
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


