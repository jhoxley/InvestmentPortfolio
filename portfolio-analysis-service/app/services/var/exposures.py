"""Builds per-date position exposures from a priced position ladder.

An Exposure is the input to the VaR engine for one as-of date: the GBP market value of
every risky (non-Cash) position, plus the Cash balance, as of that date's close.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

import pandas as pd
import structlog

from app.models.market_data import IdentifierMappingEntry

logger = structlog.get_logger(__name__)

_CASH = "Cash"


@dataclass(frozen=True)
class PositionExposure:
    """One held position's GBP market value on one date.

    Attributes:
        sub_account: Ladder sub-account name.
        identifier: Market-data identifier (ticker, or ISIN if no ticker is configured) --
            the same resolution rule PricingEnrichmentService uses.
        market_value: GBP market value (always > 0; zero/negative positions are excluded
            by build_exposures()).
    """

    sub_account: str
    identifier: str
    market_value: float


@dataclass(frozen=True)
class Exposure:
    """An account's full exposure on one as-of date.

    Attributes:
        as_of: The ladder business date these values are observed at close of.
        positions: Every held non-Cash position with a positive market value.
        cash_value: The Cash sub-account's market value (0.0 if not present that date).
        risky_value: Sum of `positions`' market values.
        total_value: risky_value + cash_value.
        fingerprint: Set by fingerprint.row_fingerprint() once the VaR configuration is
            known; empty string until then.
    """

    as_of: date
    positions: tuple[PositionExposure, ...]
    cash_value: float
    risky_value: float
    total_value: float
    fingerprint: str = field(default="")


def _resolve_identifier(entry: IdentifierMappingEntry | None) -> str | None:
    """Return the identifier to price a sub-account by: ticker, else isin, else None.

    Args:
        entry: The sub-account's identifier mapping entry, or None if unmapped.

    Returns:
        The identifier to use, or None if the sub-account cannot be resolved to one.
    """
    if entry is None:
        return None
    return entry.ticker or entry.isin or None


def build_exposures(
    ladder_df: pd.DataFrame,
    lookup: Callable[[str], IdentifierMappingEntry | None],
) -> dict[date, Exposure]:
    """Build one Exposure per business date present in a priced position ladder.

    Args:
        ladder_df: Full stored ladder columns, at minimum [date, sub_account, quantity,
            market_value] (the output of LadderRepository.read_full_df()).
        lookup: Resolves a sub-account name to its identifier mapping entry, or None.

    Returns:
        Mapping of as-of date to Exposure. A sub-account whose identifier cannot be
        resolved (no mapping entry, or neither ticker nor isin configured) is excluded
        from `positions`, the same as a zero-value or zero-quantity position -- it
        contributes nothing to risky_value and is picked up entirely by the rescale
        treatment in the engine.

    Raises:
        KeyError: If ladder_df is missing one of the required columns.
    """
    df = ladder_df[["date", "sub_account", "quantity", "market_value"]].copy()
    df["date"] = pd.to_datetime(df["date"]).dt.date

    unresolved: set[str] = set()
    result: dict[date, Exposure] = {}

    for as_of, group in df.groupby("date", sort=False):
        cash_value = 0.0
        positions: list[PositionExposure] = []

        for row in group.itertuples(index=False):
            if row.sub_account == _CASH:
                cash_value = float(row.market_value)
                continue
            if row.quantity <= 0 or row.market_value <= 0:
                continue
            identifier = _resolve_identifier(lookup(row.sub_account))
            if identifier is None:
                unresolved.add(row.sub_account)
                continue
            positions.append(
                PositionExposure(
                    sub_account=row.sub_account,
                    identifier=identifier,
                    market_value=float(row.market_value),
                )
            )

        risky_value = sum(p.market_value for p in positions)
        result[as_of] = Exposure(
            as_of=as_of,
            positions=tuple(positions),
            cash_value=cash_value,
            risky_value=risky_value,
            total_value=risky_value + cash_value,
        )

    if unresolved:
        logger.warning("var_exposure_unresolved_identifiers", sub_accounts=sorted(unresolved))

    logger.info("var_exposures_built", date_count=len(result))
    return result
