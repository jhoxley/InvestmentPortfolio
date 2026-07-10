"""Service that expands a sparse sub-account ledger into a daily position ladder."""

from datetime import date
from typing import ClassVar

import pandas as pd

from app.services.business_day_expansion import expand_business_days


class LadderExpander:
    """Expands a sparse sub-account ledger into a full daily business-day ladder.

    For each sub-account:
    - Business days (Mon-Fri) are generated from the first activity date through
      today minus 2 business days using pandas.bdate_range.
    - Values (book_cost, quantity, total_income) are forward-filled from the most
      recent activity record on or before each date.
    - Equity sub-accounts (any sub-account that is not 'Cash') are excluded on
      all dates after the date on which their cumulative quantity first reaches zero.
    - The Cash sub-account always appears, regardless of balance.
    """

    _VALUE_COLUMNS: ClassVar[list[str]] = ["book_cost", "quantity", "total_income"]

    def expand(self, df: pd.DataFrame, today: date) -> pd.DataFrame:
        """Expand a sparse ledger DataFrame into a dense daily position ladder.

        Args:
            df: Input ledger with columns [date, sub_account, book_cost, quantity, total_income].
                The date column must be parseable by pd.to_datetime.
            today: Reference date. The expansion ends at today minus 2 business days.

        Returns:
            Dense DataFrame with columns [date, sub_account, book_cost, quantity, total_income]
            sorted by (date, sub_account). Contains only business days (Mon-Fri).
        """
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"]).dt.date

        min_date = df["date"].min()
        end_ts = pd.bdate_range(end=today, periods=3)[-3]
        end_date = end_ts.date()

        expanded_parts: list[pd.DataFrame] = []

        for sub_account, group in df.groupby("sub_account", sort=False):
            reindexed = expand_business_days(group, self._VALUE_COLUMNS, min_date, end_date)
            reindexed["sub_account"] = sub_account

            if sub_account != "Cash":
                reindexed = self._apply_closure_rule(reindexed)

            expanded_parts.append(reindexed)

        if not expanded_parts:
            return pd.DataFrame(columns=["date", "sub_account", *self._VALUE_COLUMNS])

        result = pd.concat(expanded_parts, ignore_index=True)
        result = result.dropna(subset=self._VALUE_COLUMNS)
        result = result[["date", "sub_account", *self._VALUE_COLUMNS]]
        result = result.sort_values(["date", "sub_account"]).reset_index(drop=True)
        return result

    def _apply_closure_rule(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove rows from an equity sub-account after its quantity first reaches zero.

        Args:
            df: Expanded rows for a single non-Cash sub-account, with columns
                [date, sub_account, book_cost, quantity, total_income].

        Returns:
            Filtered DataFrame with no rows after the closure date.
        """
        zero_mask = df["quantity"] == 0.0
        if not zero_mask.any():
            return df
        first_zero_idx = df.index[zero_mask][0]
        closure_date = df.loc[first_zero_idx, "date"]
        return df[df["date"] <= closure_date]
