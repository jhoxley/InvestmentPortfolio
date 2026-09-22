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
import dash_bootstrap_components as dbc
import structlog
from dash import ALL, Input, Output, State, callback, ctx, dcc, html
from dash.exceptions import PreventUpdate

from config.content import get_content_config
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
from src.components.periodicity_controls import (
    derive_periodicity,
    periodicity_button_states,
    periodicity_component_id,
)
from src.exceptions import PortfolioAnalysisServiceError
from src.models.portfolio_analysis import AccountSummary
from src.pages._overview_chart import _build_figure
from src.pages._overview_position_widgets import _build_pie_figure, _build_winners_losers_table
from src.services.portfolio_analysis_client import (
    HttpPortfolioAnalysisClient,
    PortfolioAnalysisClient,
)

dash.register_page(__name__, path="/", name="Overview")

logger = structlog.get_logger(__name__)

_DEFAULT_METRIC = "market_value"
_TOGGLE_ID_TYPE = "overview-attribute-toggle"

# This page's own mount-trigger, used as a page-local scoping Input on every
# callback whose Output is one of the *shared* parameters-bar controls. Dash
# derives an `allow_duplicate=True` Output's callback id by hashing ONLY the
# Inputs (`dash/_utils.py::create_callback_id`), so without a page-local Input
# this page's handlers collide with Positions'/Performance's identical
# Output+Input pairs and are silently overwritten at import time.
# Guarded by tests/unit/test_callback_registration.py.
_PAGE_SCOPE_INPUT = "overview-mount-trigger"

# Must match src/layout/shell.py's _SHORTCUT_BUTTONS ids.
_SHORTCUT_CODE_BY_BUTTON_ID = {
    "overview-shortcut-ytd": SHORTCUT_YTD,
    "overview-shortcut-1y": SHORTCUT_1Y,
    "overview-shortcut-3y": SHORTCUT_3Y,
    "overview-shortcut-5y": SHORTCUT_5Y,
    "overview-shortcut-all": SHORTCUT_ALL,
}

_PAGE_PREFIX = "overview"

# Loaded once at import time (021) — a broken periodicity config fails fast
# here, at module import, rather than surfacing later inside a callback.
_PERIODICITY_CONFIG = get_content_config().periodicity
_PERIODICITY_STORE_ID = "overview-periodicity-store"
_PERIODICITY_BUTTON_IDS = [
    periodicity_component_id(_PAGE_PREFIX, option.key) for option in _PERIODICITY_CONFIG.options
]


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
    periodicity: str,
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
        periodicity: The service-side aggregation interval currently in
            effect (021) — e.g. "day" or "annual".

    Returns:
        A `dcc.Graph` on success with data, or an empty/error-state `Div`.
    """
    try:
        response = client.get_timeseries(
            account_name=account_name,
            attributes=attributes,
            start=date.fromisoformat(from_date),
            end=date.fromisoformat(to_date),
            periodicity=periodicity,
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
        # Effective periodicity: {"value": <service-side value>, "explicit": bool}.
        # Starts empty — `_derive_periodicity_from_range` populates it as soon
        # as the default account's date range resolves (FR-008), so no chart
        # request fires before an interval is known.
        dcc.Store(id=_PERIODICITY_STORE_ID, data=None),
        html.Div(id="overview-attribute-toggles", className="mb-3"),
        dcc.Loading(
            id="overview-chart-loading",
            children=html.Div(
                _empty_state("Loading account performance…"),
                id="overview-chart-container",
            ),
        ),
        # New row (019): pie chart + "Biggest winners and losers" table.
        # xs=12/lg=6 stacks the two halves vertically below this project's
        # own tablet-width test convention (800px — above Bootstrap's
        # default md breakpoint of 768px, below its lg breakpoint of 992px;
        # research.md #5), side-by-side at desktop widths.
        dbc.Row(
            [
                dbc.Col(
                    dcc.Loading(
                        id="overview-pie-loading",
                        children=html.Div(
                            _empty_state("Loading position weights…"),
                            id="overview-pie-container",
                        ),
                    ),
                    xs=12,
                    lg=6,
                ),
                dbc.Col(
                    dcc.Loading(
                        id="overview-winners-losers-loading",
                        children=html.Div(
                            _empty_state("Loading biggest winners and losers…"),
                            id="overview-winners-losers-container",
                        ),
                    ),
                    xs=12,
                    lg=6,
                ),
            ],
            id="overview-position-widgets-row",
            className="mt-4 g-3",
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
    Output("app-parameters-account", "value", allow_duplicate=True),
    Input("overview-accounts-store", "data"),
    Input("overview-attributes-store", "data"),
    Input(_PAGE_SCOPE_INPUT, "max_intervals"),
    prevent_initial_call=True,
)
def _apply_default_account(
    accounts_data: list[dict[str, Any]] | None,
    attributes_data: list[dict[str, Any]] | None,
    _page_scope: int | None,
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
    Input(_PAGE_SCOPE_INPUT, "max_intervals"),
    State("overview-accounts-store", "data"),
    prevent_initial_call=True,
)
def _sync_date_range_to_selected_account(
    account_name: str | None,
    _page_scope: int | None,
    accounts_data: list[dict[str, Any]] | None,
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
    Output("app-parameters-from-date", "max_date_allowed", allow_duplicate=True),
    Input("app-parameters-to-date", "date"),
    Input(_PAGE_SCOPE_INPUT, "max_intervals"),
    prevent_initial_call=True,
)
def _sync_from_date_max_to_to_date(to_date: str | None, _page_scope: int | None) -> Any:
    """Keep "from" from ever exceeding the current "to" value (FR-015)."""
    if not to_date:
        raise PreventUpdate
    return to_date


@callback(
    Output(_PERIODICITY_STORE_ID, "data", allow_duplicate=True),
    *[Input(button_id, "n_clicks") for button_id in _PERIODICITY_BUTTON_IDS],
    Input(_PAGE_SCOPE_INPUT, "max_intervals"),
    prevent_initial_call=True,
)
def _apply_periodicity_click(*_args: int | None) -> dict[str, Any]:
    """Latch the clicked interval as the user's own explicit choice (FR-012).

    `n_clicks` only ever increments on a real click — never on a callback
    writing a prop — so this is the only place `explicit` is ever set to
    `True`. The date-range derive callback (US3, T027) never sets it, which
    is what makes an explicit choice survive a later date-range change
    regardless of callback ordering.
    """
    triggered = ctx.triggered_id
    if triggered is None or triggered not in _PERIODICITY_BUTTON_IDS:
        # Guards the mount-time fire from the page-scope Input.
        raise PreventUpdate
    option_key = triggered.rsplit("-", 1)[-1]
    return {"value": _PERIODICITY_CONFIG.value_for_key(option_key), "explicit": True}


@callback(
    Output(_PERIODICITY_STORE_ID, "data", allow_duplicate=True),
    Input("app-parameters-from-date", "date"),
    Input("app-parameters-to-date", "date"),
    Input(_PAGE_SCOPE_INPUT, "max_intervals"),
    State(_PERIODICITY_STORE_ID, "data"),
    prevent_initial_call=True,
)
def _derive_periodicity_from_range(
    from_date: str | None,
    to_date: str | None,
    _page_scope: int | None,
    store_data: dict[str, Any] | None,
) -> dict[str, Any]:
    """Derive the interval from the date-range span, unless the user has
    already chosen one explicitly (FR-008, FR-012).

    This callback must NEVER set `explicit` — only `_apply_periodicity_click`
    ever does that, which is what makes an explicit choice sticky across any
    later date-range change regardless of callback ordering (US3).
    """
    if store_data and store_data.get("explicit"):
        raise PreventUpdate
    if not from_date or not to_date:
        raise PreventUpdate
    derived_key = derive_periodicity(
        date.fromisoformat(from_date),
        date.fromisoformat(to_date),
        _PERIODICITY_CONFIG.thresholds,
    )
    return {"value": _PERIODICITY_CONFIG.value_for_key(derived_key), "explicit": False}


_PERIODICITY_STYLE_OUTPUTS = [
    output
    for button_id in _PERIODICITY_BUTTON_IDS
    for output in (Output(button_id, "active"), Output(button_id, "outline"))
]


@callback(
    *_PERIODICITY_STYLE_OUTPUTS,
    Input(_PERIODICITY_STORE_ID, "data"),
    prevent_initial_call=True,
)
def _style_periodicity_buttons(store_data: dict[str, Any] | None) -> tuple[bool, ...]:
    """Highlight exactly the button matching the effective interval (FR-011).

    The chart and the buttons both read the same store, so the control can
    never show an interval other than the one actually plotted.
    """
    effective = store_data.get("value") if store_data else None
    states = periodicity_button_states(effective, _PERIODICITY_CONFIG)
    flattened: list[bool] = []
    for state in states:
        flattened.append(state["active"])
        flattened.append(state["outline"])
    return tuple(flattened)


@callback(
    Output("overview-chart-container", "children"),
    Input("app-parameters-account", "value"),
    Input("app-parameters-from-date", "date"),
    Input("app-parameters-to-date", "date"),
    Input({"type": _TOGGLE_ID_TYPE, "name": ALL}, "value"),
    Input(_PERIODICITY_STORE_ID, "data"),
    State({"type": _TOGGLE_ID_TYPE, "name": ALL}, "id"),
    running=[
        (Output(button_id, "disabled"), True, False)
        for button_id in (*_SHORTCUT_CODE_BY_BUTTON_ID, *_PERIODICITY_BUTTON_IDS)
    ],
    prevent_initial_call=True,
)
def _render_chart(
    account_name: str | None,
    from_date: str | None,
    to_date: str | None,
    toggle_values: list[bool],
    periodicity_data: dict[str, Any] | None,
    toggle_ids: list[dict[str, str]],
) -> html.Div | dcc.Graph:
    """Re-fetch and re-render whenever account/date/metric/periodicity selection changes.

    One callback for all of US1's initial render, US2's account switch,
    US3's date-range change, US4's metric toggles, and 021's periodicity
    selection (FR-008, FR-009, FR-013) — Dash does not allow multiple
    callbacks to target the same Output, so this consolidates what tasks.md
    lists as separate "wire a callback" tasks into one shared implementation.
    """
    if not account_name or not from_date or not to_date or not periodicity_data:
        raise PreventUpdate

    toggled_attributes = [
        toggle_id["name"]
        for toggle_id, is_on in zip(toggle_ids, toggle_values, strict=True)
        if is_on
    ]
    if not toggled_attributes:
        return _empty_state("Select at least one metric to display a chart.")

    client = _get_client()
    return _render_timeseries(
        client, account_name, toggled_attributes, from_date, to_date, periodicity_data["value"]
    )


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
    State("overview-accounts-store", "data"),
    prevent_initial_call=True,
)
def _apply_date_range_shortcut(
    _ytd: int | None,
    _1y: int | None,
    _3y: int | None,
    _5y: int | None,
    _all: int | None,
    _page_scope: int | None,
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


@callback(
    Output("overview-pie-container", "children"),
    Output("overview-winners-losers-container", "children"),
    Input("app-parameters-account", "value"),
    Input("app-parameters-to-date", "date"),
    prevent_initial_call=True,
)
def _render_position_widgets(account_name: str | None, to_date: str | None) -> tuple[Any, Any]:
    """Render the position-weight pie chart and "Biggest winners and losers"

    table together, from one fetch (019; FR-002-FR-014).

    Deliberately independent of `_render_chart` — no shared `Input`/`Output`
    with it, and no `Input` on `app-parameters-from-date` or any attribute
    toggle (FR-010): both widgets are a single-date snapshot as of the "To"
    date only.
    """
    if not account_name or not to_date:
        # `/speckit-analyze` finding G1: without this guard, the callback
        # can be invoked with `to_date` still `None` while the
        # account-change -> date-sync chain is still resolving (initial
        # mount or account switch), raising on `date.fromisoformat(None)`.
        raise PreventUpdate

    client = _get_client()
    try:
        response = client.get_position_timeseries(
            account_name=account_name,
            positions=[],
            attributes=["market_value", "pnl", "book_cost"],
            start=date.fromisoformat(to_date),
            end=date.fromisoformat(to_date),
        )
    except PortfolioAnalysisServiceError:
        logger.error("overview_position_widgets_fetch_failed", account_name=account_name)
        message = (
            "Could not load position data from portfolio-analysis-service. "
            "Please try again shortly."
        )
        return _error_state(message), _error_state(message)

    entries = [entry.model_dump() for entry in response.entries]
    if not entries:
        message = "No position data is available for the selected account and date."
        return _empty_state(message), _empty_state(message)

    # No fixed `style` height here: _build_pie_figure() sets its own
    # `layout.height`, growing with the number of positions so the legend
    # (now below the chart, not to the right) always has room.
    pie = dcc.Graph(id="overview-pie-chart", figure=_build_pie_figure(entries))
    table = _build_winners_losers_table(entries)
    return pie, html.Div([html.H5("Biggest winners and losers", className="mt-2"), table])
