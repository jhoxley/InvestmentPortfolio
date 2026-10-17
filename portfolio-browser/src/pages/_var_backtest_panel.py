"""Pure builder for the Value at Risk section's backtest summary panel
(026-var-risk-view, US2; restyled to a DataTable grid by 027 US5).

Kept out of risk.py so it stays importable from a plain unit test. Every statistic
rendered here is read verbatim from the already-fetched backtest result matching the
current (pnl_basis, min_quality) pair -- selecting which of the four pre-fetched results
to show is the only logic here (research.md #1/#4); nothing is recomputed.
"""

from __future__ import annotations

from typing import Any

from dash import dash_table, html

_ZONE_LABEL = {"green": "Pass", "yellow": "Caution", "red": "Fail", None: "N/A"}
_NOT_ENOUGH = "not enough observations"

# 027 FR-010/SC-005: the exact same style dictionaries `risk.py` uses for its own
# `risk-statistics-table`, imported from there rather than duplicated, so the two
# tables can never visually drift apart. Defined here (not in risk.py) so this module
# has no import-time dependency on risk.py, which already imports this module.
STYLE_CELL = {"textAlign": "left", "padding": "8px"}
STYLE_HEADER = {"fontWeight": "bold"}

_PANEL_COLUMNS = [
    {"name": "statistic", "id": "statistic"},
    {"name": "value", "id": "value"},
]


def _min_quality(hide_degraded: bool) -> str:
    return "ok" if hide_degraded else "degraded"


def _fmt(value: float | int | str | None, undefined_text: str = _NOT_ENOUGH) -> str:
    if value is None:
        return undefined_text
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _level_rows(level: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {
            "statistic": "Exceptions",
            "value": (
                f"{level['exception_count']} observed / "
                f"{_fmt(level['expected_exceptions'])} expected "
                f"(of {level['observation_count']})"
            ),
        },
        {"statistic": "Kupiec p-value", "value": _fmt(level["kupiec_p_value"])},
        {
            "statistic": "Conditional coverage p-value",
            "value": _fmt(level["conditional_coverage_p_value"]),
        },
        {"statistic": "Zone", "value": str(_ZONE_LABEL.get(level["zone"], level["zone"]))},
        {"statistic": "Mean VaR", "value": _fmt(level["mean_var_gbp"])},
        {"statistic": "VaR stability", "value": _fmt(level["var_stability"])},
    ]


def _level_block(level: dict[str, Any]) -> html.Div:
    confidence_label = f"{level['confidence_bp'] / 100:g}%"
    return html.Div(
        [
            html.H6(confidence_label),
            dash_table.DataTable(  # type: ignore[attr-defined]
                columns=_PANEL_COLUMNS,
                data=_level_rows(level),
                style_cell=STYLE_CELL,
                style_header=STYLE_HEADER,
            ),
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
