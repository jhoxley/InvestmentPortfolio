"""Service that enriches a position ladder with price, market value, and portfolio weight."""

from datetime import date

import pandas as pd
import structlog

from app.clients.market_data_client import MarketDataClient
from app.exceptions import IdentifierMappingError, MarketDataServiceError, PriceCoverageError
from app.repositories.identifier_mapping_repository import IdentifierMappingRepository

logger = structlog.get_logger(__name__)

_CASH = "Cash"
_CASH_PRICE = 1.0


class PricingEnrichmentService:
    """Resolves identifiers, batches market-data calls, and computes priced columns.

    For the "Cash" sub-account, price is fixed at 1.0 GBP with no mapping lookup or
    market-data-service call. For every other distinct sub-account, exactly one
    price-history request is issued covering that sub-account's full active date range.

    Identifier-mapping and price-coverage problems are collected across *all*
    sub-accounts before anything is raised, so a single error names every affected
    sub-account (and date, where applicable) together — never just the first problem
    encountered (FR-008, SC-004).
    """

    def __init__(
        self,
        mapping_repo: IdentifierMappingRepository,
        market_data_client: MarketDataClient,
    ) -> None:
        """Initialise with the identifier mapping repository and market-data client.

        Args:
            mapping_repo: Repository resolving sub-account names to identifiers.
            market_data_client: Client used to fetch GBP price histories.
        """
        self._mapping_repo = mapping_repo
        self._market_data_client = market_data_client

    def enrich(self, ladder_df: pd.DataFrame) -> pd.DataFrame:
        """Return the ladder with price, market_value, and portfolio_weight appended.

        Args:
            ladder_df: Base ladder rows with columns
                [date, sub_account, book_cost, quantity, total_income].

        Returns:
            DataFrame with the same rows plus price, market_value, portfolio_weight columns.

        Raises:
            IdentifierMappingError: If one or more non-Cash sub-accounts have no usable
                mapping entry, and there are no price-coverage problems.
            PriceCoverageError: If one or more (sub_account, date) pairs cannot be priced
                in GBP, or a mix of mapping and coverage problems occurs together.
            MarketDataServiceError: If a market-data-service request fails outright
                (network error, non-2xx, timeout).
        """
        df = ladder_df.copy()
        df["date"] = pd.to_datetime(df["date"]).dt.date

        priced_parts: list[pd.DataFrame] = []
        missing_mapping: list[str] = []
        coverage_problems: dict[str, list[date]] = {}

        for sub_account, group in df.groupby("sub_account", sort=False):
            group = group.copy()
            sub_account_name = str(sub_account)

            if sub_account_name == _CASH:
                group["price"] = _CASH_PRICE
                logger.info("cash_priced", sub_account=sub_account_name, row_count=len(group))
                priced_parts.append(group)
                continue

            entry = self._mapping_repo.lookup(sub_account_name)
            if entry is None or not (entry.ticker or entry.isin):
                logger.warning("identifier_mapping_problem", sub_account=sub_account_name)
                missing_mapping.append(sub_account_name)
                continue
            identifier = entry.ticker or entry.isin
            assert identifier is not None  # guaranteed by the check above

            min_date = group["date"].min()
            max_date = group["date"].max()
            log = logger.bind(
                sub_account=sub_account_name,
                identifier=identifier,
                from_date=str(min_date),
                to_date=str(max_date),
            )
            try:
                points = self._market_data_client.get_price_history(
                    identifier, min_date, max_date, "GBP"
                )
            except MarketDataServiceError as exc:
                log.error("sub_account_pricing_failed", detail=exc.detail)
                raise MarketDataServiceError(
                    sub_account=sub_account_name, detail=exc.detail
                ) from exc

            price_by_date = {point.date: point.close for point in points}
            missing_dates = sorted({d for d in group["date"] if d not in price_by_date})
            if missing_dates:
                log.warning(
                    "price_coverage_problem",
                    missing_dates=[str(d) for d in missing_dates],
                )
                coverage_problems[sub_account_name] = missing_dates
                continue

            group["price"] = group["date"].map(price_by_date)
            log.info("sub_account_priced", row_count=len(group), point_count=len(points))
            priced_parts.append(group)

        if missing_mapping or coverage_problems:
            if missing_mapping and not coverage_problems:
                raise IdentifierMappingError(sub_accounts=missing_mapping)
            problems: dict[str, list[date]] = dict(coverage_problems)
            for name in missing_mapping:
                problems[name] = []
            raise PriceCoverageError(problems=problems)

        result = pd.concat(priced_parts, ignore_index=True)
        result["market_value"] = result["price"] * result["quantity"]

        totals = result.groupby("date")["market_value"].transform("sum")
        safe_totals = totals.mask(totals == 0, other=1.0)
        result["portfolio_weight"] = (result["market_value"] / safe_totals).where(
            totals != 0, other=0.0
        )

        logger.info(
            "enrich_complete",
            row_count=len(result),
            sub_account_count=result["sub_account"].nunique(),
        )
        return result
