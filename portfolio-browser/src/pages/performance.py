"""Performance page: real account return-measure chart (020).

Callback graph (see specs/020-performance-page-chart/contracts/ui-contract.md):

1. `_fetch_accounts_and_attributes` — triggered by `performance-mount-trigger`
   (same same-page `dcc.Interval` pattern as Overview's/Positions' own mount
   triggers); fetches /v1/accounts + /v1/performance/attributes, populating
   the account dropdown, the measure-toggle switches (defaulting the
   first-returned measure on, research.md #5 — not a hard-coded name, since
   unlike Overview's `market_value` the measure set is entirely API-driven),
   and the two stores.
2. `_apply_default_account` — once both stores are populated, auto-selects
   the alphabetically-first account, mirroring overview.py/positions.py.
3. `_sync_date_range_to_selected_account` — whenever the selected account
   changes (including the very first default selection), resets the
   from/to dates to that account's own full recorded history — the same
   default Overview's own equivalent uses, NOT Positions' "YtD" default
   (research.md #4).
4. `_sync_from_date_max_to_to_date` — keeps the "from" picker's
   `max_date_allowed` in sync with the current "to" value (FR-015).
5. `_render_chart` — the single callback that (re-)fetches and renders the
   chart whenever the account, from-date, to-date, or any measure toggle
   changes.
6. `_apply_date_range_shortcut` — five `n_clicks` Inputs (the same shared
   shortcut buttons Overview/Positions use, research.md #3); this page's own
   `_SHORTCUT_CODE_BY_BUTTON_ID` maps the button labeled "ITD" to
   `SHORTCUT_ALL` (not `SHORTCUT_YTD`) — a deliberate, spec-accepted
   redundancy with the neighboring "All" button.
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
    _earliest_from_date,
    _last_business_day,
    _shortcut_from_date,
)
from src.exceptions import PortfolioAnalysisServiceError
from src.models.portfolio_analysis import AccountSummary
from src.pages._performance_chart import _build_figure
from src.services.portfolio_analysis_client import (
    HttpPortfolioAnalysisClient,
    PortfolioAnalysisClient,
)

dash.register_page(__name__, path="/performance", name="Performance")

logger = structlog.get_logger(__name__)

_TOGGLE_ID_TYPE = "performance-attribute-toggle"

# Must match src/layout/shell.py's shared shortcut button ids (reused
# verbatim from Overview/Positions; research.md #3). The button labeled
# "ITD" on this page shares the same DOM id as Overview's/Positions' own
# "YtD" button — only its page-local *code mapping* differs.
_SHORTCUT_CODE_BY_BUTTON_ID = {
    "overview-shortcut-ytd": SHORTCUT_ALL,
    "overview-shortcut-1y": SHORTCUT_1Y,
    "overview-shortcut-3y": SHORTCUT_3Y,
    "overview-shortcut-5y": SHORTCUT_5Y,
    "overview-shortcut-all": SHORTCUT_ALL,
}

# Every control FR-017 requires disabled during an in-flight refresh, except
# the measure-toggle switches: they are pattern-matched/dynamically created
# (`{"type": _TOGGLE_ID_TYPE, "name": ALL}`), so there is no single static
# Output id to disable them through — the same carve-out Positions' own
# `_REFRESH_DISABLED_IDS` documents for its attribute toggles.
_REFRESH_DISABLED_IDS = [
    "app-parameters-account",
    "app-parameters-from-date",
    "app-parameters-to-date",
    *_SHORTCUT_CODE_BY_BUTTON_ID,
]


def _get_client() -> PortfolioAnalysisClient:
    """Factory for the outbound client.

    A plain module-level function (not a module-level instance) so BDD tests
    can monkeypatch `src.pages.performance._get_client` with a fake before
    the browser triggers any callback, without needing a running
    portfolio-analysis-service instance.
    """
    settings = Settings()
    return HttpPortfolioAnalysisClient(
        base_url=settings.portfolio_analysis_service_url,
        timeout_seconds=settings.request_timeout_seconds,
    )


def _empty_state(message: str) -> html.Div:
    return html.Div(message, id="performance-empty-state", className="text-center text-muted p-5")


def _error_state(message: str) -> html.Div:
    return html.Div(message, id="performance-error-state", className="text-center text-danger p-5")


def _render_performance(
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
        attributes: Toggled-on measure names (must be non-empty — callers
            short-circuit to `_empty_state` before calling this for FR-011's
            zero-measure case).
        from_date: ISO start date.
        to_date: ISO end date.

    Returns:
        A `dcc.Graph` on success with data, or an empty/error-state `Div`.
    """
    try:
        response = client.get_performance(
            account_name=account_name,
            attributes=attributes,
            start=date.fromisoformat(from_date),
            end=date.fromisoformat(to_date),
        )
    except PortfolioAnalysisServiceError:
        logger.error("performance_fetch_failed", account_name=account_name)
        return _error_state(
            "Could not load performance data from portfolio-analysis-service. "
            "Please try again shortly."
        )

    entries = [entry.model_dump(mode="json") for entry in response.entries]
    if not entries:
        return _empty_state(
            "No data is available for the selected account, date range, and measures."
        )

    figure = _build_figure(entries, attributes)
    return dcc.Graph(id="performance-chart", figure=figure, style={"height": "600px"})


layout = html.Div(
    [
        # Fires its one tick ~200ms after every mount of this layout (first
        # load AND every revisit), mirroring overview.py's/positions.py's
        # own mount-trigger pattern.
        dcc.Interval(id="performance-mount-trigger", interval=200, max_intervals=1),
        dcc.Store(id="performance-accounts-store"),
        dcc.Store(id="performance-attributes-store"),
        html.Div(id="performance-attribute-toggles", className="mb-3"),
        dcc.Loading(
            id="performance-chart-loading",
            children=html.Div(
                _empty_state("Loading account performance…"),
                id="performance-chart-container",
            ),
        ),
    ],
    className="p-3",
)


@callback(
    Output("performance-accounts-store", "data"),
    Output("performance-attributes-store", "data"),
    Output("app-parameters-account", "options"),
    Output("performance-attribute-toggles", "children"),
    Output("performance-chart-container", "children", allow_duplicate=True),
    Input("performance-mount-trigger", "n_intervals"),
    prevent_initial_call=True,
)
def _fetch_accounts_and_attributes(_n_intervals: int) -> tuple[Any, ...]:
    """Fetch /v1/accounts and /v1/performance/attributes on every Performance mount.

    Satisfies FR-002/FR-006. `performance-mount-trigger` only exists inside
    this page's own layout, so this cannot fire while on another route — no
    separate pathname check needed.
    """
    client = _get_client()
    try:
        accounts = client.list_accounts()
        attributes = client.list_performance_attributes()
    except PortfolioAnalysisServiceError:
        logger.error("performance_mount_fetch_failed")
        return (
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            _error_state(
                "Could not load accounts/measures from portfolio-analysis-service. "
                "Please try again shortly."
            ),
        )

    account_options = [{"label": a.account_name, "value": a.account_name} for a in accounts]
    default_on_names = frozenset({attributes[0].name}) if attributes else frozenset()
    toggle_children = build_attribute_toggles(attributes, _TOGGLE_ID_TYPE, default_on_names)
    return (
        [a.model_dump(mode="json") for a in accounts],
        [a.model_dump(mode="json") for a in attributes],
        account_options,
        toggle_children,
        dash.no_update,
    )


@callback(
    Output("app-parameters-account", "value"),
    Input("performance-accounts-store", "data"),
    Input("performance-attributes-store", "data"),
    prevent_initial_call=True,
)
def _apply_default_account(
    accounts_data: list[dict[str, Any]] | None, attributes_data: list[dict[str, Any]] | None
) -> str:
    """Auto-select the alphabetically-first account once accounts are loaded (FR-008)."""
    if not accounts_data:
        raise PreventUpdate
    names = sorted(a["account_name"] for a in accounts_data)
    return names[0]


@callback(
    Output("app-parameters-from-date", "date", allow_duplicate=True),
    Output("app-parameters-to-date", "date", allow_duplicate=True),
    Input("app-parameters-account", "value"),
    State("performance-accounts-store", "data"),
    prevent_initial_call=True,
)
def _sync_date_range_to_selected_account(
    account_name: str | None, accounts_data: list[dict[str, Any]] | None
) -> tuple[Any, Any]:
    """Reset from/to dates to the selected account's own full history (FR-008, FR-009).

    Fires both on the initial default-account selection and on every
    subsequent manual account switch. Uses the account's own earliest
    recorded date directly — the same default Overview's own
    `_sync_date_range_to_selected_account` uses (research.md #4), NOT
    Positions' own "always YtD" default.
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
    Output("performance-chart-container", "children"),
    Input("app-parameters-account", "value"),
    Input("app-parameters-from-date", "date"),
    Input("app-parameters-to-date", "date"),
    Input({"type": _TOGGLE_ID_TYPE, "name": ALL}, "value"),
    State({"type": _TOGGLE_ID_TYPE, "name": ALL}, "id"),
    running=[
        (Output(component_id, "disabled"), True, False) for component_id in _REFRESH_DISABLED_IDS
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
    """Re-fetch and re-render whenever account/date/measure selection changes.

    One callback for every user story's chart refresh (FR-009, FR-010) —
    Dash does not allow multiple callbacks to target the same Output.
    """
    if not account_name or not from_date or not to_date:
        raise PreventUpdate

    toggled_attributes = [
        toggle_id["name"]
        for toggle_id, is_on in zip(toggle_ids, toggle_values, strict=True)
        if is_on
    ]
    if not toggled_attributes:
        return _empty_state("Select at least one measure to display a chart.")

    client = _get_client()
    return _render_performance(client, account_name, toggled_attributes, from_date, to_date)


@callback(
    Output("app-parameters-from-date", "date", allow_duplicate=True),
    Output("app-parameters-to-date", "date", allow_duplicate=True),
    Input("overview-shortcut-ytd", "n_clicks"),
    Input("overview-shortcut-1y", "n_clicks"),
    Input("overview-shortcut-3y", "n_clicks"),
    Input("overview-shortcut-5y", "n_clicks"),
    Input("overview-shortcut-all", "n_clicks"),
    State("app-parameters-account", "value"),
    State("performance-accounts-store", "data"),
    prevent_initial_call=True,
)
def _apply_date_range_shortcut(
    _itd: int | None,
    _1y: int | None,
    _3y: int | None,
    _5y: int | None,
    _all: int | None,
    account_name: str | None,
    accounts_data: list[dict[str, Any]] | None,
) -> tuple[Any, Any]:
    """Apply a Reporting Period Shortcut's date range (FR-004).

    This page's own `_SHORTCUT_CODE_BY_BUTTON_ID` maps the button labeled
    "ITD" (same shared DOM id `overview-shortcut-ytd`) to `SHORTCUT_ALL`,
    not `SHORTCUT_YTD` — the only divergence from Overview's/Positions' own
    copies of this mapping (research.md #3).
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
