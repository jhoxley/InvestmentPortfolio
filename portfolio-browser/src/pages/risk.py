"""Risk page: return-histogram chart + statistics table for a real account (024).

Callback graph (see specs/024-risk-return-histogram-page/contracts/ui-contract.md):

1. `_fetch_accounts` — triggered by `risk-mount-trigger` (same mount-trigger
   pattern as Overview's/Positions'/Performance's own); fetches /v1/accounts,
   populating the account dropdown and `risk-accounts-store`.
2. `_apply_default_account` — once the store is populated, auto-selects the
   alphabetically-first account, mirroring every other page.
3. `_sync_date_range_to_selected_account` — whenever the selected account
   changes (including the very first default selection), resets the
   from/to dates to that account's own full recorded history — the same
   default Overview's/Performance's own equivalent uses.
4. `_sync_from_date_max_to_to_date` — keeps the "from" picker's
   `max_date_allowed` in sync with the current "to" value.
5. `_validate_date_range` — shows an inline message when "to" is not
   strictly after "from" (FR-007), without touching the rendered chart/table.
6. `_render_histogram_and_table` — the single callback that (re-)fetches and
   renders both the chart and the table whenever the account, from-date, or
   to-date changes.
7. `_apply_date_range_shortcut` — five `n_clicks` Inputs (the same shared
   shortcut buttons Overview/Positions/Performance use); this page's own
   `_SHORTCUT_CODE_BY_BUTTON_ID` maps the button labeled "10Y" to the new
   `SHORTCUT_10Y` (not `SHORTCUT_YTD`/`SHORTCUT_ALL`) — the same page-local
   remapping Performance already uses for its "ITD" label.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import Any

import dash
import dash_bootstrap_components as dbc
import structlog
from dash import Input, Output, State, callback, ctx, dash_table, dcc, html
from dash.exceptions import PreventUpdate

from config.settings import Settings
from src.components.date_range_controls import (
    SHORTCUT_1Y,
    SHORTCUT_3Y,
    SHORTCUT_5Y,
    SHORTCUT_10Y,
    SHORTCUT_ALL,
    _earliest_from_date,
    _last_business_day,
    _shortcut_from_date,
)
from src.exceptions import PortfolioAnalysisServiceError
from src.models.portfolio_analysis import AccountSummary
from src.pages import _var_controls
from src.pages._risk_chart import build_figure
from src.pages._risk_table import build_rows
from src.pages._var_backtest_panel import build_panel as build_var_backtest_panel
from src.pages._var_chart import build_figures as build_var_figures
from src.services.portfolio_analysis_client import (
    HttpPortfolioAnalysisClient,
    PortfolioAnalysisClient,
)

# (pnl_basis, min_quality) pairs fetched on every account/date/look-back refetch
# (research.md #1 — both are server-side parameters that change the computed
# backtest statistics, not just their display).
_BACKTEST_PNL_BASES = ("hypothetical", "ladder")
_BACKTEST_MIN_QUALITIES = ("ok", "degraded")

dash.register_page(__name__, path="/risk", name="Risk")

logger = structlog.get_logger(__name__)

# See performance.py's own `_PAGE_SCOPE_INPUT` docstring for why every
# callback whose Output is one of the shared parameters-bar controls needs a
# page-local scoping Input: Dash derives an `allow_duplicate=True` Output's
# callback id by hashing only its Inputs, and every account-scoped page
# shares the same Outputs from the same shared Inputs.
_PAGE_SCOPE_INPUT = "risk-mount-trigger"

# Must match src/layout/shell.py's shared shortcut button ids. The button
# labeled "10Y" on this page shares the same DOM id as every other page's
# first shortcut button — only its page-local *code mapping* differs.
_SHORTCUT_CODE_BY_BUTTON_ID = {
    "overview-shortcut-ytd": SHORTCUT_10Y,
    "overview-shortcut-1y": SHORTCUT_1Y,
    "overview-shortcut-3y": SHORTCUT_3Y,
    "overview-shortcut-5y": SHORTCUT_5Y,
    "overview-shortcut-all": SHORTCUT_ALL,
}

_REFRESH_DISABLED_IDS = [
    "app-parameters-account",
    "app-parameters-from-date",
    "app-parameters-to-date",
    *_SHORTCUT_CODE_BY_BUTTON_ID,
]

_VAR_REFRESH_DISABLED_IDS = [*_REFRESH_DISABLED_IDS, "risk-var-lookback"]

_STATISTIC_COLUMNS = [
    {"name": "statistic", "id": "statistic"},
    {"name": "value", "id": "value"},
]


def _get_client() -> PortfolioAnalysisClient:
    """Factory for the outbound client.

    A plain module-level function (not a module-level instance) so BDD tests
    can monkeypatch `src.pages.risk._get_client` with a fake before the
    browser triggers any callback, without needing a running
    portfolio-analysis-service instance.
    """
    settings = Settings()
    return HttpPortfolioAnalysisClient(
        base_url=settings.portfolio_analysis_service_url,
        timeout_seconds=settings.request_timeout_seconds,
    )


def _empty_state(message: str) -> html.Div:
    return html.Div(message, id="risk-empty-state", className="text-center text-muted p-5")


def _error_state(message: str) -> html.Div:
    return html.Div(message, id="risk-error-state", className="text-center text-danger p-5")


def _render_chart_and_table(
    client: PortfolioAnalysisClient,
    account_name: str,
    from_date: str,
    to_date: str,
) -> tuple[html.Div | dcc.Graph, Any]:
    """Fetch and shape a chart + table, or matching empty/error states.

    Returns `Any` rather than `dash_table.DataTable` for the table half: see
    `_positions_chart.py::_build_comparison_table`'s docstring for why mypy
    cannot resolve Dash's own generated submodule type here.

    Args:
        client: The portfolio-analysis-service client to call.
        account_name: The selected account.
        from_date: ISO start date.
        to_date: ISO end date.

    Returns:
        A `(chart, table)` pair: both `dcc.Graph`/`dash_table.DataTable` on
        success, or matching empty/error-state `Div`s on either output when
        there is nothing (or nothing valid) to show.
    """
    try:
        response = client.get_return_histogram(
            account_name=account_name,
            start=date.fromisoformat(from_date),
            end=date.fromisoformat(to_date),
        )
    except PortfolioAnalysisServiceError:
        logger.error("risk_fetch_failed", account_name=account_name)
        message = (
            "Could not load risk data from portfolio-analysis-service. Please try again shortly."
        )
        return _error_state(message), _error_state(message)

    if response.statistics.count == 0:
        message = "No data is available for the selected account and date range."
        return _empty_state(message), _empty_state(message)

    chart = dcc.Graph(
        id="risk-histogram-chart",
        figure=build_figure(response.histogram, response.statistics),
        style={"height": "500px"},
    )
    table = dash_table.DataTable(  # type: ignore[attr-defined]
        id="risk-statistics-table",
        columns=_STATISTIC_COLUMNS,
        data=build_rows(response.statistics),
        style_cell={"textAlign": "left", "padding": "8px"},
        style_header={"fontWeight": "bold"},
    )
    return chart, table


layout = html.Div(
    [
        # Fires its one tick ~200ms after every mount of this layout (first
        # load AND every revisit), mirroring every other page's own
        # mount-trigger pattern.
        dcc.Interval(id="risk-mount-trigger", interval=200, max_intervals=1),
        dcc.Store(id="risk-accounts-store"),
        dcc.Store(id="risk-var-store"),
        dcc.Store(id="risk-var-methods-store"),
        dcc.Store(id="risk-var-confidence-last-nonempty"),
        dbc.Tabs(
            [
                dbc.Tab(
                    label="Return Histogram",
                    tab_id="risk-tab-histogram",
                    children=dbc.Row(
                        [
                            dbc.Col(
                                dcc.Loading(
                                    html.Div(
                                        _empty_state("Loading return histogram…"),
                                        id="risk-chart-container",
                                    )
                                ),
                                width=7,
                            ),
                            dbc.Col(
                                dcc.Loading(html.Div(html.Div(), id="risk-table-container")),
                                width=5,
                            ),
                        ]
                    ),
                ),
                dbc.Tab(
                    label="Value at Risk",
                    tab_id="risk-tab-var",
                    children=html.Div(
                        [
                            html.Div(id="risk-var-stale-banner"),
                            html.Div(
                                _var_controls.build_controls(None), id="risk-var-controls-container"
                            ),
                            dbc.Row(
                                [
                                    dbc.Col(
                                        dcc.Loading(
                                            html.Div(
                                                _empty_state("Loading Value at Risk…"),
                                                id="risk-var-chart-container",
                                            )
                                        ),
                                        width=9,
                                    ),
                                    dbc.Col(
                                        dcc.Loading(
                                            html.Div(html.Div(), id="risk-var-backtest-panel")
                                        ),
                                        width=3,
                                    ),
                                ]
                            ),
                        ],
                        className="pt-3",
                    ),
                ),
            ],
            id="risk-tabs",
        ),
    ],
    className="p-3",
)


@callback(
    Output("risk-accounts-store", "data"),
    Output("app-parameters-account", "options"),
    Output("risk-chart-container", "children", allow_duplicate=True),
    Output("risk-table-container", "children", allow_duplicate=True),
    Input("risk-mount-trigger", "n_intervals"),
    prevent_initial_call=True,
)
def _fetch_accounts(_n_intervals: int) -> tuple[Any, ...]:
    """Fetch /v1/accounts on every Risk mount."""
    client = _get_client()
    try:
        accounts = client.list_accounts()
    except PortfolioAnalysisServiceError:
        logger.error("risk_mount_fetch_failed")
        message = (
            "Could not load accounts from portfolio-analysis-service. Please try again shortly."
        )
        return dash.no_update, dash.no_update, _error_state(message), _error_state(message)

    account_options = [{"label": a.account_name, "value": a.account_name} for a in accounts]
    return (
        [a.model_dump(mode="json") for a in accounts],
        account_options,
        dash.no_update,
        dash.no_update,
    )


@callback(
    Output("app-parameters-account", "value", allow_duplicate=True),
    Input("risk-accounts-store", "data"),
    Input(_PAGE_SCOPE_INPUT, "max_intervals"),
    prevent_initial_call=True,
)
def _apply_default_account(
    accounts_data: list[dict[str, Any]] | None,
    _page_scope: int | None,
) -> str:
    """Auto-select the alphabetically-first account once accounts are loaded."""
    if not accounts_data:
        raise PreventUpdate
    names = sorted(a["account_name"] for a in accounts_data)
    return names[0]


@callback(
    Output("app-parameters-from-date", "date", allow_duplicate=True),
    Output("app-parameters-to-date", "date", allow_duplicate=True),
    Input("app-parameters-account", "value"),
    Input(_PAGE_SCOPE_INPUT, "max_intervals"),
    State("risk-accounts-store", "data"),
    prevent_initial_call=True,
)
def _sync_date_range_to_selected_account(
    account_name: str | None,
    _page_scope: int | None,
    accounts_data: list[dict[str, Any]] | None,
) -> tuple[Any, Any]:
    """Reset from/to dates to the selected account's own full history.

    Fires both on the initial default-account selection and on every
    subsequent manual account switch.
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
    Output("app-parameters-from-date", "max_date_allowed", allow_duplicate=True),
    Input("app-parameters-to-date", "date"),
    Input(_PAGE_SCOPE_INPUT, "max_intervals"),
    prevent_initial_call=True,
)
def _sync_from_date_max_to_to_date(to_date: str | None, _page_scope: int | None) -> Any:
    """Keep "from" from ever exceeding the current "to" value."""
    if not to_date:
        raise PreventUpdate
    return to_date


@callback(
    Output("risk-chart-container", "children"),
    Output("risk-table-container", "children"),
    Input("app-parameters-account", "value"),
    Input("app-parameters-from-date", "date"),
    Input("app-parameters-to-date", "date"),
    running=[
        (Output(component_id, "disabled"), True, False) for component_id in _REFRESH_DISABLED_IDS
    ],
    prevent_initial_call=True,
)
def _render_histogram_and_table(
    account_name: str | None,
    from_date: str | None,
    to_date: str | None,
) -> tuple[html.Div | dcc.Graph, Any]:
    """Re-fetch and re-render whenever account/date selection changes."""
    if not account_name or not from_date or not to_date:
        raise PreventUpdate
    if date.fromisoformat(to_date) <= date.fromisoformat(from_date):
        raise PreventUpdate

    client = _get_client()
    return _render_chart_and_table(client, account_name, from_date, to_date)


@callback(
    Output("risk-date-validation", "children"),
    Input("app-parameters-from-date", "date"),
    Input("app-parameters-to-date", "date"),
    Input(_PAGE_SCOPE_INPUT, "max_intervals"),
    prevent_initial_call=True,
)
def _validate_date_range(
    from_date: str | None, to_date: str | None, _page_scope: int | None
) -> str:
    """Show an inline message when "to" is not strictly after "from" (FR-007)."""
    if not from_date or not to_date:
        raise PreventUpdate
    if date.fromisoformat(to_date) <= date.fromisoformat(from_date):
        return "The end date must be after the start date."
    return ""


@callback(
    Output("app-parameters-from-date", "date", allow_duplicate=True),
    Output("app-parameters-to-date", "date", allow_duplicate=True),
    Input("overview-shortcut-ytd", "n_clicks"),
    Input("overview-shortcut-1y", "n_clicks"),
    Input("overview-shortcut-3y", "n_clicks"),
    Input("overview-shortcut-5y", "n_clicks"),
    Input("overview-shortcut-all", "n_clicks"),
    Input(_PAGE_SCOPE_INPUT, "max_intervals"),
    State("app-parameters-account", "value"),
    State("risk-accounts-store", "data"),
    prevent_initial_call=True,
)
def _apply_date_range_shortcut(
    _10y: int | None,
    _1y: int | None,
    _3y: int | None,
    _5y: int | None,
    _all: int | None,
    _page_scope: int | None,
    account_name: str | None,
    accounts_data: list[dict[str, Any]] | None,
) -> tuple[Any, Any]:
    """Apply a Reporting Period Shortcut's date range.

    This page's own `_SHORTCUT_CODE_BY_BUTTON_ID` maps the button labeled
    "10Y" (shared DOM id `overview-shortcut-ytd`) to `SHORTCUT_10Y`, the only
    divergence from every other page's copy of this mapping.
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
    Output("risk-var-methods-store", "data"),
    Output("risk-var-controls-container", "children"),
    Input("risk-mount-trigger", "n_intervals"),
    prevent_initial_call=True,
)
def _fetch_var_methods(_n_intervals: int) -> tuple[Any, Any]:
    """Fetch /v1/risk/var/methods once per mount (research.md #2 -- account-independent)."""
    client = _get_client()
    try:
        methods = client.get_var_methods()
    except PortfolioAnalysisServiceError:
        logger.error("risk_var_methods_fetch_failed")
        message = (
            "Could not load VaR method configuration from portfolio-analysis-service. "
            "Please try again shortly."
        )
        return None, _error_state(message)

    return methods.model_dump(mode="json"), _var_controls.build_controls(methods)


@callback(
    Output("risk-var-confidence-last-nonempty", "data"),
    Input("risk-var-confidence", "value"),
    prevent_initial_call=True,
)
def _track_last_nonempty_confidence(value: list[int] | None) -> list[int]:
    """Record the confidence selection whenever it is non-empty (FR-003's own history)."""
    if not value:
        raise PreventUpdate
    return value


@callback(
    Output("risk-var-confidence", "value", allow_duplicate=True),
    Input("risk-var-confidence", "value"),
    State("risk-var-confidence-last-nonempty", "data"),
    prevent_initial_call=True,
)
def _guard_confidence_selection(
    value: list[int] | None, last_nonempty: list[int] | None
) -> list[int]:
    """Revert an attempted clear-to-empty back to the last non-empty selection (FR-003).

    The confidence multi-select must always retain at least one selected level (spec.md
    Edge Cases) -- this is an interaction constraint on the control, not a data property,
    so it lives here rather than in `_var_controls.build_controls()`.
    """
    if value:
        raise PreventUpdate
    if not last_nonempty:
        raise PreventUpdate
    return last_nonempty


@callback(
    Output("risk-var-store", "data"),
    Input("app-parameters-account", "value"),
    Input("app-parameters-from-date", "date"),
    Input("app-parameters-to-date", "date"),
    Input("risk-var-lookback", "value"),
    running=[
        (Output(component_id, "disabled"), True, False)
        for component_id in _VAR_REFRESH_DISABLED_IDS
    ],
    prevent_initial_call=True,
)
def _fetch_var_data(
    account_name: str | None,
    from_date: str | None,
    to_date: str | None,
    lookback: str | None,
) -> Any:
    """Fetch the series once, the backtest four times, and status once -- concurrently.

    research.md #1: `pnl_basis` and `min_quality` are server-side parameters that change
    the computed backtest statistics, not just their display, so both states of both are
    pre-fetched here rather than refetched when the PnL-basis/hide-degraded controls
    change (FR-010/FR-012). research.md #6: the six calls run concurrently via a thread
    pool so the combined refetch does not serialize to ~six times a single call's latency.
    """
    if not account_name or not from_date or not to_date or not lookback:
        raise PreventUpdate

    client = _get_client()
    start = date.fromisoformat(from_date)
    end = date.fromisoformat(to_date)

    def _fetch_series() -> dict[str, Any]:
        return client.get_var_series(account_name, start, end, lookback).model_dump(mode="json")

    def _fetch_backtest(pnl_basis: str, min_quality: str) -> dict[str, Any]:
        return client.get_var_backtest(
            account_name, start, end, lookback, pnl_basis, min_quality
        ).model_dump(mode="json")

    def _fetch_status() -> dict[str, Any]:
        return client.get_var_status(account_name).model_dump(mode="json")

    try:
        with ThreadPoolExecutor(max_workers=6) as pool:
            series_future = pool.submit(_fetch_series)
            backtest_futures = {
                (pnl_basis, min_quality): pool.submit(_fetch_backtest, pnl_basis, min_quality)
                for pnl_basis in _BACKTEST_PNL_BASES
                for min_quality in _BACKTEST_MIN_QUALITIES
            }
            status_future = pool.submit(_fetch_status)

            series_data = series_future.result()
            backtest_data: dict[str, dict[str, Any]] = {
                pnl_basis: {} for pnl_basis in _BACKTEST_PNL_BASES
            }
            for (pnl_basis, min_quality), future in backtest_futures.items():
                backtest_data[pnl_basis][min_quality] = future.result()
            status_data = status_future.result()
    except PortfolioAnalysisServiceError as exc:
        logger.error("risk_var_data_fetch_failed", account_name=account_name, detail=str(exc))
        return {"fetch_error": str(exc)}

    return {
        "account_name": account_name,
        "lookback_code": lookback,
        "series": series_data,
        "backtest": backtest_data,
        "status": status_data,
        "fetch_error": None,
    }


@callback(
    Output("risk-var-chart-container", "children"),
    Output("risk-var-backtest-panel", "children"),
    Input("risk-var-store", "data"),
    Input("risk-var-confidence", "value"),
    Input("risk-var-units", "value"),
    Input("risk-var-pnl-basis", "value"),
    Input("risk-var-hide-degraded", "value"),
    Input("risk-var-show-es", "value"),
    prevent_initial_call=True,
)
def _render_var_view(
    store_data: dict[str, Any] | None,
    confidence_bp: list[int] | None,
    units: str | None,
    pnl_basis: str | None,
    hide_degraded: bool | None,
    show_es: bool | None,
) -> tuple[Any, Any]:
    """Render the chart and backtest panel from already-fetched data only (FR-010/FR-012).

    This callback makes no client call -- every value it plots comes from `store_data`,
    which `_fetch_var_data` already populated. Confidence/units/PnL-basis/hide-degraded/
    show-ES are all `Input`s here (never to `_fetch_var_data`), which is what makes them
    "instant" (US3).
    """
    if not store_data:
        raise PreventUpdate
    if store_data.get("fetch_error"):
        message = (
            "Could not load Value at Risk data from portfolio-analysis-service. "
            "Please try again shortly."
        )
        return _error_state(message), _error_state(message)

    series = store_data["series"]["series"]
    if not series:
        if store_data["status"]["computed_range"] is None:
            message = (
                "No VaR calculation has ever been run for this account. Run one via the "
                "portfolio-analysis-service API, then reload this page."
            )
        else:
            message = "No Value at Risk data is available for the selected range."
        return _empty_state(message), _empty_state(message)

    levels = confidence_bp or []
    figure = build_var_figures(
        series,
        selected_confidence_bp=levels,
        units=units or "gbp",
        pnl_basis=pnl_basis or "hypothetical",
        hide_degraded=bool(hide_degraded),
        show_es=bool(show_es),
    )
    chart = dcc.Graph(id="risk-var-chart", figure=figure, style={"height": "500px"})
    panel = build_var_backtest_panel(
        store_data["backtest"],
        selected_confidence_bp=levels,
        pnl_basis=pnl_basis or "hypothetical",
        hide_degraded=bool(hide_degraded),
    )
    return chart, panel


@callback(
    Output("risk-var-stale-banner", "children"),
    Input("risk-var-store", "data"),
    prevent_initial_call=True,
)
def _render_stale_banner(store_data: dict[str, Any] | None) -> Any:
    """Show a banner naming how many dates the VaR store is behind the ladder (FR-014)."""
    if not store_data:
        raise PreventUpdate
    if store_data.get("fetch_error"):
        return None
    missing_dates = store_data["status"]["missing_dates"]
    if not missing_dates:
        return None
    return dbc.Alert(
        f"The VaR calculation is behind the account's trading activity by {missing_dates} "
        "date(s). The chart and panel below reflect whatever has been calculated so far.",
        color="warning",
        id="risk-var-stale-banner-alert",
    )
