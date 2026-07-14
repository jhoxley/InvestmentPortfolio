"""Income placeholder page (User Story 2)."""

import dash
from dash import html

dash.register_page(__name__, path="/income", name="Income")

layout = html.Div(
    "Income placeholder content — real income data arrives in a future feature.",
    className="p-3",
)
