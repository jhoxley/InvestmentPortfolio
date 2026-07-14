"""Positions placeholder page (User Story 2)."""

import dash
from dash import html

dash.register_page(__name__, path="/positions", name="Positions")

layout = html.Div(
    "Positions placeholder content — real position data arrives in a future feature.",
    className="p-3",
)
