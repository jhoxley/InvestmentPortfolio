"""Unit tests for src/pages/_var_chart.py's pure build_figures() (026-var-risk-view, US1)."""

from __future__ import annotations

import plotly.graph_objects as go

from src.pages._var_chart import EXCEPTION_COLOR, build_figures


def _entry(
    on: str,
    outcome_date: str,
    quality: str = "ok",
    hypothetical_pnl_gbp: float | None = -10.0,
    ladder_pnl_gbp: float | None = -10.0,
    var_9500_gbp: float | None = 100.0,
    var_9500_pct: float | None = 10.0,
    es_9500_gbp: float | None = 120.0,
    hypothetical_exception: bool | None = False,
    ladder_exception: bool | None = False,
    total_value_gbp: float = 1000.0,
    proxied_mv_pct: float = 0.0,
    rescaled_mv_pct: float = 0.0,
) -> dict:
    return {
        "date": on,
        "outcome_date": outcome_date,
        "total_value_gbp": total_value_gbp,
        "scenario_count": 520,
        "actual_mv_pct": 100.0 - proxied_mv_pct - rescaled_mv_pct,
        "proxied_mv_pct": proxied_mv_pct,
        "rescaled_mv_pct": rescaled_mv_pct,
        "quality": quality,
        "quality_reason": None,
        "hypothetical_pnl_gbp": hypothetical_pnl_gbp,
        "ladder_pnl_gbp": ladder_pnl_gbp,
        "levels": [
            {
                "confidence_bp": 9500,
                "var_gbp": var_9500_gbp,
                "var_pct": var_9500_pct,
                "es_gbp": es_9500_gbp,
                "es_pct": es_9500_gbp / 10 if es_9500_gbp is not None else None,
                "hypothetical_exception": hypothetical_exception,
                "ladder_exception": ladder_exception,
            }
        ],
    }


def _figure_bar_trace(fig: go.Figure) -> go.Bar:
    bars = [t for t in fig.data if isinstance(t, go.Bar)]
    assert len(bars) == 1
    return bars[0]


def test_one_bar_per_entry_using_selected_pnl_basis() -> None:
    series = [_entry("2026-03-02", "2026-03-03", hypothetical_pnl_gbp=-10.0, ladder_pnl_gbp=-20.0)]
    fig = build_figures(
        series,
        selected_confidence_bp=[9500],
        units="gbp",
        pnl_basis="hypothetical",
        hide_degraded=False,
        show_es=False,
    )
    bar = _figure_bar_trace(fig)
    assert list(bar.y) == [-10.0]

    fig_ladder = build_figures(
        series,
        selected_confidence_bp=[9500],
        units="gbp",
        pnl_basis="ladder",
        hide_degraded=False,
        show_es=False,
    )
    bar_ladder = _figure_bar_trace(fig_ladder)
    assert list(bar_ladder.y) == [-20.0]


def test_pending_outcome_entry_is_skipped_from_bars() -> None:
    series = [_entry("2026-03-02", "2026-03-03", hypothetical_pnl_gbp=None, ladder_pnl_gbp=None)]
    fig = build_figures(
        series,
        selected_confidence_bp=[9500],
        units="gbp",
        pnl_basis="hypothetical",
        hide_degraded=False,
        show_es=False,
    )
    bar = _figure_bar_trace(fig)
    assert list(bar.x) == []


def test_overlay_line_uses_negative_var_with_gap_for_insufficient_quality() -> None:
    series = [
        _entry("2026-03-02", "2026-03-03", var_9500_gbp=100.0),
        _entry(
            "2026-03-03",
            "2026-03-04",
            quality="insufficient",
            var_9500_gbp=None,
            var_9500_pct=None,
            es_9500_gbp=None,
            hypothetical_exception=None,
            ladder_exception=None,
        ),
    ]
    fig = build_figures(
        series,
        selected_confidence_bp=[9500],
        units="gbp",
        pnl_basis="hypothetical",
        hide_degraded=False,
        show_es=False,
    )
    overlays = [t for t in fig.data if isinstance(t, go.Scatter) and t.name and "95" in str(t.name)]
    assert len(overlays) == 1
    assert list(overlays[0].y) == [-100.0, None]


def test_units_pct_uses_var_pct_instead_of_gbp() -> None:
    series = [_entry("2026-03-02", "2026-03-03", var_9500_gbp=100.0, var_9500_pct=10.0)]
    fig = build_figures(
        series,
        selected_confidence_bp=[9500],
        units="pct",
        pnl_basis="hypothetical",
        hide_degraded=False,
        show_es=False,
    )
    overlays = [t for t in fig.data if isinstance(t, go.Scatter)]
    assert list(overlays[0].y) == [-10.0]


def test_exceedance_bar_is_colored_distinctly() -> None:
    series = [
        _entry("2026-03-02", "2026-03-03", hypothetical_exception=True),
        _entry("2026-03-03", "2026-03-04", hypothetical_exception=False),
    ]
    fig = build_figures(
        series,
        selected_confidence_bp=[9500],
        units="gbp",
        pnl_basis="hypothetical",
        hide_degraded=False,
        show_es=False,
    )
    bar = _figure_bar_trace(fig)
    colors = list(bar.marker.color)
    assert colors[0] == EXCEPTION_COLOR
    assert colors[1] != EXCEPTION_COLOR


def test_multiple_selected_levels_any_exception_colors_the_bar() -> None:
    entry = _entry("2026-03-02", "2026-03-03", hypothetical_exception=False)
    entry["levels"].append(
        {
            "confidence_bp": 9900,
            "var_gbp": 150.0,
            "var_pct": 15.0,
            "es_gbp": 180.0,
            "es_pct": 18.0,
            "hypothetical_exception": True,
            "ladder_exception": False,
        }
    )
    fig = build_figures(
        [entry],
        selected_confidence_bp=[9500, 9900],
        units="gbp",
        pnl_basis="hypothetical",
        hide_degraded=False,
        show_es=False,
    )
    bar = _figure_bar_trace(fig)
    assert list(bar.marker.color)[0] == EXCEPTION_COLOR


def test_show_es_adds_a_dashed_overlay_per_selected_level() -> None:
    series = [_entry("2026-03-02", "2026-03-03", es_9500_gbp=120.0)]
    fig_without = build_figures(
        series,
        selected_confidence_bp=[9500],
        units="gbp",
        pnl_basis="hypothetical",
        hide_degraded=False,
        show_es=False,
    )
    fig_with = build_figures(
        series,
        selected_confidence_bp=[9500],
        units="gbp",
        pnl_basis="hypothetical",
        hide_degraded=False,
        show_es=True,
    )
    scatter_without = [t for t in fig_without.data if isinstance(t, go.Scatter)]
    scatter_with = [t for t in fig_with.data if isinstance(t, go.Scatter)]
    assert len(scatter_with) == len(scatter_without) + 1
    es_trace = next(t for t in scatter_with if "ES" in str(t.name))
    assert es_trace.line.dash == "dash"


def test_hide_degraded_omits_degraded_entries() -> None:
    series = [
        _entry("2026-03-02", "2026-03-03", quality="ok"),
        _entry("2026-03-03", "2026-03-04", quality="degraded"),
    ]
    fig_shown = build_figures(
        series,
        selected_confidence_bp=[9500],
        units="gbp",
        pnl_basis="hypothetical",
        hide_degraded=False,
        show_es=False,
    )
    fig_hidden = build_figures(
        series,
        selected_confidence_bp=[9500],
        units="gbp",
        pnl_basis="hypothetical",
        hide_degraded=True,
        show_es=False,
    )
    assert len(_figure_bar_trace(fig_shown).x) == 2
    assert len(_figure_bar_trace(fig_hidden).x) == 1

    overlay_shown = next(
        t for t in fig_shown.data if isinstance(t, go.Scatter) and "95" in str(t.name)
    )
    overlay_hidden = next(
        t for t in fig_hidden.data if isinstance(t, go.Scatter) and "95" in str(t.name)
    )
    assert len(overlay_shown.x) == 2
    assert len(overlay_hidden.x) == 1


def test_pct_units_omits_the_realised_pnl_bar_entirely() -> None:
    """028 FR-005: no percentage-equivalent of realised PnL exists on `VarSeriesEntry`
    (confirmed against src/models/portfolio_analysis.py), so in percentage mode the bar
    trace must be omitted entirely -- not added with `visible=False` -- while the VaR
    overlay line and the linked market-value subplot are unaffected.
    """
    series = [_entry("2026-03-02", "2026-03-03", total_value_gbp=1234.0)]
    fig = build_figures(
        series,
        selected_confidence_bp=[9500],
        units="pct",
        pnl_basis="hypothetical",
        hide_degraded=False,
        show_es=False,
    )
    bars = [t for t in fig.data if isinstance(t, go.Bar)]
    assert bars == []
    overlays = [t for t in fig.data if isinstance(t, go.Scatter) and "95" in str(t.name)]
    assert len(overlays) == 1
    value_traces = [t for t in fig.data if t.name == "Total Market Value"]
    assert len(value_traces) == 1
    assert list(value_traces[0].y) == [1234.0]


def test_gbp_units_still_render_the_bar_after_a_prior_pct_mode_call() -> None:
    """028 FR-006: build_figures is a pure function with no shared state, so switching
    units back to money restores the bar trace exactly as a gbp-only call would -- this
    test is a regression guard for that invariant, not a fix for a known bug.
    """
    series = [_entry("2026-03-02", "2026-03-03", hypothetical_pnl_gbp=-42.0)]
    build_figures(
        series,
        selected_confidence_bp=[9500],
        units="pct",
        pnl_basis="hypothetical",
        hide_degraded=False,
        show_es=False,
    )
    fig_gbp_only = build_figures(
        series,
        selected_confidence_bp=[9500],
        units="gbp",
        pnl_basis="hypothetical",
        hide_degraded=False,
        show_es=False,
    )
    fig_after_pct = build_figures(
        series,
        selected_confidence_bp=[9500],
        units="gbp",
        pnl_basis="hypothetical",
        hide_degraded=False,
        show_es=False,
    )
    bar_only = _figure_bar_trace(fig_gbp_only)
    bar_after_pct = _figure_bar_trace(fig_after_pct)
    assert list(bar_only.y) == list(bar_after_pct.y) == [-42.0]


def test_each_subplot_row_has_a_caption() -> None:
    """028 FR-007/FR-008: a caption above each chart section, via Plotly's own
    `subplot_titles` -- not a second `dcc.Graph`, which would need new wiring to keep
    the two rows' x-axis zoom/pan linked (research.md #4).
    """
    series = [_entry("2026-03-02", "2026-03-03")]
    fig = build_figures(
        series,
        selected_confidence_bp=[9500],
        units="gbp",
        pnl_basis="hypothetical",
        hide_degraded=False,
        show_es=False,
    )
    # make_subplots renders subplot_titles as annotations; with no other annotations
    # added by this module, there must be exactly two, one per row.
    titles = [a.text for a in fig.layout.annotations]
    assert len(titles) == 2
    assert "pnl" in titles[0].lower()
    assert "value at risk" in titles[0].lower()
    assert "market value" in titles[1].lower()


def test_subplot_titles_do_not_disturb_the_shared_x_axis_link() -> None:
    """028 research.md #4: adding captions must not break the linked zoom/pan between
    the main chart and the market-value chart beneath it. `shared_xaxes=True` links the
    two rows' x-axes via Plotly's `matches` layout property (not by giving them the same
    `xaxis` id -- each subplot row always gets its own).
    """
    series = [_entry("2026-03-02", "2026-03-03", total_value_gbp=1234.0)]
    fig = build_figures(
        series,
        selected_confidence_bp=[9500],
        units="gbp",
        pnl_basis="hypothetical",
        hide_degraded=False,
        show_es=False,
    )
    assert fig.layout.xaxis.matches == "x2"


def test_legend_is_positioned_below_the_chart() -> None:
    """028 FR-001: the legend must not render inside/beside the plot area, where it
    crowds into the backtest panel's column space. No specific y magnitude is asserted
    beyond "below the plot" -- Plotly's legend y is relative to the whole figure's paper
    space regardless of subplot row count, so this chart needs the same y as every other
    chart in this codebase, not a more-negative one (research.md #1).
    """
    series = [_entry("2026-03-02", "2026-03-03")]
    fig = build_figures(
        series,
        selected_confidence_bp=[9500],
        units="gbp",
        pnl_basis="hypothetical",
        hide_degraded=False,
        show_es=False,
    )
    legend = fig.layout.legend
    assert legend.orientation == "h"
    assert legend.xanchor == "center"
    assert legend.x == 0.5
    assert legend.y < 0


def test_linked_market_value_subplot_present() -> None:
    series = [_entry("2026-03-02", "2026-03-03", total_value_gbp=1234.0, proxied_mv_pct=5.0)]
    fig = build_figures(
        series,
        selected_confidence_bp=[9500],
        units="gbp",
        pnl_basis="hypothetical",
        hide_degraded=False,
        show_es=False,
    )
    value_traces = [t for t in fig.data if t.name == "Total Market Value"]
    assert len(value_traces) == 1
    assert list(value_traces[0].y) == [1234.0]
    # Shared x-axis subplot: the market-value trace is on a different y-axis than the bars.
    bar = _figure_bar_trace(fig)
    assert value_traces[0].yaxis != bar.yaxis
