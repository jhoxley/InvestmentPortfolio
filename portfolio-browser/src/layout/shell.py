"""Composes header + sidebar + content frame + parameters bar (FR-004, FR-005, FR-008).

The parameters bar is route-aware (016): on the Overview route it hosts real
Account/date-range controls; on every other route it keeps 015's original
static, disabled placeholder unchanged (research.md #7 in
specs/016-link-real-portfolio).
"""

from __future__ import annotations

from datetime import date

import dash
import dash_bootstrap_components as dbc
from dash import Dash, Input, Output, dcc, html

from config.content import ContentConfig
from src.components.footer import build_footer
from src.components.header import build_header
from src.components.sidebar import build_sidebar

_CONTENT_WIDTH = 10  # out of 12 grid columns — the remainder of the sidebar's 2
_OVERVIEW_PATH = "/"


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


_SHORTCUT_BUTTONS = [
    ("overview-shortcut-ytd", "YtD"),
    ("overview-shortcut-1y", "1Y"),
    ("overview-shortcut-3y", "3Y"),
    ("overview-shortcut-5y", "5Y"),
    ("overview-shortcut-all", "All"),
]


def _build_shortcut_buttons() -> dbc.Col:
    """Five Reporting Period Shortcut buttons (017; FR-001).

    Click handling (which date range each computes, and disabling them
    during a refresh per FR-013) lives in src/pages/overview.py — this only
    builds the buttons themselves.
    """
    buttons = [
        dbc.Button(label, id=button_id, size="sm", color="secondary", outline=True)
        for button_id, label in _SHORTCUT_BUTTONS
    ]
    return dbc.Col(dbc.ButtonGroup(buttons), width="auto")


def _build_overview_parameters_bar() -> list:
    """Real Account selector + From/To date pickers + shortcut buttons (016/017).

    Options/values are populated by a callback in src/pages/overview.py once
    the page has fetched /v1/accounts — this only builds the empty controls.
    """
    account_selector = dbc.Select(id="app-parameters-account", options=[], value=None)
    from_date = dcc.DatePickerSingle(id="app-parameters-from-date", placeholder="From")
    # max_date_allowed=today is static (today doesn't change within a session);
    # the "from" picker's max is kept in sync with the *current* "to" value
    # dynamically instead, via a callback (src/pages/overview.py, FR-015).
    to_date = dcc.DatePickerSingle(
        id="app-parameters-to-date", placeholder="To", max_date_allowed=date.today().isoformat()
    )
    return [
        dbc.Col(
            html.Label("Account", htmlFor="app-parameters-account"),
            width="auto",
        ),
        dbc.Col(account_selector, width=3),
        dbc.Col(
            html.Label("From", htmlFor="app-parameters-from-date"),
            width="auto",
        ),
        dbc.Col(from_date, width="auto"),
        dbc.Col(
            html.Label("To", htmlFor="app-parameters-to-date"),
            width="auto",
        ),
        dbc.Col(to_date, width="auto"),
        _build_shortcut_buttons(),
    ]


def _render_parameters_bar(pathname: str | None) -> list:
    if pathname == _OVERVIEW_PATH:
        return _build_overview_parameters_bar()
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
