"""Service that expands a sparse capital ledger into a daily business-day series."""

from typing import ClassVar

import pandas as pd

from app.services.business_day_expansion import expand_business_days


class CapitalLedgerExpander:
    """Expands a sparse capital ledger into a full daily business-day series.

    Unlike the position ladder, this is a single flat series with no sub-account
    grouping and no closure rule. The expansion range is [min(date), max(date)] of the
    submitted file itself — it is NOT extended forward to today, since there is no
    pricing step requiring that freshness boundary.
    """

    _VALUE_COLUMNS: ClassVar[list[str]] = ["capital", "income", "book_value"]

    def expand(self, df: pd.DataFrame) -> pd.DataFrame:
        """Expand a sparse capital ledger DataFrame into a dense daily business-day series.

        Args:
            df: Input ledger with columns [date, capital, income, book_value]. The date
                column must be parseable by pd.to_datetime.

        Returns:
            Dense DataFrame with columns [date, capital, income, book_value] sorted by
            date. Contains only business days (Mon-Fri) between the earliest and latest
            date recorded in df.
        """
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"]).dt.date

        min_date = df["date"].min()
        max_date = df["date"].max()

        result = expand_business_days(df, self._VALUE_COLUMNS, min_date, max_date)
        result = result.sort_values("date").reset_index(drop=True)
        return result
