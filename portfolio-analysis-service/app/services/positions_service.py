"""Service for position enumeration and effective-position-set resolution.

Operates purely on an already-loaded position-ladder DataFrame; it has no repository or
I/O dependency of its own (research.md §4), which keeps it independently unit-testable
with plain synthetic DataFrames.
"""

import pandas as pd

from app.models.position_timeseries import PositionSummary


class PositionsService:
    """Enumerates positions and resolves the effective position set for a request."""

    def list_positions(self, ladder_df: pd.DataFrame) -> list[PositionSummary]:
        """Return every distinct position with its first/last recorded date.

        Args:
            ladder_df: Full position ladder rows for one account (must include
                `date` and `sub_account` columns).

        Returns:
            One PositionSummary per distinct sub_account, sorted by position name.
        """
        grouped = ladder_df.groupby("sub_account")["date"].agg(["min", "max"])
        return [
            PositionSummary(position=str(name), from_date=row["min"], to_date=row["max"])
            for name, row in grouped.sort_index().iterrows()
        ]

    def resolve_effective_positions(
        self, ladder_df: pd.DataFrame, requested: list[str]
    ) -> list[str]:
        """Resolve the effective position set from the requested names.

        Args:
            ladder_df: Full position ladder rows for one account (must include a
                `sub_account` column).
            requested: Caller-supplied position names, possibly empty, possibly
                containing duplicates or names not recorded for this account.

        Returns:
            Sorted distinct sub_account values if `requested` is empty; otherwise the
            sorted intersection of `requested` and the distinct sub_account values —
            an empty list if nothing matches. Never raises.
        """
        distinct = set(ladder_df["sub_account"].unique())
        if not requested:
            return sorted(distinct)
        return sorted(distinct & set(requested))
