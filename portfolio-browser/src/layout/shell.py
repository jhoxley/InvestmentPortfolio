"""Composes header + sidebar + content frame + parameters bar (FR-004, FR-005, FR-008)."""

from __future__ import annotations

import dash
import dash_bootstrap_components as dbc
from dash import html

from config.content import ContentConfig
from src.components.footer import build_footer
from src.components.header import build_header
from src.components.sidebar import build_sidebar

_CONTENT_WIDTH = 10  # out of 12 grid columns — the remainder of the sidebar's 2


def _build_parameters_bar() -> dbc.Row:
    """Illustrative, disabled placeholder controls (spec Assumptions; FR-005)."""
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
    return dbc.Row(
        [
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
        ],
        id="app-parameters-bar",
        className="g-2 align-items-center border-bottom py-2 mb-3",
    )


def build_shell(content: ContentConfig) -> html.Div:
    content_frame = dbc.Col(
        [
            _build_parameters_bar(),
            html.Div(dash.page_container, id="app-page-content"),
        ],
        id="app-content-frame",
        width=_CONTENT_WIDTH,
    )
    body = dbc.Row(
        [build_sidebar(content), content_frame],
        className="g-0",
    )
    return html.Div([build_header(content), body, build_footer(content)])
