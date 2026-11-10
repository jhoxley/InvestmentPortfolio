"""Extends a stale capital ledger forward through a target end date, carrying values forward.

Unlike the position ladder, capital/income/book_value have no market-pricing dependency
(research.md R3) -- the extension is a plain forward-fill, always fully resolvable.
"""

from datetime import UTC, date, datetime

import pandas as pd
import structlog

from app.repositories.capital_repository import CapitalRepository
from app.services.business_day_expansion import expand_business_days

logger = structlog.get_logger(__name__)

_VALUE_COLUMNS = ["capital", "income", "book_value"]


class CapitalRebuildService:
    """Extends a stale capital ledger's carried-forward values through a target end date."""

    def __init__(self, repository: CapitalRepository) -> None:
        """Initialise with the capital repository.

        Args:
            repository: Repository for reading and writing capital ledger files.
        """
        self._repository = repository

    def rebuild(self, account_name: str, rebuild_target_end: date) -> None:
        """Extend the stored capital ledger through `rebuild_target_end`.

        Args:
            account_name: The account whose capital ledger is stale.
            rebuild_target_end: The capped target end date (StalenessGate's
                `rebuild_target_end`, already capped at the prior business day).
        """
        log = logger.bind(account_name=account_name, rebuild_target_end=str(rebuild_target_end))
        existing_df = self._repository.read_df(account_name)
        existing_df = existing_df.assign(date=pd.to_datetime(existing_df["date"]).dt.date)
        if "provenance" not in existing_df.columns:
            existing_df = existing_df.assign(provenance="ingested")

        last_known_date: date = existing_df["date"].max()
        if rebuild_target_end <= last_known_date:
            log.info("capital_rebuild_noop", last_known_date=str(last_known_date))
            return

        expanded = expand_business_days(
            existing_df[["date", *_VALUE_COLUMNS]],
            _VALUE_COLUMNS,
            last_known_date,
            rebuild_target_end,
        )
        new_rows = expanded[expanded["date"] > last_known_date].copy()
        new_rows["provenance"] = "projected"

        final_df = pd.concat(
            [existing_df, new_rows[existing_df.columns.tolist()]], ignore_index=True
        )
        final_df = final_df.sort_values("date").reset_index(drop=True)

        meta = self._repository.read_meta(account_name)
        updated_meta = meta.model_copy(
            update={
                "to_date": final_df["date"].max(),
                "row_count": len(final_df),
                "rebuilt_at": datetime.now(UTC),
            }
        )
        self._repository.write(account_name, final_df, updated_meta)
        log.info(
            "capital_rebuild_complete",
            new_to_date=str(updated_meta.to_date),
            row_count=len(final_df),
        )
