"""Builds Mon-Fri business-day return grids from observed-only price history.

The grid is the shared scenario-day axis every as-of date's look-back window slices
into: a pure function from observed prices to returns, with no market-data calls of its
own. Callers are responsible for requesting enough history (a buffer before the grid's
first day) that the grid's earliest rows can find a prior observed price to compute a
return from.
"""

from dataclasses import dataclass, replace
from datetime import date

import numpy as np
import pandas as pd
import structlog

from app.config import ExcludedReturn
from app.models.market_data import ObservedPriceHistory
from app.models.var import RunWarning

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ReturnPanel:
    """A business-day grid of per-identifier observed simple returns.

    Attributes:
        grid: Business days (Mon-Fri) from grid_start to grid_end inclusive, ascending.
        identifiers: Column identifiers, in a stable order matching `returns`/`observed`.
        returns: T x m float array. NaN before an identifier has two observed prices to
            form a ratio from (its first observed day, or any earlier day); 0.0 on a day
            with no observation but within the instrument's known observation window
            (first_observed_date..last_observed_date); the real simple return
            (price / previous observed price - 1) wherever two observed prices bracket
            the day.
        observed: T x m bool array. True only where `returns` holds a genuine observed
            return, i.e. this grid day and its immediately preceding observed price were
            both real market observations. False for zero-filled gap days and for the
            NaN cells described above -- so this mask reflects "this is usable scenario
            information", not merely "a price quote exists on this day".
        first_observed: Identifier to the instrument's known first observed date (from
            market-data-service), or None if nothing is known about it.
    """

    grid: tuple[date, ...]
    identifiers: tuple[str, ...]
    returns: np.ndarray
    observed: np.ndarray
    first_observed: dict[str, date | None]


def build_return_panel(
    histories: dict[str, ObservedPriceHistory], grid_start: date, grid_end: date
) -> ReturnPanel:
    """Build a Mon-Fri return grid for every identifier from its observed price history.

    Args:
        histories: Identifier to its ObservedPriceHistory.
        grid_start: First business day of the grid (inclusive).
        grid_end: Last business day of the grid (inclusive).

    Returns:
        A ReturnPanel covering every Mon-Fri business day in [grid_start, grid_end].
    """
    grid = tuple(d.date() for d in pd.bdate_range(start=grid_start, end=grid_end))
    identifiers = tuple(histories.keys())
    t, m = len(grid), len(identifiers)
    returns = np.full((t, m), np.nan, dtype=float)
    observed = np.zeros((t, m), dtype=bool)
    first_observed: dict[str, date | None] = {}

    for col, identifier in enumerate(identifiers):
        history = histories[identifier]
        first_observed[identifier] = history.first_observed_date
        price_by_date = {p.date: p.close for p in history.points}
        first_obs = history.first_observed_date
        last_obs = history.last_observed_date

        prev_observed_date = max((d for d in price_by_date if d < grid[0]), default=None)

        for row, d in enumerate(grid):
            if d in price_by_date:
                if prev_observed_date is not None:
                    returns[row, col] = price_by_date[d] / price_by_date[prev_observed_date] - 1.0
                    observed[row, col] = True
                prev_observed_date = d
            elif first_obs is not None and last_obs is not None and first_obs <= d <= last_obs:
                returns[row, col] = 0.0

    logger.info("var_return_panel_built", grid_days=t, identifier_count=m)
    return ReturnPanel(
        grid=grid,
        identifiers=identifiers,
        returns=returns,
        observed=observed,
        first_observed=first_observed,
    )


@dataclass(frozen=True)
class OutlierObservation:
    """One observed return whose magnitude exceeds the configured outlier threshold."""

    identifier: str
    date: date
    value: float


def find_outliers(panel: ReturnPanel, threshold: float) -> list[OutlierObservation]:
    """List every observed return whose absolute value exceeds a threshold (FR-028).

    Only genuinely observed cells (`panel.observed`) are considered -- zero-filled gap
    days and NaN cells are never reported, regardless of magnitude (they have none).

    Args:
        panel: The return panel to scan.
        threshold: Absolute return magnitude above which a return is an outlier
            (strictly greater than; a return exactly at the threshold is not flagged).

    Returns:
        OutlierObservation entries, in grid-then-identifier order.
    """
    results: list[OutlierObservation] = []
    for col, identifier in enumerate(panel.identifiers):
        for row, d in enumerate(panel.grid):
            if panel.observed[row, col] and abs(panel.returns[row, col]) > threshold:
                results.append(
                    OutlierObservation(
                        identifier=identifier, date=d, value=float(panel.returns[row, col])
                    )
                )
    return results


def apply_exclusions(
    panel: ReturnPanel, exclusions: list[ExcludedReturn]
) -> tuple[ReturnPanel, list[RunWarning]]:
    """Blank configured bad (identifier, date) prices, treating them as missing (FR-029).

    Args:
        panel: The return panel to apply exclusions to (not mutated).
        exclusions: Configured (identifier, date) prices to exclude.

    Returns:
        (new_panel, warnings): a new ReturnPanel with each matched cell set to NaN and
        unobserved (so the engine's proxy/rescale treatment picks it up as missing), and
        one `excluded_price` RunWarning per exclusion that matched a real panel cell.
        An exclusion naming an identifier or date outside the panel is a no-op.
    """
    returns = panel.returns.copy()
    observed = panel.observed.copy()
    warnings: list[RunWarning] = []
    identifier_index = {identifier: i for i, identifier in enumerate(panel.identifiers)}
    grid_index = {d: i for i, d in enumerate(panel.grid)}

    for excluded in exclusions:
        if excluded.identifier not in identifier_index or excluded.date not in grid_index:
            continue
        col = identifier_index[excluded.identifier]
        row = grid_index[excluded.date]
        previous = returns[row, col]
        returns[row, col] = np.nan
        observed[row, col] = False
        warnings.append(
            RunWarning(
                kind="excluded_price",
                identifier=excluded.identifier,
                date=excluded.date,
                value=None if np.isnan(previous) else float(previous),
                message=(
                    f"Excluded configured bad price for '{excluded.identifier}' on {excluded.date}."
                ),
            )
        )

    new_panel = replace(panel, returns=returns, observed=observed)
    return new_panel, warnings
