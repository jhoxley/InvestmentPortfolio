"""Performance placeholder page (User Story 2)."""

import dash
from dash import html

dash.register_page(__name__, path="/performance", name="Performance")

layout = html.Div(
    "Performance placeholder content — real performance data arrives in a future feature.",
    className="p-3",
)
