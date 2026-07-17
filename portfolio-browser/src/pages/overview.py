"""Overview page: real account performance chart (016; FR-001-FR-015).

Callback graph (see specs/016-link-real-portfolio/contracts/ui-contract.md):

1. `_fetch_accounts_and_attributes` — triggered by `overview-mount-trigger`
   (a `dcc.Interval` declared in this page's own layout, firing its one tick
   shortly after every mount — including revisits, not just first load);
   fetches /v1/accounts + /v1/timeseries/attributes, populates the account
   dropdown, the metric-toggle switches, and the two stores. Deliberately
   NOT triggered by `app-parameters-bar.children` (a shell.py-owned signal)
   — that indirection raced against Dash's own internal page-routing swap
   on revisits, leaving the page stuck on "Loading account performance…"
   with the Account/From/To controls unpopulated (see git history/PR notes
   for the bug this replaced). A same-page `dcc.Interval` sidesteps that
   entirely: it only exists while Overview is mounted, so it inherently
   cannot fire on other routes, and it fires fresh on every single mount.
2. `_apply_default_account_and_metric` — once both stores are populated,
   auto-selects the alphabetically-first account and defaults the
   `market_value` toggle on (FR-001a).
3. `_sync_date_range_to_selected_account` — whenever the selected account
   changes (including the very first default selection), resets the
   from/to dates to that account's own defaults (FR-003, FR-004, and the
   "date range resets on account switch" edge case).
4. `_sync_from_date_max_to_to_date` — keeps the "from" picker's
   `max_date_allowed` in sync with the current "to" value (FR-015).
5. `_render_chart` — the single callback that (re-)fetches and renders the
   chart whenever the account, from-date, to-date, or any metric toggle
   changes; this is one callback (not one per user story) because Dash
   forbids two callbacks from targeting the same Output.
6. `_apply_date_range_shortcut` (017) — five `n_clicks` Inputs (one per
   Reporting Period Shortcut button, built in src/layout/shell.py), sets
   the same `app-parameters-from-date`/`to-date` props #3 already sets;
   `_render_chart` picks up the change and re-fetches automatically — no
   new render logic (research.md #3 in specs/017-chart-date-range-shortcuts).
"""

from __future__ import annotations

from datetime import date
from typing import Any

import dash
import structlog
from dash import ALL, Input, Output, State, callback, ctx, dcc, html
from dash.exceptions import PreventUpdate

from config.settings import Settings
from src.components.attribute_toggles import build_attribute_toggles
from src.components.date_range_controls import (
    SHORTCUT_1Y,
    SHORTCUT_3Y,
    SHORTCUT_5Y,
    SHORTCUT_ALL,
    SHORTCUT_YTD,
    _earliest_from_date,
    _last_business_day,
    _shortcut_from_date,
)
from src.exceptions import PortfolioAnalysisServiceError
from src.models.portfolio_analysis import AccountSummary
from src.pages._overview_chart import _build_figure
from src.services.portfolio_analysis_client import (
    HttpPortfolioAnalysisClient,
    PortfolioAnalysisClient,
)

dash.register_page(__name__, path="/", name="Overview")

logger = structlog.get_logger(__name__)

_DEFAULT_METRIC = "market_value"
_TOGGLE_ID_TYPE = "overview-attribute-toggle"

# Must match src/layout/shell.py's _SHORTCUT_BUTTONS ids.
_SHORTCUT_CODE_BY_BUTTON_ID = {
    "overview-shortcut-ytd": SHORTCUT_YTD,
    "overview-shortcut-1y": SHORTCUT_1Y,
    "overview-shortcut-3y": SHORTCUT_3Y,
    "overview-shortcut-5y": SHORTCUT_5Y,
    "overview-shortcut-all": SHORTCUT_ALL,
}


def _get_client() -> PortfolioAnalysisClient:
    """Factory for the outbound client.

    A plain module-level function (not a module-level instance) so BDD tests
    can monkeypatch `src.pages.overview._get_client` with a fake before the
    browser triggers any callback, without needing a running
    portfolio-analysis-service instance.
    """
    settings = Settings()
    return HttpPortfolioAnalysisClient(
        base_url=settings.portfolio_analysis_service_url,
        timeout_seconds=settings.request_timeout_seconds,
    )


def _empty_state(message: str) -> html.Div:
    return html.Div(message, id="overview-empty-state", className="text-center text-muted p-5")


def _error_state(message: str) -> html.Div:
    return html.Div(message, id="overview-error-state", className="text-center text-danger p-5")


def _render_timeseries(
    client: PortfolioAnalysisClient,
    account_name: str,
    attributes: list[str],
    from_date: str,
    to_date: str,
) -> html.Div | dcc.Graph:
    """Fetch and shape a chart, or an empty/error state — the shared render path.

    Args:
        client: The portfolio-analysis-service client to call.
        account_name: The selected account.
        attributes: Toggled-on metric names (must be non-empty — callers
            short-circuit to `_empty_state` before calling this for FR-013's
            zero-metric case).
        from_date: ISO start date.
        to_date: ISO end date.

    Returns:
        A `dcc.Graph` on success with data, or an empty/error-state `Div`.
    """
    try:
        response = client.get_timeseries(
            account_name=account_name,
            attributes=attributes,
            start=date.fromisoformat(from_date),
            end=date.fromisoformat(to_date),
        )
    except PortfolioAnalysisServiceError:
        logger.error("overview_timeseries_fetch_failed", account_name=account_name)
        return _error_state(
            "Could not load performance data from portfolio-analysis-service. "
            "Please try again shortly."
        )

    entries = [entry.model_dump(mode="json") for entry in response.entries]
    if not entries:
        return _empty_state(
            "No data is available for the selected account, date range, and metrics."
        )

    figure = _build_figure(entries, attributes)
    return dcc.Graph(id="overview-chart", figure=figure, style={"height": "600px"})


layout = html.Div(
    [
        # Fires its one tick ~200ms after every mount of this layout (first
        # load AND every revisit), giving shell.py's own pathname-triggered
        # bar-render callback (fast, no I/O) a head start so the real
        # app-parameters-account/from-date/to-date controls reliably exist
        # before this page tries to populate them.
        dcc.Interval(id="overview-mount-trigger", interval=200, max_intervals=1),
        dcc.Store(id="overview-accounts-store"),
        dcc.Store(id="overview-attributes-store"),
        html.Div(id="overview-attribute-toggles", className="mb-3"),
        dcc.Loading(
            id="overview-chart-loading",
            children=html.Div(
                _empty_state("Loading account performance…"),
                id="overview-chart-container",
            ),
        ),
    ],
    className="p-3",
)


@callback(
    Output("overview-accounts-store", "data"),
    Output("overview-attributes-store", "data"),
    Output("app-parameters-account", "options"),
    Output("overview-attribute-toggles", "children"),
    Output("overview-chart-container", "children", allow_duplicate=True),
    Input("overview-mount-trigger", "n_intervals"),
    prevent_initial_call=True,
)
def _fetch_accounts_and_attributes(_n_intervals: int) -> tuple[Any, ...]:
    """Fetch /v1/accounts and /v1/timeseries/attributes on every Overview mount.

    Satisfies FR-001 and FR-005. `overview-mount-trigger` only exists inside
    this page's own layout, so this cannot fire while on another route —
    no separate pathname check needed.
    """
    client = _get_client()
    try:
        accounts = client.list_accounts()
        attributes = client.list_attributes()
    except PortfolioAnalysisServiceError:
        logger.error("overview_mount_fetch_failed")
        return (
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            _error_state(
                "Could not load accounts/metrics from portfolio-analysis-service. "
                "Please try again shortly."
            ),
        )

    account_options = [{"label": a.account_name, "value": a.account_name} for a in accounts]
    toggle_children = build_attribute_toggles(
        attributes, _TOGGLE_ID_TYPE, frozenset({_DEFAULT_METRIC})
    )
    return (
        [a.model_dump(mode="json") for a in accounts],
        [a.model_dump(mode="json") for a in attributes],
        account_options,
        toggle_children,
        dash.no_update,
    )


@callback(
    Output("app-parameters-account", "value"),
    Input("overview-accounts-store", "data"),
    Input("overview-attributes-store", "data"),
    prevent_initial_call=True,
)
def _apply_default_account(
    accounts_data: list[dict[str, Any]] | None, attributes_data: list[dict[str, Any]] | None
) -> str:
    """Auto-select the alphabetically-first account once accounts are loaded (FR-001a)."""
    if not accounts_data:
        raise PreventUpdate
    names = sorted(a["account_name"] for a in accounts_data)
    return names[0]


@callback(
    Output("app-parameters-from-date", "date", allow_duplicate=True),
    Output("app-parameters-to-date", "date", allow_duplicate=True),
    Input("app-parameters-account", "value"),
    State("overview-accounts-store", "data"),
    prevent_initial_call=True,
)
def _sync_date_range_to_selected_account(
    account_name: str | None, accounts_data: list[dict[str, Any]] | None
) -> tuple[Any, Any]:
    """Reset from/to dates to the selected account's own range (FR-003, FR-004).

    Fires both on the initial default-account selection and on every
    subsequent manual account switch, so a previously-chosen custom date
    range always resets on switch (spec Edge Cases).
    """
    if not account_name or not accounts_data:
        raise PreventUpdate
    match = next((a for a in accounts_data if a["account_name"] == account_name), None)
    if match is None:
        raise PreventUpdate
    account = AccountSummary.model_validate(match)
    from_date = _earliest_from_date(account)
    to_date = _last_business_day(date.today())
    return from_date.isoformat(), to_date.isoformat()


@callback(
    Output("app-parameters-from-date", "max_date_allowed"),
    Input("app-parameters-to-date", "date"),
    prevent_initial_call=True,
)
def _sync_from_date_max_to_to_date(to_date: str | None) -> Any:
    """Keep "from" from ever exceeding the current "to" value (FR-015)."""
    if not to_date:
        raise PreventUpdate
    return to_date


@callback(
    Output("overview-chart-container", "children"),
    Input("app-parameters-account", "value"),
    Input("app-parameters-from-date", "date"),
    Input("app-parameters-to-date", "date"),
    Input({"type": _TOGGLE_ID_TYPE, "name": ALL}, "value"),
    State({"type": _TOGGLE_ID_TYPE, "name": ALL}, "id"),
    running=[
        (Output(button_id, "disabled"), True, False)
        for button_id in _SHORTCUT_CODE_BY_BUTTON_ID
    ],
    prevent_initial_call=True,
)
def _render_chart(
    account_name: str | None,
    from_date: str | None,
    to_date: str | None,
    toggle_values: list[bool],
    toggle_ids: list[dict[str, str]],
) -> html.Div | dcc.Graph:
    """Re-fetch and re-render whenever account/date/metric selection changes.

    One callback for all of US1's initial render, US2's account switch,
    US3's date-range change, and US4's metric toggles (FR-008, FR-009,
    FR-013) — Dash does not allow multiple callbacks to target the same
    Output, so this consolidates what tasks.md lists as four separate
    "wire a callback" tasks into one shared implementation.
    """
    if not account_name or not from_date or not to_date:
        raise PreventUpdate

    toggled_attributes = [
        toggle_id["name"]
        for toggle_id, is_on in zip(toggle_ids, toggle_values, strict=True)
        if is_on
    ]
    if not toggled_attributes:
        return _empty_state("Select at least one metric to display a chart.")

    client = _get_client()
    return _render_timeseries(client, account_name, toggled_attributes, from_date, to_date)


@callback(
    Output("app-parameters-from-date", "date", allow_duplicate=True),
    Output("app-parameters-to-date", "date", allow_duplicate=True),
    Input("overview-shortcut-ytd", "n_clicks"),
    Input("overview-shortcut-1y", "n_clicks"),
    Input("overview-shortcut-3y", "n_clicks"),
    Input("overview-shortcut-5y", "n_clicks"),
    Input("overview-shortcut-all", "n_clicks"),
    State("app-parameters-account", "value"),
    State("overview-accounts-store", "data"),
    prevent_initial_call=True,
)
def _apply_date_range_shortcut(
    _ytd: int | None,
    _1y: int | None,
    _3y: int | None,
    _5y: int | None,
    _all: int | None,
    account_name: str | None,
    accounts_data: list[dict[str, Any]] | None,
) -> tuple[Any, Any]:
    """Apply a Reporting Period Shortcut's date range (017; FR-002-FR-010).

    Sets the same two props `_sync_date_range_to_selected_account` sets —
    `_render_chart` already has both as Inputs, so setting them here is
    sufficient to trigger a fresh chart request (FR-010); no new fetch/render
    code needed (research.md #3 in specs/017-chart-date-range-shortcuts).
    """
    button_id = ctx.triggered_id
    code = _SHORTCUT_CODE_BY_BUTTON_ID.get(button_id)
    if code is None or not account_name or not accounts_data:
        raise PreventUpdate

    match = next((a for a in accounts_data if a["account_name"] == account_name), None)
    if match is None:
        raise PreventUpdate

    account = AccountSummary.model_validate(match)
    from_date = _shortcut_from_date(code, account, date.today())
    to_date = _last_business_day(date.today())
    return from_date.isoformat(), to_date.isoformat()
