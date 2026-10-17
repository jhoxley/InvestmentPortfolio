"""Shared Periodicity control for the Overview and Positions pages (021).

Both pages build this control from the one builder here, so the UI is
identical — but each page gets its **own component ids**, derived from a
`page_prefix`. That is a deliberate departure from
`src/components/date_range_controls.py`, which shares one id across routes.

The reason: Dash derives an `allow_duplicate` Output's callback id by hashing
the callback's *Inputs* alone (`dash/_utils.py::create_callback_id`), so two
pages declaring the same Output from the same Inputs collapse into a single
registration and the page imported last silently wins. That is exactly the
defect found while closing feature 020, where 7 of 20 callback registrations
were being discarded. Per-page ids make it impossible here rather than merely
guarded against; `tests/unit/test_callback_registration.py` is the backstop.

This module is pure presentation: it performs no I/O and holds no state. The
effective interval lives in each page's own `dcc.Store`.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import dash_bootstrap_components as dbc
from dash import html

from config.content import (
    PERIODICITY_DAY,
    PERIODICITY_MONTH,
    PERIODICITY_QUARTER,
    PERIODICITY_WEEK,
    PERIODICITY_YEAR,
    PeriodicityConfig,
    PeriodicityThresholds,
)
from src.components.date_range_controls import _years_before

# Re-exported so pages and tests import the option keys from one place. The
# canonical definitions live in config/content.py, which also validates that
# every derivable key is present in the configured options.
__all__ = [
    "PERIODICITY_DAY",
    "PERIODICITY_MONTH",
    "PERIODICITY_QUARTER",
    "PERIODICITY_WEEK",
    "PERIODICITY_YEAR",
    "build_periodicity_control",
    "derive_periodicity",
    "periodicity_button_states",
    "periodicity_component_id",
]

_ID_SUFFIX = "parameters-periodicity"


def periodicity_component_id(page_prefix: str, key: str) -> str:
    """Return the component id for one page's interval button.

    Args:
        page_prefix: The owning page, e.g. "overview" or "positions".
        key: The periodicity option key, e.g. "quarter".

    Returns:
        The page-scoped component id, e.g. "overview-parameters-periodicity-quarter".
    """
    return f"{page_prefix}-{_ID_SUFFIX}-{key}"


def periodicity_group_id(page_prefix: str) -> str:
    """Return the component id for one page's button group.

    Args:
        page_prefix: The owning page, e.g. "overview" or "positions".

    Returns:
        The page-scoped button-group id.
    """
    return f"{page_prefix}-{_ID_SUFFIX}-group"


def periodicity_label_id(page_prefix: str) -> str:
    """Return the component id for one page's control label.

    Args:
        page_prefix: The owning page, e.g. "overview" or "positions".

    Returns:
        The page-scoped label id.
    """
    return f"{page_prefix}-{_ID_SUFFIX}-label"


def periodicity_store_id(page_prefix: str) -> str:
    """Return the component id for one page's effective-interval store.

    Args:
        page_prefix: The owning page, e.g. "overview" or "positions".

    Returns:
        The page-scoped store id.
    """
    return f"{page_prefix}-periodicity-store"


def build_periodicity_control(page_prefix: str, config: PeriodicityConfig) -> list[Any]:
    """Build the label + interval buttons for one page's parameters bar (FR-001).

    Buttons rather than a dropdown because `n_clicks` increments only on a real
    click, which is what lets a page tell a user's explicit choice from a
    system-derived one (FR-012) without depending on callback ordering.

    Args:
        page_prefix: The owning page, e.g. "overview" or "positions".
        config: The validated periodicity configuration.

    Returns:
        A list of `dbc.Col` elements ready to splice into a `dbc.Row`.
    """
    buttons = [
        dbc.Button(
            option.label,
            id=periodicity_component_id(page_prefix, option.key),
            size="sm",
            color="secondary",
            outline=True,
            active=False,
        )
        for option in config.options
    ]
    return [
        dbc.Col(
            html.Label(
                config.label,
                id=periodicity_label_id(page_prefix),
                htmlFor=periodicity_group_id(page_prefix),
            ),
            width="auto",
        ),
        dbc.Col(dbc.ButtonGroup(buttons, id=periodicity_group_id(page_prefix)), width="auto"),
    ]


def periodicity_button_states(
    effective: str | None, config: PeriodicityConfig
) -> list[dict[str, bool]]:
    """Return each button's active/outline state for the effective interval (FR-011).

    Args:
        effective: The interval currently in effect, given either as an option
            key ("year") or as its service-side value ("annual"); None
            highlights nothing.
        config: The validated periodicity configuration.

    Returns:
        One `{"active": bool, "outline": bool}` per configured option, in
        config order. Exactly one is active when `effective` matches an option;
        none is active otherwise.
    """
    matched = config.option_for(effective) if effective else None
    return [
        {
            "active": matched is not None and option.key == matched.key,
            "outline": matched is None or option.key != matched.key,
        }
        for option in config.options
    ]


def derive_periodicity(from_date: date, to_date: date, thresholds: PeriodicityThresholds) -> str:
    """Derive an interval from how long the requested date range is (FR-008).

    Comparisons are inclusive, so a span sitting exactly on a threshold keeps
    the *finer* interval (spec Assumptions). Year arithmetic is delegated to
    `date_range_controls._years_before`, the same helper the 1Y/3Y/5Y shortcut
    buttons use, so a shortcut click lands exactly on the boundary this rule
    expects — leap-day fallback included.

    `week` is never returned: no threshold resolves to it, so it is reachable
    only by explicit selection (FR-009).

    Args:
        from_date: Start of the effective range.
        to_date: End of the effective range.
        thresholds: The configured year bounds.

    Returns:
        A periodicity option key — one of day/month/quarter/year.
    """
    if from_date >= to_date:
        # Degenerate or transiently inverted (mid-edit) range: the finest
        # interval is the only sensible answer, and never an exception.
        return PERIODICITY_DAY
    if from_date >= _years_before(to_date, thresholds.day_max_years):
        return PERIODICITY_DAY
    if from_date >= _years_before(to_date, thresholds.month_max_years):
        return PERIODICITY_MONTH
    if from_date >= _years_before(to_date, thresholds.quarter_max_years):
        return PERIODICITY_QUARTER
    return PERIODICITY_YEAR
