"""Pure builder for the Value at Risk tab's main + linked charts (026-var-risk-view, US1).

Kept out of risk.py so it stays importable from a plain unit test, mirroring
`_risk_chart.py`'s/`_performance_chart.py`'s own separation-of-concerns rationale. Every
value plotted here is read verbatim from the already-fetched series (Constitution
Principle I) -- the only arithmetic is negating VaR for the overlay line (a sign flip for
charting convention, not a new financial fact).
"""

from __future__ import annotations

from typing import Any

import plotly.graph_objects as go
from plotly.subplots import make_subplots

EXCEPTION_COLOR = "#d62728"
NORMAL_COLOR = "#1f77b4"
_VAR_LINE_COLOR = "#ff7f0e"
_ES_LINE_COLOR = "#9467bd"


def _pnl_field(pnl_basis: str) -> str:
    return "hypothetical_pnl_gbp" if pnl_basis == "hypothetical" else "ladder_pnl_gbp"


def _exception_field(pnl_basis: str) -> str:
    return "hypothetical_exception" if pnl_basis == "hypothetical" else "ladder_exception"


def _level(entry: dict[str, Any], confidence_bp: int) -> dict[str, Any] | None:
    return next((lvl for lvl in entry["levels"] if lvl["confidence_bp"] == confidence_bp), None)


def build_figures(
    series: list[dict[str, Any]],
    selected_confidence_bp: list[int],
    units: str,
    pnl_basis: str,
    hide_degraded: bool,
    show_es: bool,
) -> go.Figure:
    """Build the main PnL/VaR chart with a linked market-value subplot beneath it.

    Args:
        series: The already-fetched VarSeriesEntry dicts (from risk-var-store.data).
        selected_confidence_bp: Confidence levels (basis points) to overlay.
        units: "gbp" or "pct" -- which already-provided field to plot.
        pnl_basis: "hypothetical" or "ladder" -- which realised PnL field to plot.
        hide_degraded: When True, omit entries with quality == "degraded".
        show_es: When True, add a dashed Expected Shortfall overlay per selected level.

    Returns:
        A two-row go.Figure (PnL/VaR on row 1, market value/coverage on row 2), sharing
        one x-axis.
    """
    entries = [e for e in series if not (hide_degraded and e["quality"] == "degraded")]
    pnl_field = _pnl_field(pnl_basis)
    exception_field = _exception_field(pnl_basis)
    var_field = "var_gbp" if units == "gbp" else "var_pct"
    es_field = "es_gbp" if units == "gbp" else "es_pct"

    bar_entries = [e for e in entries if e[pnl_field] is not None]
    bar_x = [e["outcome_date"] for e in bar_entries]
    bar_y = [e[pnl_field] for e in bar_entries]
    bar_colors = [
        EXCEPTION_COLOR
        if any(
            (lvl := _level(e, bp)) is not None and lvl[exception_field]
            for bp in selected_confidence_bp
        )
        else NORMAL_COLOR
        for e in bar_entries
    ]

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.7, 0.3],
        specs=[[{}], [{"secondary_y": True}]],
    )
    fig.add_trace(
        go.Bar(x=bar_x, y=bar_y, marker={"color": bar_colors}, name="Realised PnL"), row=1, col=1
    )

    for confidence_bp in selected_confidence_bp:
        var_x: list[Any] = []
        var_y: list[float | None] = []
        es_y: list[float | None] = []
        for e in entries:
            level = _level(e, confidence_bp)
            var_x.append(e["outcome_date"])
            if level is None or level[var_field] is None:
                var_y.append(None)
                es_y.append(None)
            else:
                var_y.append(-level[var_field])
                es_y.append(None if level[es_field] is None else -level[es_field])

        label = f"{confidence_bp / 100:g}% VaR"
        fig.add_trace(
            go.Scatter(x=var_x, y=var_y, mode="lines", name=label, line={"color": _VAR_LINE_COLOR}),
            row=1,
            col=1,
        )
        if show_es:
            es_label = f"{confidence_bp / 100:g}% ES"
            fig.add_trace(
                go.Scatter(
                    x=var_x,
                    y=es_y,
                    mode="lines",
                    name=es_label,
                    line={"color": _ES_LINE_COLOR, "dash": "dash"},
                ),
                row=1,
                col=1,
            )

    fig.add_trace(
        go.Scatter(
            x=[e["outcome_date"] for e in entries],
            y=[e["total_value_gbp"] for e in entries],
            mode="lines",
            name="Total Market Value",
        ),
        row=2,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=[e["outcome_date"] for e in entries],
            y=[e["proxied_mv_pct"] + e["rescaled_mv_pct"] for e in entries],
            mode="lines",
            name="Proxied/Rescaled Share (%)",
        ),
        row=2,
        col=1,
        secondary_y=True,
    )

    fig.update_layout(margin={"t": 30, "b": 30})
    return fig
