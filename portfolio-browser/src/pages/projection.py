"""Projection page: historical market value plus one projected line per selected
return, out to a horizon-button or calendar-picked target date (022; replaces
the "Income" placeholder page).

Callback graph (see specs/022-projection-page/contracts/ui-contract.md):

1. `_fetch_accounts` — triggered by `projection-mount-trigger`; fetches
   /v1/accounts, populating the account dropdown and `projection-accounts-store`.
   No attribute fetch is needed — the four selectable returns are a fixed,
   page-local list (research.md #5), not API-driven.
2. `_apply_default_account` — once accounts are loaded, auto-selects the
   alphabetically-first account, mirroring every other page.
3. `_sync_start_date_to_selected_account` — whenever the selected account
   changes, resets `projection-start-date` to that account's most recently
   recorded date (FR-007; also the account-switch half of FR-015).
4. `_reset_target_and_returns_on_account_switch` — the rest of FR-015: clears
   the projection-target store and every selected-return toggle back to off.
5. `_apply_horizon_click` — the four horizon buttons; each resolves to
   `start_date + N years` and writes `projection-target-store`.
6. `_apply_calendar_pick` — validates a calendar pick is strictly later than
   the start date; on success writes `projection-target-store` and clears the
   validation message; on failure sets the validation message and leaves the
   store untouched (FR-014).
7. `_sync_target_display` — keeps the calendar control's own `date` in sync
   with whatever is currently in `projection-target-store`, however it got
   there (FR-006).
8. `_render_chart` — (re-)fetches and renders whenever the account, start
   date, target date, or any return toggle changes.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import dash
import structlog
from dash import ALL, Input, Output, State, callback, ctx, dcc, html
from dash.exceptions import PreventUpdate

from config.content import get_content_config
from config.settings import Settings
from src.components.attribute_toggles import build_attribute_toggles
from src.exceptions import PortfolioAnalysisServiceError
from src.models.portfolio_analysis import AttributeDefinition
from src.pages._projection_chart import _build_figure, _years_after
from src.services.portfolio_analysis_client import (
    HttpPortfolioAnalysisClient,
    PortfolioAnalysisClient,
)

dash.register_page(__name__, path="/projection", name="Projection")

logger = structlog.get_logger(__name__)

_TOGGLE_ID_TYPE = "projection-attribute-toggle"

# This page's own mount-trigger, used as a page-local scoping Input on every
# callback whose Output is one of the *shared* parameters-bar controls — the
# same collision-avoidance pattern documented at length in performance.py
# (specs/020-performance-page-chart) and reused unmodified here.
_PAGE_SCOPE_INPUT = "projection-mount-trigger"

# The four selectable returns are fixed and page-local (research.md #5) — the
# labels come from config/content.yaml's `projection.returns` list, sourced
# lazily inside the callback (not at import time) so tests that monkeypatch
# `get_content_config` still control it.


def _get_client() -> PortfolioAnalysisClient:
    """Factory for the outbound client.

    A plain module-level function (not a module-level instance) so BDD tests
    can monkeypatch `src.pages.projection._get_client` with a fake before the
    browser triggers any callback, without needing a running
    portfolio-analysis-service instance.
    """
    settings = Settings()
    return HttpPortfolioAnalysisClient(
        base_url=settings.portfolio_analysis_service_url,
        timeout_seconds=settings.request_timeout_seconds,
    )


def _projection_return_definitions() -> list[AttributeDefinition]:
    """Build the fixed, page-local return list from config (research.md #5)."""
    return [
        AttributeDefinition(
            name=item.label,
            description=f"The {item.label} return, projected forward from the start date.",
            source="performance",
        )
        for item in get_content_config().projection.returns
    ]


def _return_key_for_label(label: str) -> str:
    """Resolve a return's display label (e.g. "Ann. ITD") to its wire value (e.g. "itd_ann")."""
    for item in get_content_config().projection.returns:
        if item.label == label:
            return item.key
    raise KeyError(f"Unknown projection return label: {label!r}")


def _empty_state(message: str) -> html.Div:
    return html.Div(message, id="projection-empty-state", className="text-center text-muted p-5")


def _error_state(message: str) -> html.Div:
    return html.Div(message, id="projection-error-state", className="text-center text-danger p-5")


layout = html.Div(
    [
        # Fires its one tick ~200ms after every mount of this layout (first
        # load AND every revisit), mirroring every other page's own
        # mount-trigger pattern.
        dcc.Interval(id=_PAGE_SCOPE_INPUT, interval=200, max_intervals=1),
        dcc.Store(id="projection-accounts-store"),
        dcc.Store(id="projection-target-store"),
        html.Div(
            build_attribute_toggles(
                _projection_return_definitions(), _TOGGLE_ID_TYPE, frozenset()
            ),
            id="projection-attribute-toggles",
            className="mb-3",
        ),
        dcc.Loading(
            id="projection-chart-loading",
            children=html.Div(
                _empty_state("Loading account projection…"),
                id="projection-chart-container",
            ),
        ),
    ],
    className="p-3",
)


@callback(
    Output("projection-accounts-store", "data"),
    Output("app-parameters-account", "options"),
    Output("projection-chart-container", "children", allow_duplicate=True),
    Input(_PAGE_SCOPE_INPUT, "n_intervals"),
    prevent_initial_call=True,
)
def _fetch_accounts(_n_intervals: int) -> tuple[Any, ...]:
    """Fetch /v1/accounts on every Projection mount (FR-003)."""
    client = _get_client()
    try:
        accounts = client.list_accounts()
    except PortfolioAnalysisServiceError:
        logger.error("projection_mount_fetch_failed")
        return (
            dash.no_update,
            dash.no_update,
            _error_state(
                "Could not load accounts from portfolio-analysis-service. "
                "Please try again shortly."
            ),
        )

    account_options = [{"label": a.account_name, "value": a.account_name} for a in accounts]
    return (
        [a.model_dump(mode="json") for a in accounts],
        account_options,
        dash.no_update,
    )


@callback(
    Output("app-parameters-account", "value", allow_duplicate=True),
    Input("projection-accounts-store", "data"),
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
    Output("projection-start-date", "date", allow_duplicate=True),
    Input("app-parameters-account", "value"),
    Input(_PAGE_SCOPE_INPUT, "max_intervals"),
    State("projection-accounts-store", "data"),
    prevent_initial_call=True,
)
def _sync_start_date_to_selected_account(
    account_name: str | None,
    _page_scope: int | None,
    accounts_data: list[dict[str, Any]] | None,
) -> Any:
    """Default the start date to the account's most recently recorded date (FR-007, FR-015)."""
    if not account_name or not accounts_data:
        raise PreventUpdate
    account = next((a for a in accounts_data if a["account_name"] == account_name), None)
    if account is None:
        raise PreventUpdate
    resource = account.get("position_ladder") or account.get("capital_ledger")
    if resource is None:
        raise PreventUpdate
    return resource["to_date"]


@callback(
    Output("projection-target-store", "data", allow_duplicate=True),
    Output({"type": _TOGGLE_ID_TYPE, "name": ALL}, "value", allow_duplicate=True),
    Input("app-parameters-account", "value"),
    Input(_PAGE_SCOPE_INPUT, "max_intervals"),
    State({"type": _TOGGLE_ID_TYPE, "name": ALL}, "id"),
    prevent_initial_call=True,
)
def _reset_target_and_returns_on_account_switch(
    _account_name: str | None,
    _page_scope: int | None,
    toggle_ids: list[dict[str, str]],
) -> tuple[Any, list[bool]]:
    """Clear the projection target and every selected return on account switch (FR-015)."""
    return None, [False for _ in toggle_ids]


@callback(
    Output("projection-target-store", "data", allow_duplicate=True),
    *[
        Input(f"projection-horizon-{h.key}", "n_clicks")
        for h in get_content_config().projection.horizons
    ],
    State("projection-start-date", "date"),
    prevent_initial_call=True,
)
def _apply_horizon_click(*args: Any) -> Any:
    """Resolve a horizon button click to `start_date + N years` (FR-004)."""
    *_button_clicks, start_date_value = args
    if not start_date_value:
        raise PreventUpdate
    triggered_id = ctx.triggered_id
    if not isinstance(triggered_id, str) or not triggered_id.startswith("projection-horizon-"):
        raise PreventUpdate
    key = triggered_id.removeprefix("projection-horizon-")
    horizon = next((h for h in get_content_config().projection.horizons if h.key == key), None)
    if horizon is None:
        raise PreventUpdate
    start_date = date.fromisoformat(start_date_value)
    return _years_after(start_date, horizon.years).isoformat()


@callback(
    Output("projection-target-store", "data", allow_duplicate=True),
    Output("projection-date-validation", "children"),
    Input("projection-target-date", "date"),
    State("projection-start-date", "date"),
    State("projection-target-store", "data"),
    prevent_initial_call=True,
)
def _apply_calendar_pick(
    picked_date: str | None,
    start_date_value: str | None,
    current_target: str | None,
) -> tuple[Any, str]:
    """Validate and apply a calendar-picked projection target date (FR-005, FR-014)."""
    if not picked_date or not start_date_value:
        raise PreventUpdate
    # The calendar's own `date` prop is also written by `_sync_target_display`
    # below (a button click, or this same callback's own success path) —
    # ignore those echoes so this callback only reacts to a genuine pick.
    if picked_date == current_target:
        raise PreventUpdate
    start_date = date.fromisoformat(start_date_value)
    target_date = date.fromisoformat(picked_date)
    if target_date <= start_date:
        return dash.no_update, (
            f"Projection date must be later than the start date ({start_date.isoformat()})."
        )
    return picked_date, ""


@callback(
    Output("projection-target-date", "date"),
    Output("projection-target-date", "min_date_allowed"),
    Input("projection-target-store", "data"),
    Input("projection-start-date", "date"),
)
def _sync_target_display(target_date: str | None, start_date_value: str | None) -> tuple[Any, Any]:
    """Keep the calendar control's display in sync with the effective target date (FR-006)."""
    min_allowed: Any = dash.no_update
    if start_date_value:
        min_allowed = (date.fromisoformat(start_date_value) + timedelta(days=1)).isoformat()
    return (target_date if target_date else dash.no_update), min_allowed


@callback(
    Output("projection-chart-container", "children"),
    Input("app-parameters-account", "value"),
    Input("projection-start-date", "date"),
    Input("projection-target-store", "data"),
    Input({"type": _TOGGLE_ID_TYPE, "name": ALL}, "value"),
    State({"type": _TOGGLE_ID_TYPE, "name": ALL}, "id"),
)
def _render_chart(
    account_name: str | None,
    start_date_value: str | None,
    target_date_value: str | None,
    toggle_values: list[bool],
    toggle_ids: list[dict[str, str]],
) -> html.Div | dcc.Graph:
    """Fetch and render the projection chart, or an empty/error state (FR-009-FR-014, FR-017)."""
    if not account_name or not start_date_value or not target_date_value:
        return _empty_state("Select an account and a projection target date.")

    selected_labels = [
        toggle_id["name"]
        for toggle_id, selected in zip(toggle_ids, toggle_values, strict=True)
        if selected
    ]
    returns = [_return_key_for_label(label) for label in selected_labels]

    client = _get_client()
    try:
        response = client.get_projection(
            account_name=account_name,
            projection_date=date.fromisoformat(target_date_value),
            returns=returns,
            start=date.fromisoformat(start_date_value),
        )
    except PortfolioAnalysisServiceError:
        logger.error("projection_fetch_failed", account_name=account_name)
        return _error_state(
            "Could not load projection data from portfolio-analysis-service. "
            "Please try again shortly."
        )

    entries = [entry.model_dump(mode="json") for entry in response.entries]
    if not entries:
        return _empty_state("No data is available for the selected account.")

    figure = _build_figure(entries)
    return dcc.Graph(id="projection-chart", figure=figure, style={"height": "600px"})
