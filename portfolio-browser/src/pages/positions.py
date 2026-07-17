"""Positions page: real per-position performance chart + comparison table (018).

Callback graph (see specs/018-positions-page/contracts/ui-contract.md):

1. `_fetch_accounts_and_attributes` — triggered by `positions-mount-trigger`
   (same same-page `dcc.Interval` pattern as Overview's own
   `overview-mount-trigger`); fetches /v1/accounts + /v1/positions/attributes,
   populates the account dropdown, the attribute-toggle switches (defaulting
   `market_value` on, FR-012/spec Assumptions), and the two stores.
2. `_apply_default_account` — once both stores are populated, auto-selects
   the alphabetically-first account (FR-012), mirroring overview.py.
3. `_sync_account_change` — whenever the selected account changes (including
   the very first default selection), resets the date range to "YtD" for
   that account (FR-012, FR-014 — deliberately NOT Overview's own full-history
   default; see specs/018-positions-page/research.md #1a), fetches
   /v1/accounts/{account}/positions, and resets the position filter to every
   position recorded for the new account.
4. `_apply_date_range_shortcut` — five `n_clicks` Inputs (the same shared
   shortcut buttons Overview uses, research.md #1), sets the same
   `app-parameters-from-date`/`to-date` props #3 already sets.
5. `_render_positions` — the single callback that (re-)fetches and renders
   both the chart AND the comparison table whenever the account, from-date,
   to-date, any attribute toggle, the position filter, or the stacked-area
   toggle changes (FR-013, SC-006) — one callback, not two, both because
   Dash forbids two callbacks from targeting the same Output and because the
   spec requires the chart and table to always refresh atomically together.
6. `_apply_stacked_area_validation` — enforces FR-009/FR-010/FR-011's
   single-attribute constraint on the "Stacked area graph" toggle.
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
    _last_business_day,
    _shortcut_from_date,
)
from src.exceptions import PortfolioAnalysisServiceError
from src.models.portfolio_analysis import AccountSummary
from src.pages._positions_chart import _build_comparison_table, _build_figure
from src.services.portfolio_analysis_client import (
    HttpPortfolioAnalysisClient,
    PortfolioAnalysisClient,
)

dash.register_page(__name__, path="/positions", name="Positions")

logger = structlog.get_logger(__name__)

_DEFAULT_ATTRIBUTE = "market_value"
_TOGGLE_ID_TYPE = "positions-attribute-toggle"

# Must match src/layout/shell.py's shared shortcut button ids (reused
# verbatim from Overview; research.md #1).
_SHORTCUT_CODE_BY_BUTTON_ID = {
    "overview-shortcut-ytd": SHORTCUT_YTD,
    "overview-shortcut-1y": SHORTCUT_1Y,
    "overview-shortcut-3y": SHORTCUT_3Y,
    "overview-shortcut-5y": SHORTCUT_5Y,
    "overview-shortcut-all": SHORTCUT_ALL,
}

# Every control FR-023 requires disabled during an in-flight refresh, except
# the attribute-toggle switches and the "Stacked area graph" toggle: the
# former are pattern-matched/dynamically created and the latter's `disabled`
# prop is already owned by `_apply_stacked_area_validation` (FR-011) — a
# second callback targeting the same Output would conflict. Both remain
# clickable during a refresh; this is a deliberate, narrow scope reduction
# from FR-023's literal wording to avoid an unsupported dual-owner Output.
_REFRESH_DISABLED_IDS = [
    "app-parameters-account",
    "app-parameters-from-date",
    "app-parameters-to-date",
    *_SHORTCUT_CODE_BY_BUTTON_ID,
    "positions-parameters-position-filter",
]


def _get_client() -> PortfolioAnalysisClient:
    """Factory for the outbound client.

    A plain module-level function (not a module-level instance) so BDD tests
    can monkeypatch `src.pages.positions._get_client` with a fake before the
    browser triggers any callback, without needing a running
    portfolio-analysis-service instance.
    """
    settings = Settings()
    return HttpPortfolioAnalysisClient(
        base_url=settings.portfolio_analysis_service_url,
        timeout_seconds=settings.request_timeout_seconds,
    )


def _empty_state(message: str) -> html.Div:
    return html.Div(message, id="positions-empty-state", className="text-center text-muted p-5")


def _error_state(message: str) -> html.Div:
    return html.Div(message, id="positions-error-state", className="text-center text-danger p-5")


layout = html.Div(
    [
        # Fires its one tick ~200ms after every mount of this layout (first
        # load AND every revisit), mirroring overview.py's own
        # `overview-mount-trigger` (016 research.md #7).
        dcc.Interval(id="positions-mount-trigger", interval=200, max_intervals=1),
        dcc.Store(id="positions-accounts-store"),
        dcc.Store(id="positions-attributes-store"),
        dcc.Store(id="positions-list-store"),
        html.Div(id="positions-attribute-toggles", className="mb-3"),
        dcc.Loading(
            id="positions-chart-loading",
            children=html.Div(
                _empty_state("Loading position performance…"),
                id="positions-chart-container",
            ),
        ),
        html.Div(id="positions-table-container", className="mt-4"),
    ],
    className="p-3",
)


@callback(
    Output("positions-accounts-store", "data"),
    Output("positions-attributes-store", "data"),
    Output("app-parameters-account", "options"),
    Output("positions-attribute-toggles", "children"),
    Output("positions-chart-container", "children", allow_duplicate=True),
    Input("positions-mount-trigger", "n_intervals"),
    prevent_initial_call=True,
)
def _fetch_accounts_and_attributes(_n_intervals: int) -> tuple[Any, ...]:
    """Fetch /v1/accounts and /v1/positions/attributes on every Positions mount.

    Satisfies FR-002/FR-004/FR-012. `positions-mount-trigger` only exists
    inside this page's own layout, so this cannot fire while on another
    route — no separate pathname check needed.
    """
    client = _get_client()
    try:
        accounts = client.list_accounts()
        attributes = client.list_position_attributes()
    except PortfolioAnalysisServiceError:
        logger.error("positions_mount_fetch_failed")
        return (
            dash.no_update,
            dash.no_update,
            dash.no_update,
            dash.no_update,
            _error_state(
                "Could not load accounts/attributes from portfolio-analysis-service. "
                "Please try again shortly."
            ),
        )

    account_options = [{"label": a.account_name, "value": a.account_name} for a in accounts]
    toggle_children = build_attribute_toggles(
        attributes, _TOGGLE_ID_TYPE, frozenset({_DEFAULT_ATTRIBUTE})
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
    Input("positions-accounts-store", "data"),
    Input("positions-attributes-store", "data"),
    prevent_initial_call=True,
)
def _apply_default_account(
    accounts_data: list[dict[str, Any]] | None, attributes_data: list[dict[str, Any]] | None
) -> str:
    """Auto-select the alphabetically-first account once accounts are loaded (FR-012)."""
    if not accounts_data:
        raise PreventUpdate
    names = sorted(a["account_name"] for a in accounts_data)
    return names[0]


@callback(
    Output("app-parameters-from-date", "date", allow_duplicate=True),
    Output("app-parameters-to-date", "date", allow_duplicate=True),
    Output("positions-list-store", "data"),
    Output("positions-parameters-position-filter", "options"),
    Output("positions-parameters-position-filter", "value"),
    Input("app-parameters-account", "value"),
    State("positions-accounts-store", "data"),
    prevent_initial_call=True,
)
def _sync_account_change(
    account_name: str | None, accounts_data: list[dict[str, Any]] | None
) -> tuple[Any, ...]:
    """Reset date range to "YtD" and the position filter to every position (FR-012, FR-014).

    Fires both on the initial default-account selection and on every
    subsequent manual account switch. Deliberately does NOT reuse Overview's
    own `_sync_date_range_to_selected_account` (which yields the account's
    full recorded history) — Positions' own default range is always "YtD"
    (specs/018-positions-page/research.md #1a).
    """
    if not account_name or not accounts_data:
        raise PreventUpdate
    match = next((a for a in accounts_data if a["account_name"] == account_name), None)
    if match is None:
        raise PreventUpdate
    account = AccountSummary.model_validate(match)
    today = date.today()
    from_date = _shortcut_from_date(SHORTCUT_YTD, account, today)
    to_date = _last_business_day(today)

    client = _get_client()
    try:
        positions = client.list_account_positions(account_name=account_name)
    except PortfolioAnalysisServiceError:
        logger.error("positions_list_fetch_failed", account_name=account_name)
        return from_date.isoformat(), to_date.isoformat(), dash.no_update, [], []

    position_names = [p.position for p in positions]
    options = [{"label": name, "value": name} for name in position_names]
    return (
        from_date.isoformat(),
        to_date.isoformat(),
        [p.model_dump(mode="json") for p in positions],
        options,
        position_names,
    )


@callback(
    Output("app-parameters-from-date", "max_date_allowed"),
    Input("app-parameters-to-date", "date"),
    prevent_initial_call=True,
)
def _sync_from_date_max_to_to_date(to_date: str | None) -> Any:
    """Keep "from" from ever exceeding the current "to" value (mirrors Overview's FR-015)."""
    if not to_date:
        raise PreventUpdate
    return to_date


@callback(
    Output("app-parameters-from-date", "date", allow_duplicate=True),
    Output("app-parameters-to-date", "date", allow_duplicate=True),
    Input("overview-shortcut-ytd", "n_clicks"),
    Input("overview-shortcut-1y", "n_clicks"),
    Input("overview-shortcut-3y", "n_clicks"),
    Input("overview-shortcut-5y", "n_clicks"),
    Input("overview-shortcut-all", "n_clicks"),
    State("app-parameters-account", "value"),
    State("positions-accounts-store", "data"),
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
    """Apply a Reporting Period Shortcut's date range (FR-003).

    Mirrors overview.py's `_apply_date_range_shortcut` exactly (same shared
    `_shortcut_from_date`/`_last_business_day` helpers, research.md #1) but
    reads from this page's own `positions-accounts-store`.
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


@callback(
    Output("positions-parameters-stacked-toggle", "value"),
    Output("positions-parameters-stacked-toggle", "disabled"),
    Input({"type": _TOGGLE_ID_TYPE, "name": ALL}, "value"),
    State("positions-parameters-stacked-toggle", "value"),
    prevent_initial_call=True,
)
def _apply_stacked_area_validation(
    toggle_values: list[bool], stacked_value: bool
) -> tuple[Any, bool]:
    """Enforce the single-attribute constraint on "Stacked area graph" (FR-009-FR-011).

    Auto-turns the toggle off (never blocking the attribute selection
    itself) the instant a second attribute is selected, and disables the
    toggle for as long as more than one attribute remains selected.
    """
    selected_count = sum(1 for is_on in toggle_values if is_on)
    disabled = selected_count > 1
    if disabled and stacked_value:
        return False, True
    return dash.no_update, disabled


@callback(
    Output("positions-chart-container", "children"),
    Output("positions-table-container", "children"),
    Input("app-parameters-account", "value"),
    Input("app-parameters-from-date", "date"),
    Input("app-parameters-to-date", "date"),
    Input({"type": _TOGGLE_ID_TYPE, "name": ALL}, "value"),
    Input("positions-parameters-position-filter", "value"),
    Input("positions-parameters-stacked-toggle", "value"),
    State({"type": _TOGGLE_ID_TYPE, "name": ALL}, "id"),
    running=[
        (Output(component_id, "disabled"), True, False) for component_id in _REFRESH_DISABLED_IDS
    ],
    prevent_initial_call=True,
)
def _render_positions(
    account_name: str | None,
    from_date: str | None,
    to_date: str | None,
    toggle_values: list[bool],
    selected_positions: list[str] | None,
    stacked: bool | None,
    toggle_ids: list[dict[str, str]],
) -> tuple[Any, Any]:
    """Re-fetch and re-render the chart + table whenever any selection changes.

    One callback for the default view (US1), account/date exploration
    (US2), attribute/position filtering (US3), the comparison table (US4),
    and the stacked-area toggle (US5) — Dash does not allow multiple
    callbacks to target the same Output, and FR-013/SC-006 require the
    chart and table to always refresh atomically together.
    """
    if not account_name or not from_date or not to_date:
        raise PreventUpdate

    toggled_attributes = [
        toggle_id["name"]
        for toggle_id, is_on in zip(toggle_ids, toggle_values, strict=True)
        if is_on
    ]
    if not toggled_attributes:
        return (
            _empty_state("Select at least one attribute to display a chart."),
            None,
        )

    if not selected_positions:
        return (
            _empty_state("Select at least one position to display a chart."),
            None,
        )

    client = _get_client()
    try:
        response = client.get_position_timeseries(
            account_name=account_name,
            positions=selected_positions,
            attributes=toggled_attributes,
            start=date.fromisoformat(from_date),
            end=date.fromisoformat(to_date),
        )
    except PortfolioAnalysisServiceError:
        logger.error("positions_timeseries_fetch_failed", account_name=account_name)
        return (
            _error_state(
                "Could not load position data from portfolio-analysis-service. "
                "Please try again shortly."
            ),
            None,
        )

    # mode="python" (the default), NOT mode="json": _build_comparison_rows
    # compares entry["date"] (a datetime.date) against from_date/to_date
    # (also datetime.date) by equality — model_dump(mode="json") would
    # serialize "date" to an ISO string instead, silently breaking that
    # comparison (every value would read as absent) while the chart itself
    # stayed visibly correct (Plotly accepts either form for x-values, so
    # nothing there would reveal the mismatch).
    entries = [entry.model_dump() for entry in response.entries]
    if not entries:
        return (
            _empty_state(
                "No data is available for the selected account, date range, and positions."
            ),
            None,
        )

    is_stacked = bool(stacked) and len(toggled_attributes) == 1
    figure = _build_figure(entries, toggled_attributes, stacked=is_stacked)
    chart = dcc.Graph(id="positions-chart", figure=figure, style={"height": "600px"})
    table = _build_comparison_table(
        entries,
        toggled_attributes,
        date.fromisoformat(from_date),
        date.fromisoformat(to_date),
    )
    return chart, table
