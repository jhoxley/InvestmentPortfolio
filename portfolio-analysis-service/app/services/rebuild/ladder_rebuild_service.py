"""Extends a stale position ladder forward through a target end date, pricing the gap."""

from datetime import UTC, date, datetime

import pandas as pd
import structlog

from app.clients.market_data_client import MarketDataClient
from app.exceptions import MarketDataServiceError, PriceCoverageError, RebuildUnavailableError
from app.repositories.identifier_mapping_repository import IdentifierMappingRepository
from app.repositories.ladder_repository import LadderRepository
from app.services.ladder_expander import LadderExpander
from app.services.pricing_enrichment_service import PricingEnrichmentService
from app.services.returns_enrichment_service import ReturnsEnrichmentService

logger = structlog.get_logger(__name__)

_CASH = "Cash"
_CASH_PRICE = 1.0
_BASE_COLUMNS = ["date", "sub_account", "book_cost", "quantity", "total_income"]


class LadderRebuildService:
    """Extends a stale ladder's held-constant positions forward, pricing the new days only.

    Reuses `LadderExpander` to carry the last known (book_cost, quantity, total_income)
    forward and apply the existing equity-closure rule, `PricingEnrichmentService` for the
    happy-path all-dates-available pricing call, and `ReturnsEnrichmentService` for the
    new rows' returns. Only the gap itself is priced -- previously persisted rows are
    never re-fetched or re-written.
    """

    def __init__(
        self,
        repository: LadderRepository,
        mapping_repo: IdentifierMappingRepository,
        market_data_client: MarketDataClient,
        enrichment_service: PricingEnrichmentService,
        returns_service: ReturnsEnrichmentService,
    ) -> None:
        """Initialise with the repository, pricing dependencies, and enrichment services.

        Args:
            repository: Repository for reading and writing ladder files.
            mapping_repo: Repository resolving sub-account names to identifiers, used for
                the tolerant partial-pricing fallback (bypassing PricingEnrichmentService's
                all-or-nothing contract without modifying it).
            market_data_client: Client used for the same tolerant fallback.
            enrichment_service: Shared service for the happy-path (all dates available) call.
            returns_service: Shared service that computes position_return/weighted_position_return.
        """
        self._repository = repository
        self._mapping_repo = mapping_repo
        self._market_data_client = market_data_client
        self._enrichment_service = enrichment_service
        self._returns_service = returns_service
        self._expander = LadderExpander()

    def rebuild(self, account_name: str, rebuild_target_end: date) -> None:
        """Extend the stored ladder through `rebuild_target_end`, pricing only the gap.

        Args:
            account_name: The account whose ladder is stale.
            rebuild_target_end: The capped target end date (StalenessGate's
                `rebuild_target_end`, already capped at the prior business day).

        Raises:
            RebuildUnavailableError: If no pricing at all could be sourced for the gap;
                nothing is persisted and the caller should fall back to the prior read.
        """
        log = logger.bind(account_name=account_name, rebuild_target_end=str(rebuild_target_end))
        existing_full_df = self._repository.read_full_df(account_name)
        existing_full_df = existing_full_df.assign(
            date=pd.to_datetime(existing_full_df["date"]).dt.date
        )
        if "provenance" not in existing_full_df.columns:
            existing_full_df = existing_full_df.assign(provenance="ingested")

        last_known_date: date = existing_full_df["date"].max()
        if rebuild_target_end <= last_known_date:
            log.info("ladder_rebuild_noop", last_known_date=str(last_known_date))
            return

        seed = existing_full_df[existing_full_df["date"] == last_known_date][
            ["date", "sub_account", "book_cost", "quantity", "total_income"]
        ]
        expanded_seed = self._expander.expand(seed, rebuild_target_end, end_date=rebuild_target_end)
        new_base = expanded_seed[expanded_seed["date"] > last_known_date].copy()

        if new_base.empty:
            log.info("ladder_rebuild_noop_all_closed")
            meta = self._repository.read_meta(account_name)
            self._repository.write(
                account_name,
                existing_full_df,
                meta.model_copy(update={"rebuilt_at": datetime.now(UTC)}),
            )
            return

        last_rows = existing_full_df[existing_full_df["date"] == last_known_date]
        try:
            priced_new = self._price_happy_path(new_base, last_rows)
        except (PriceCoverageError, MarketDataServiceError) as exc:
            log.warning("ladder_rebuild_pricing_problem", detail=str(exc))
            priced_new = self._price_tolerant(new_base, last_rows, account_name)

        priced_new = priced_new.assign(provenance="projected")
        final_df = pd.concat(
            [existing_full_df, priced_new[existing_full_df.columns.tolist()]],
            ignore_index=True,
        )
        final_df = final_df.sort_values(["date", "sub_account"]).reset_index(drop=True)

        meta = self._repository.read_meta(account_name)
        new_to_date = final_df["date"].max()
        updated_meta = meta.model_copy(
            update={
                "to_date": new_to_date,
                "row_count": len(final_df),
                "rebuilt_at": datetime.now(UTC),
            }
        )
        self._repository.write(account_name, final_df, updated_meta)
        log.info("ladder_rebuild_complete", new_to_date=str(new_to_date), row_count=len(final_df))

    def _price_happy_path(self, new_base: pd.DataFrame, last_rows: pd.DataFrame) -> pd.DataFrame:
        """Price the gap via the shared enrichment services, with no tolerance for gaps.

        Args:
            new_base: The new rows (date > last_known_date) with base columns only.
            last_rows: The single last-known-date row per sub-account, with full columns,
                used as context so the first new row's return is computed correctly.

        Returns:
            The new rows only, priced and with returns computed, same shape as `new_base`
            plus [price, market_value, portfolio_weight, position_return,
            weighted_position_return].

        Raises:
            PriceCoverageError: If any (sub_account, date) in the gap cannot be priced.
            MarketDataServiceError: If a market-data-service request fails outright.
        """
        enriched_new = self._enrichment_service.enrich(new_base)
        combined = pd.concat(
            [
                last_rows[
                    [
                        "date",
                        "sub_account",
                        "book_cost",
                        "quantity",
                        "total_income",
                        "price",
                        "market_value",
                        "portfolio_weight",
                    ]
                ],
                enriched_new,
            ],
            ignore_index=True,
        )
        combined_with_returns = self._returns_service.enrich(combined)
        result = combined_with_returns[combined_with_returns["date"] > last_rows["date"].iloc[0]]
        return result.reset_index(drop=True)

    def _price_tolerant(
        self, new_base: pd.DataFrame, last_rows: pd.DataFrame, account_name: str
    ) -> pd.DataFrame:
        """Price the gap tolerantly, leaving unresolvable (sub_account, date) pairs null.

        Bypasses PricingEnrichmentService's all-or-nothing contract (left unchanged for
        every other caller, per research.md R7) by resolving identifiers and calling the
        market-data client directly, the same way PricingEnrichmentService itself does.

        Args:
            new_base: The new rows (date > last_known_date) with base columns only.
            last_rows: The single last-known-date row per sub-account, with full columns.
            account_name: The account being rebuilt (for logging only).

        Returns:
            The new rows, priced where possible; `price`/`market_value`/`portfolio_weight`/
            `position_return`/`weighted_position_return` are null (NaN) for any
            (sub_account, date) that could not be priced.

        Raises:
            RebuildUnavailableError: If literally nothing in the gap could be priced.
        """
        df = new_base.copy()
        df["price"] = pd.Series([pd.NA] * len(df), dtype="object")
        any_priced = False

        for sub_account, group in df.groupby("sub_account", sort=False):
            if str(sub_account) == _CASH:
                df.loc[group.index, "price"] = _CASH_PRICE
                any_priced = True
                continue

            entry = self._mapping_repo.lookup(str(sub_account))
            identifier = (entry.ticker or entry.isin) if entry else None
            if identifier is None:
                continue

            min_date = group["date"].min()
            max_date = group["date"].max()
            try:
                points = self._market_data_client.get_price_history(
                    identifier, min_date, max_date, "GBP"
                )
            except MarketDataServiceError:
                continue

            price_by_date = {p.date: p.close for p in points}
            for idx, row in group.iterrows():
                price = price_by_date.get(row["date"])
                if price is not None:
                    df.at[idx, "price"] = price
                    any_priced = True

        if not any_priced:
            raise RebuildUnavailableError(account_name=account_name, resource="ladder")

        df["price"] = pd.to_numeric(df["price"], errors="coerce")
        df["market_value"] = df["price"] * df["quantity"]
        totals = df.groupby("date")["market_value"].transform("sum")
        df["portfolio_weight"] = df["market_value"] / totals

        combined = pd.concat(
            [
                last_rows[
                    [
                        "date",
                        "sub_account",
                        "book_cost",
                        "quantity",
                        "total_income",
                        "price",
                        "market_value",
                        "portfolio_weight",
                    ]
                ],
                df,
            ],
            ignore_index=True,
        )
        with_returns = self._returns_service.enrich(combined)
        result = with_returns[with_returns["date"] > last_rows["date"].iloc[0]]
        return result.reset_index(drop=True)
