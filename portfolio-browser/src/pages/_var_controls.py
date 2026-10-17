"""Pure builder for the Value at Risk section's own controls block (026-var-risk-view;
no longer includes a "Look-back" control as of 027 -- see module docstring note there).

Kept out of risk.py so it stays importable from a plain unit test, mirroring
`_risk_chart.py`'s/`_risk_table.py`'s own separation-of-concerns rationale.
"""

from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import html

from src.models.portfolio_analysis import VarMethodsResponse


def _format_confidence_label(confidence_bp: int) -> str:
    """Format a basis-point confidence level as a percentage label (e.g. 9750 -> '97.5%')."""
    return f"{confidence_bp / 100:g}%"


def build_controls(methods: VarMethodsResponse | None) -> html.Div:
    """Build the Value at Risk section's own controls block.

    027: no longer renders its own "Look-back" select -- the page's single shared range
    control (shortcut buttons) drives the look-back instead (research.md #5 in
    specs/027-risk-page-cleanup); `methods` is still needed here for the confidence-level
    options.

    Args:
        methods: The fetched VarMethodsResponse, or None before it has loaded (renders a
            disabled placeholder with no options yet).

    Returns:
        An html.Div containing the confidence-level multi-select, units toggle, PnL-basis
        toggle, "hide degraded" toggle and "show ES" toggle.
    """
    if methods is None:
        return html.Div("Loading controls…", id="risk-var-controls", className="text-muted")

    confidence_options = [
        {"label": _format_confidence_label(bp), "value": bp} for bp in methods.confidence_levels_bp
    ]

    return html.Div(
        [
            dbc.Col(html.Label("Confidence", htmlFor="risk-var-confidence"), width="auto"),
            dbc.Col(
                dbc.Checklist(
                    id="risk-var-confidence",
                    options=confidence_options,
                    value=list(methods.confidence_levels_bp),
                    inline=True,
                ),
                width="auto",
            ),
            dbc.Col(
                dbc.RadioItems(
                    id="risk-var-units",
                    options=[{"label": "£", "value": "gbp"}, {"label": "%", "value": "pct"}],
                    value="gbp",
                    inline=True,
                ),
                width="auto",
            ),
            dbc.Col(
                dbc.RadioItems(
                    id="risk-var-pnl-basis",
                    options=[
                        {"label": "Hypothetical", "value": "hypothetical"},
                        {"label": "Ladder", "value": "ladder"},
                    ],
                    value="hypothetical",
                    inline=True,
                ),
                width="auto",
            ),
            dbc.Col(
                dbc.Switch(
                    id="risk-var-hide-degraded",
                    label="Hide degraded-quality dates",
                    value=False,
                ),
                width="auto",
            ),
            dbc.Col(
                dbc.Switch(id="risk-var-show-es", label="Show Expected Shortfall", value=False),
                width="auto",
            ),
        ],
        id="risk-var-controls",
        className="d-flex flex-wrap align-items-center gap-2 mb-2",
    )
