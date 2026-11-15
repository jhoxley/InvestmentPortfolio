"""Orchestration service for ledger ingestion: validate → checksum → expand → persist."""

import hashlib
import io
from datetime import UTC, date, datetime

import pandas as pd
import structlog

from app.exceptions import MergeNotSupportedError, SchemaValidationError
from app.models.ladder import IngestionSummary, Links
from app.repositories.ladder_repository import AccountMeta, LadderRepository
from app.services.ladder_expander import LadderExpander
from app.services.pricing_enrichment_service import PricingEnrichmentService
from app.services.returns_enrichment_service import ReturnsEnrichmentService
from app.validators.ledger import LedgerValidator

logger = structlog.get_logger(__name__)


class IngestionService:
    """Orchestrates the full ledger ingestion pipeline.

    Steps for a new account:
    1. Compute SHA-256 checksum of raw file bytes.
    2. If account exists: compare checksum (refresh pricing, or 409 on mismatch).
    3. Parse bytes to DataFrame.
    4. Validate schema via LedgerValidator.
    5. Expand to daily ladder via LadderExpander.
    6. Enrich with price/market_value/portfolio_weight via PricingEnrichmentService.
    7. Enrich with position_return/weighted_position_return via ReturnsEnrichmentService.
    8. Persist via LadderRepository.
    9. Return IngestionSummary.
    """

    def __init__(
        self,
        repository: LadderRepository,
        enrichment_service: PricingEnrichmentService,
        returns_service: ReturnsEnrichmentService,
    ) -> None:
        """Initialise with a LadderRepository and the two enrichment services.

        Args:
            repository: Repository for reading and writing ladder files.
            enrichment_service: Service that adds price/market_value/portfolio_weight.
            returns_service: Service that adds position_return/weighted_position_return.
        """
        self._repository = repository
        self._enrichment_service = enrichment_service
        self._returns_service = returns_service
        self._validator = LedgerValidator()
        self._expander = LadderExpander()

    def ingest(self, account_name: str, file_bytes: bytes, today: date) -> IngestionSummary:
        """Process an uploaded ledger file for the given account.

        Args:
            account_name: The validated account identifier.
            file_bytes: Raw bytes of the uploaded XLSX file.
            today: Reference date for expansion (T-2 boundary calculation).

        Returns:
            IngestionSummary describing the result (status 'created' or 'refreshed').

        Raises:
            MergeNotSupportedError: If a ladder exists with a different checksum.
            SchemaValidationError: If the uploaded file fails schema validation.
            EmptyDateRangeError: If the expansion date range contains no business days.
            IdentifierMappingError: If a non-Cash sub-account has no usable mapping entry.
            PriceCoverageError: If a GBP price cannot be obtained for every business day.
            MarketDataServiceError: If a market-data-service request fails.
        """
        checksum = hashlib.sha256(file_bytes).hexdigest()
        log = logger.bind(account_name=account_name, checksum=checksum[:8])

        if self._repository.exists(account_name):
            meta = self._repository.read_meta(account_name)
            if meta.checksum == checksum:
                log.info("ingest_refresh", reason="checksum_match")
                base_df = self._repository.read_ladder_df(account_name)
                enriched_df = self._enrichment_service.enrich(base_df)
                enriched_df = self._returns_service.enrich(enriched_df)
                refreshed_meta = meta.model_copy(update={"ingested_at": datetime.now(UTC)})
                self._repository.write(account_name, enriched_df, refreshed_meta)
                log.info("ingest_refresh_complete", row_count=refreshed_meta.row_count)
                return self._summary_from_meta(refreshed_meta, status="refreshed")

            superseded = self._try_supersede_projected_span(account_name, file_bytes, today)
            if superseded is not None:
                return superseded
            log.warning("ingest_conflict", reason="checksum_mismatch")
            raise MergeNotSupportedError(account_name=account_name)

        log.info("ingest_start")
        try:
            df = pd.read_excel(io.BytesIO(file_bytes), engine="openpyxl")
        except Exception as exc:
            raise SchemaValidationError(
                fields=["file"],
                message=f"File could not be parsed as XLSX: {exc}",
            ) from exc
        self._validator.validate(df, account_name, today)

        ladder_df = self._expander.expand(df, today)
        ladder_df = ladder_df.assign(provenance="ingested")
        enriched_df = self._enrichment_service.enrich(ladder_df)
        enriched_df = self._returns_service.enrich(enriched_df)

        sub_accounts: list[str] = sorted(ladder_df["sub_account"].unique().tolist())
        from_date: date = ladder_df["date"].min()
        to_date: date = ladder_df["date"].max()
        row_count = len(ladder_df)

        meta = AccountMeta(
            account_name=account_name,
            checksum=checksum,
            row_count=row_count,
            from_date=from_date,
            to_date=to_date,
            sub_accounts=sub_accounts,
            ingested_at=datetime.now(UTC),
        )
        self._repository.write(account_name, enriched_df, meta)
        log.info("ingest_complete", row_count=row_count)

        return self._summary_from_meta(meta, status="created")

    def _try_supersede_projected_span(
        self, account_name: str, file_bytes: bytes, today: date
    ) -> IngestionSummary | None:
        """Re-ingest a checksum-mismatched ledger if it overlaps a previously rebuilt span.

        Implements research.md R5: a new ledger whose own date range overlaps any
        `provenance="projected"` row in the currently stored ladder must correctly
        supersede that projection (FR-008), rather than being unconditionally rejected
        as an unsupported merge. A new ledger with no such overlap falls through
        unchanged to today's existing `MergeNotSupportedError` behaviour (FR-007).

        Args:
            account_name: The account being re-ingested.
            file_bytes: Raw bytes of the newly uploaded XLSX file.
            today: Reference date for expansion (T-2 boundary calculation).
            log: Bound logger from the caller.

        Returns:
            An IngestionSummary with status 'created' if supersession applied, or None
            if the new ledger's range does not overlap any projected span (caller then
            raises MergeNotSupportedError as before).

        Raises:
            SchemaValidationError: If the uploaded file fails schema validation.
            EmptyDateRangeError: If the resulting expansion range has no business days.
            IdentifierMappingError, PriceCoverageError, MarketDataServiceError: As for a
                normal new-account ingestion.
        """
        log = logger.bind(account_name=account_name)
        existing_full_df = self._repository.read_full_df(account_name)
        existing_full_df = existing_full_df.assign(
            date=pd.to_datetime(existing_full_df["date"]).dt.date
        )
        if "provenance" not in existing_full_df.columns:
            return None  # nothing was ever projected; no supersession is possible

        try:
            new_df = pd.read_excel(io.BytesIO(file_bytes), engine="openpyxl")
        except Exception as exc:
            raise SchemaValidationError(
                fields=["file"],
                message=f"File could not be parsed as XLSX: {exc}",
            ) from exc
        new_df = new_df.copy()
        new_df["date"] = pd.to_datetime(new_df["date"]).dt.date
        new_min, new_max = new_df["date"].min(), new_df["date"].max()

        projected_mask = existing_full_df["provenance"] == "projected"
        overlap = existing_full_df[
            projected_mask
            & (existing_full_df["date"] >= new_min)
            & (existing_full_df["date"] <= new_max)
        ]
        if overlap.empty:
            return None

        log.info(
            "ingest_supersedes_projected_span",
            overlap_row_count=len(overlap),
            new_from_date=str(new_min),
            new_to_date=str(new_max),
        )

        self._validator.validate(new_df, account_name, today)

        existing_ladder_df = self._repository.read_ladder_df(account_name)
        existing_ladder_df = existing_ladder_df.assign(
            date=pd.to_datetime(existing_ladder_df["date"]).dt.date
        )
        seed = existing_ladder_df[existing_ladder_df["date"] < new_min][
            ["date", "sub_account", "book_cost", "quantity", "total_income"]
        ]
        combined_sparse = pd.concat([seed, new_df], ignore_index=True)

        expanded_df = self._expander.expand(combined_sparse, today)
        expanded_df = expanded_df.assign(
            provenance=expanded_df["date"].apply(
                lambda d, _max=new_max: "ingested" if d <= _max else "projected"
            )
        )
        enriched_df = self._enrichment_service.enrich(expanded_df)
        enriched_df = self._returns_service.enrich(enriched_df)

        sub_accounts: list[str] = sorted(expanded_df["sub_account"].unique().tolist())
        new_checksum = hashlib.sha256(file_bytes).hexdigest()
        meta = AccountMeta(
            account_name=account_name,
            checksum=new_checksum,
            row_count=len(expanded_df),
            from_date=expanded_df["date"].min(),
            to_date=expanded_df["date"].max(),
            sub_accounts=sub_accounts,
            ingested_at=datetime.now(UTC),
            rebuilt_at=None,
        )
        self._repository.write(account_name, enriched_df, meta)
        log.info("ingest_supersedes_projected_span_complete", row_count=len(expanded_df))

        return self._summary_from_meta(meta, status="created")

    def _summary_from_meta(self, meta: AccountMeta, status: str) -> IngestionSummary:
        """Build an IngestionSummary from stored AccountMeta.

        Args:
            meta: The AccountMeta read from or written to the repository.
            status: Either 'created' or 'refreshed'.

        Returns:
            Populated IngestionSummary with HATEOAS links.
        """
        links = Links(
            self=f"/v1/accounts/{meta.account_name}/ladder",
            download=f"/v1/accounts/{meta.account_name}/ladder/download",
        )
        return IngestionSummary(
            account_name=meta.account_name,
            status=status,  # type: ignore[arg-type]
            row_count=meta.row_count,
            from_date=meta.from_date,
            to_date=meta.to_date,
            sub_accounts=meta.sub_accounts,
            ingested_at=meta.ingested_at,
            _links=links,
        )
