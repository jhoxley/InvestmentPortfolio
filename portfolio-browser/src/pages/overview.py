"""Default placeholder page for the Overview nav section (FR-007 default)."""

import dash
from dash import html

dash.register_page(__name__, path="/", name="Overview")

layout = html.Div(
    "Overview placeholder content — real portfolio data arrives in a future feature.",
    className="p-3",
)
