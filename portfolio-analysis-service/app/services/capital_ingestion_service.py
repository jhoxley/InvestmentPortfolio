"""Orchestration service for capital ledger ingestion: validate → expand → persist."""

import hashlib
import io
from datetime import UTC, date, datetime

import pandas as pd
import structlog

from app.exceptions import MergeNotSupportedError, SchemaValidationError
from app.models.capital import CapitalIngestionSummary
from app.models.ladder import Links
from app.repositories.capital_repository import CapitalMeta, CapitalRepository
from app.services.capital_ledger_expander import CapitalLedgerExpander
from app.validators.capital_ledger import CapitalLedgerValidator

logger = structlog.get_logger(__name__)


class CapitalIngestionService:
    """Orchestrates the full capital ledger ingestion pipeline.

    Steps for a new account:
    1. Compute SHA-256 checksum of raw file bytes.
    2. If account exists: compare checksum (refresh timestamp only, or 409 on mismatch).
    3. Parse bytes to DataFrame.
    4. Validate schema via CapitalLedgerValidator.
    5. Expand to a daily business-day series via CapitalLedgerExpander.
    6. Persist via CapitalRepository.
    7. Return CapitalIngestionSummary.

    Unlike position ladder ingestion, there is no market-data enrichment step for this
    resource — capital, income, and book_value are already in the account's base
    currency.
    """

    def __init__(
        self,
        repository: CapitalRepository,
        validator: CapitalLedgerValidator,
        expander: CapitalLedgerExpander,
    ) -> None:
        """Initialise with a CapitalRepository, CapitalLedgerValidator, and expander.

        Args:
            repository: Repository for reading and writing capital ledger files.
            validator: Validator for the uploaded capital ledger schema.
            expander: Expander that densifies the sparse capital ledger to daily rows.
        """
        self._repository = repository
        self._validator = validator
        self._expander = expander

    def ingest(self, account_name: str, file_bytes: bytes) -> CapitalIngestionSummary:
        """Process an uploaded capital ledger file for the given account.

        Args:
            account_name: The validated account identifier.
            file_bytes: Raw bytes of the uploaded XLSX file.

        Returns:
            CapitalIngestionSummary describing the result (status 'created' or 'refreshed').

        Raises:
            MergeNotSupportedError: If a capital ledger exists with a different checksum.
            SchemaValidationError: If the uploaded file fails schema validation.
            EmptyCapitalDateRangeError: If the recorded date range contains no business days.
        """
        checksum = hashlib.sha256(file_bytes).hexdigest()
        log = logger.bind(account_name=account_name, checksum=checksum[:8])

        if self._repository.exists(account_name):
            meta = self._repository.read_meta(account_name)
            if meta.checksum == checksum:
                log.info("capital_ingest_refresh", reason="checksum_match")
                # No recomputation occurs — there is no enrichment step to refresh. The
                # stored XLSX is provably unchanged, so it is never rewritten; only the
                # ingestion timestamp is updated.
                refreshed_meta = meta.model_copy(update={"ingested_at": datetime.now(UTC)})
                self._repository.write_meta(account_name, refreshed_meta)
                log.info("capital_ingest_complete", row_count=refreshed_meta.row_count)
                return self._summary_from_meta(refreshed_meta, status="refreshed")
            log.warning("capital_ingest_conflict", reason="checksum_mismatch")
            raise MergeNotSupportedError(
                account_name=account_name,
                message=(
                    f"A capital ledger already exists for '{account_name}' with a different "
                    "checksum. Merging updated capital ledgers is not currently supported."
                ),
            )

        log.info("capital_ingest_start")
        try:
            df = pd.read_excel(io.BytesIO(file_bytes), engine="openpyxl")
        except Exception as exc:
            raise SchemaValidationError(
                fields=["file"],
                message=f"File could not be parsed as XLSX: {exc}",
            ) from exc
        self._validator.validate(df, account_name)

        capital_df = self._expander.expand(df)

        from_date: date = capital_df["date"].min()
        to_date: date = capital_df["date"].max()
        row_count = len(capital_df)

        meta = CapitalMeta(
            account_name=account_name,
            checksum=checksum,
            row_count=row_count,
            from_date=from_date,
            to_date=to_date,
            ingested_at=datetime.now(UTC),
        )
        self._repository.write(account_name, capital_df, meta)
        log.info("capital_ingest_complete", row_count=row_count)

        return self._summary_from_meta(meta, status="created")

    def _summary_from_meta(self, meta: CapitalMeta, status: str) -> CapitalIngestionSummary:
        """Build a CapitalIngestionSummary from stored CapitalMeta.

        Args:
            meta: The CapitalMeta read from or written to the repository.
            status: Either 'created' or 'refreshed'.

        Returns:
            Populated CapitalIngestionSummary with HATEOAS links.
        """
        links = Links(
            self=f"/v1/accounts/{meta.account_name}/capital",
            download=f"/v1/accounts/{meta.account_name}/capital/download",
        )
        return CapitalIngestionSummary(
            account_name=meta.account_name,
            status=status,  # type: ignore[arg-type]
            row_count=meta.row_count,
            from_date=meta.from_date,
            to_date=meta.to_date,
            ingested_at=meta.ingested_at,
            _links=links,
        )
