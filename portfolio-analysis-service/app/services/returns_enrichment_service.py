"""Service that enriches a priced position ladder with daily return metrics."""

import pandas as pd
import structlog

logger = structlog.get_logger(__name__)

_MAX_ADJACENT_ROW_GAP_DAYS = 3
"""Widest calendar gap between two genuinely adjacent rows for the same sub-account.

LadderExpander expands to consecutive business days (Mon-Fri, no holiday calendar) while a
position is active, so the only legitimate gap between two adjacent rows is a Friday-to-Monday
weekend (3 calendar days). A larger gap means the previous row is not this row's true T-1 (e.g.
a sub-account fully divested and later re-purchased) and must not be used as one.
"""


class ReturnsEnrichmentService:
    """Computes position_return and weighted_position_return for a priced position ladder.

    Both metrics are pure functions of columns already present after price enrichment
    (`price`, `total_income`, `quantity`, `portfolio_weight`) — no external calls are made.
    `position_return` compares a row to its sub-account's immediately preceding row;
    `weighted_position_return` scales that return by the *previous* row's `portfolio_weight`
    (the start-of-day weight), not the current row's own weight. A sub-account's first
    recorded row, or a row following a gap of more than
    `_MAX_ADJACENT_ROW_GAP_DAYS` calendar days since its predecessor, has both metrics
    recorded as 0.0.
    """

    def enrich(self, priced_df: pd.DataFrame) -> pd.DataFrame:
        """Return the ladder with position_return and weighted_position_return appended.

        Args:
            priced_df: Priced ladder rows with columns
                [date, sub_account, book_cost, quantity, total_income, price, market_value,
                portfolio_weight] (the output of PricingEnrichmentService.enrich()).

        Returns:
            DataFrame with the same rows plus position_return and weighted_position_return
            columns, sorted by (date, sub_account).
        """
        df = priced_df.copy()
        df["date"] = pd.to_datetime(df["date"]).dt.date

        parts: list[pd.DataFrame] = []
        for _sub_account, group in df.groupby("sub_account", sort=False):
            group = group.sort_values("date").copy()

            prev_price = group["price"].shift(1)
            prev_total_income = group["total_income"].shift(1)
            prev_portfolio_weight = group["portfolio_weight"].shift(1)

            date_ts = pd.to_datetime(group["date"])
            gap_days = (date_ts - date_ts.shift(1)).dt.days
            has_prior_row = gap_days.notna() & (gap_days <= _MAX_ADJACENT_ROW_GAP_DAYS)

            income_per_share = (
                (group["total_income"] - prev_total_income) / group["quantity"]
            ).where(group["quantity"] != 0, other=0.0)

            position_return = ((group["price"] - prev_price + income_per_share) / prev_price).where(
                has_prior_row & (prev_price != 0), other=0.0
            )

            weighted_position_return = position_return * prev_portfolio_weight.where(
                has_prior_row, other=0.0
            ).fillna(0.0)

            group["position_return"] = position_return
            group["weighted_position_return"] = weighted_position_return
            parts.append(group)

        result = pd.concat(parts, ignore_index=True)
        result = result.sort_values(["date", "sub_account"]).reset_index(drop=True)

        logger.info(
            "returns_enrich_complete",
            row_count=len(result),
            sub_account_count=result["sub_account"].nunique(),
        )
        return result
