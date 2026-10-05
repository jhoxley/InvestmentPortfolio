"""Pure builder for the Value at Risk tab's backtest summary panel (026-var-risk-view, US2).

Kept out of risk.py so it stays importable from a plain unit test. Every statistic
rendered here is read verbatim from the already-fetched backtest result matching the
current (pnl_basis, min_quality) pair -- selecting which of the four pre-fetched results
to show is the only logic here (research.md #1/#4); nothing is recomputed.
"""

from __future__ import annotations

from typing import Any

from dash import html

_ZONE_LABEL = {"green": "Pass", "yellow": "Caution", "red": "Fail", None: "N/A"}
_NOT_ENOUGH = "not enough observations"


def _min_quality(hide_degraded: bool) -> str:
    return "ok" if hide_degraded else "degraded"


def _fmt(value: float | int | str | None, undefined_text: str = _NOT_ENOUGH) -> str:
    if value is None:
        return undefined_text
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _level_block(level: dict[str, Any]) -> html.Div:
    confidence_label = f"{level['confidence_bp'] / 100:g}%"
    return html.Div(
        [
            html.H6(confidence_label),
            html.P(
                f"Exceptions: {level['exception_count']} observed / "
                f"{_fmt(level['expected_exceptions'])} expected "
                f"(of {level['observation_count']})"
            ),
            html.P(f"Kupiec p-value: {_fmt(level['kupiec_p_value'])}"),
            html.P(f"Conditional coverage p-value: {_fmt(level['conditional_coverage_p_value'])}"),
            html.P(f"Zone: {_ZONE_LABEL.get(level['zone'], level['zone'])}"),
            html.P(f"Mean VaR: {_fmt(level['mean_var_gbp'])}"),
            html.P(f"VaR stability: {_fmt(level['var_stability'])}"),
        ],
        className="mb-3",
    )


def build_panel(
    backtest_by_basis_quality: dict[str, dict[str, dict[str, Any]]],
    selected_confidence_bp: list[int],
    pnl_basis: str,
    hide_degraded: bool,
) -> html.Div:
    """Build the backtest panel from the already-fetched (pnl_basis, min_quality) result.

    Args:
        backtest_by_basis_quality: `{pnl_basis: {min_quality: VarBacktestResponse-dict}}`,
            all four combinations already fetched (research.md #1).
        selected_confidence_bp: Confidence levels (basis points) to show.
        pnl_basis: "hypothetical" or "ladder" -- which already-fetched basis to select.
        hide_degraded: When True, select the "ok" min_quality result instead of "degraded".

    Returns:
        An html.Div with one block per selected confidence level.
    """
    min_quality = _min_quality(hide_degraded)
    result = backtest_by_basis_quality[pnl_basis][min_quality]
    levels_by_bp = {lvl["confidence_bp"]: lvl for lvl in result["levels"]}

    blocks = [_level_block(levels_by_bp[bp]) for bp in selected_confidence_bp if bp in levels_by_bp]
    return html.Div(blocks, id="risk-var-backtest-panel-content")
