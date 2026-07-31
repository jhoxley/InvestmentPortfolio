"""Composes header + sidebar + content frame + parameters bar (FR-004, FR-005, FR-008).

The parameters bar is route-aware (016): on the Overview route it hosts real
Account/date-range controls; on every other route it keeps 015's original
static, disabled placeholder unchanged (research.md #7 in
specs/016-link-real-portfolio).
"""

from __future__ import annotations

import dash
import dash_bootstrap_components as dbc
from dash import Dash, Input, Output, dcc, html

from config.content import ContentConfig
from src.components.date_range_controls import build_account_date_controls
from src.components.footer import build_footer
from src.components.header import build_header
from src.components.sidebar import build_sidebar

_CONTENT_WIDTH = 10  # out of 12 grid columns — the remainder of the sidebar's 2
_OVERVIEW_PATH = "/"
_POSITIONS_PATH = "/positions"
_PERFORMANCE_PATH = "/performance"


def _build_static_parameters_bar() -> list:
    """Illustrative, disabled placeholder controls (015 spec Assumptions; FR-005).

    Rendered on every route except Overview.
    """
    account_selector = dbc.Select(
        id="app-parameters-account",
        options=[{"label": "All accounts", "value": "all"}],
        value="all",
        disabled=True,
    )
    date_range = dbc.Input(
        id="app-parameters-daterange",
        type="text",
        value="Placeholder date range",
        disabled=True,
    )
    return [
        dbc.Col(
            html.Label("Account", htmlFor="app-parameters-account"),
            width="auto",
        ),
        dbc.Col(account_selector, width=3),
        dbc.Col(
            html.Label("Date range", htmlFor="app-parameters-daterange"),
            width="auto",
        ),
        dbc.Col(date_range, width=3),
    ]


def _build_overview_parameters_bar() -> list:
    """Real Account selector + From/To date pickers + shortcut buttons (016/017).

    Options/values are populated by a callback in src/pages/overview.py once
    the page has fetched /v1/accounts — this only builds the empty controls.
    Shared with the Positions page (018) via
    src/components/date_range_controls.py.
    """
    return build_account_date_controls()


def _build_positions_parameters_bar() -> list:
    """Real Account/From/To/shortcut controls (shared) + Positions-only controls (018).

    Options/values are populated by callbacks in src/pages/positions.py once
    the page has fetched /v1/accounts, /v1/positions/attributes, and
    /v1/accounts/{account}/positions — this only builds the empty controls.
    """
    stacked_toggle = dbc.Switch(
        id="positions-parameters-stacked-toggle",
        label="Stacked area graph",
        value=False,
        className="d-inline-block",
    )
    position_filter = dcc.Dropdown(
        id="positions-parameters-position-filter",
        options=[],
        value=[],
        multi=True,
        searchable=True,
        placeholder="All positions",
    )
    return [
        *build_account_date_controls(),
        dbc.Col(stacked_toggle, width="auto"),
        dbc.Col(
            html.Label("Positions", htmlFor="positions-parameters-position-filter"),
            width="auto",
        ),
        dbc.Col(position_filter, width=4),
    ]


def _build_performance_parameters_bar() -> list:
    """Real Account/From/To/shortcut controls only — no Performance-only controls (020).

    Options/values are populated by callbacks in src/pages/performance.py
    once the page has fetched /v1/accounts + /v1/performance/attributes —
    this only builds the empty controls. The first shortcut button is
    relabeled "ITD" (in place of "YtD") per spec Clarifications; no
    stacked-area toggle or other chart-mode control is added (FR-005).
    """
    return build_account_date_controls(first_shortcut_label="ITD")


def _render_parameters_bar(pathname: str | None) -> list:
    if pathname == _OVERVIEW_PATH:
        return _build_overview_parameters_bar()
    if pathname == _POSITIONS_PATH:
        return _build_positions_parameters_bar()
    if pathname == _PERFORMANCE_PATH:
        return _build_performance_parameters_bar()
    return _build_static_parameters_bar()


def build_shell(app: Dash, content: ContentConfig) -> html.Div:
    parameters_bar = dbc.Row(
        _build_static_parameters_bar(),
        id="app-parameters-bar",
        className="g-2 align-items-center border-bottom py-2 mb-3",
    )
    content_frame = dbc.Col(
        [
            parameters_bar,
            html.Div(dash.page_container, id="app-page-content"),
        ],
        id="app-content-frame",
        width=_CONTENT_WIDTH,
    )
    body = dbc.Row(
        [build_sidebar(content), content_frame],
        className="g-0",
    )

    # Registered here (not as a bare `@callback` at module level) so it is
    # bound after `app` already exists — Dash Pages' internal routing
    # component (`_pages_location`) is only guaranteed present once
    # `Dash(use_pages=True)` has run, mirroring why `register_page` itself
    # must run after app instantiation.
    app.callback(
        Output("app-parameters-bar", "children"),
        Input("_pages_location", "pathname"),
    )(_render_parameters_bar)

    return html.Div([build_header(content), body, build_footer(content)])
