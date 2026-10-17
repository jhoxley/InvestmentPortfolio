"""Pure builder for the Value at Risk section's backtest summary panel
(026-var-risk-view, US2; restyled to a DataTable grid by 027 US5; collapsed into one
combined multi-column table by 028 US2).

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

def _confidence_label(confidence_bp: int) -> str:
    return f"{confidence_bp / 100:g}%"


def _level_column_id(confidence_bp: int) -> str:
    # "level_", not "pct_" -- avoids confusion with this feature area's unrelated
    # `units == "pct"` chart-display concept (028 research.md #2).
    return f"level_{confidence_bp}"


def _combined_columns(selected_confidence_bp: list[int]) -> list[dict[str, str]]:
    """One "statistic" column plus one column per selected confidence level (028 FR-003)."""
    return [
        {"name": "statistic", "id": "statistic"},
        *(
            {"name": _confidence_label(bp), "id": _level_column_id(bp)}
            for bp in selected_confidence_bp
        ),
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


def _combined_rows(
    levels_by_bp: dict[int, dict[str, Any]], present_confidence_bp: list[int]
) -> list[dict[str, str]]:
    """Pivot each present level's own `_level_rows()` into one shared-statistic row per
    statistic, with one value key per level's column id (028 FR-003).
    """
    if not present_confidence_bp:
        return []
    per_level_rows = {bp: _level_rows(levels_by_bp[bp]) for bp in present_confidence_bp}
    statistic_labels = [row["statistic"] for row in per_level_rows[present_confidence_bp[0]]]
    return [
        {
            "statistic": statistic,
            **{
                _level_column_id(bp): per_level_rows[bp][i]["value"]
                for bp in present_confidence_bp
            },
        }
        for i, statistic in enumerate(statistic_labels)
    ]


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
        An html.Div containing a single `dash_table.DataTable`: one row per statistic,
        one column per selected confidence level (028 FR-003) -- replacing the former
        one-table-per-level layout.
    """
    min_quality = _min_quality(hide_degraded)
    result = backtest_by_basis_quality[pnl_basis][min_quality]
    levels_by_bp = {lvl["confidence_bp"]: lvl for lvl in result["levels"]}
    present_confidence_bp = [bp for bp in selected_confidence_bp if bp in levels_by_bp]

    table = dash_table.DataTable(  # type: ignore[attr-defined]
        columns=_combined_columns(present_confidence_bp),
        data=_combined_rows(levels_by_bp, present_confidence_bp),
        style_cell=STYLE_CELL,
        style_header=STYLE_HEADER,
    )
    return html.Div(table, id="risk-var-backtest-panel-content")
