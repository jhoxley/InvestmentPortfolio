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
from app.validators.ledger import LedgerValidator

logger = structlog.get_logger(__name__)


class IngestionService:
    """Orchestrates the full ledger ingestion pipeline.

    Steps for a new account:
    1. Compute SHA-256 checksum of raw file bytes.
    2. If account exists: compare checksum (idempotent or 409).
    3. Parse bytes to DataFrame.
    4. Validate schema via LedgerValidator.
    5. Expand to daily ladder via LadderExpander.
    6. Persist via LadderRepository.
    7. Return IngestionSummary.
    """

    def __init__(self, repository: LadderRepository) -> None:
        """Initialise with a LadderRepository instance.

        Args:
            repository: Repository for reading and writing ladder files.
        """
        self._repository = repository
        self._validator = LedgerValidator()
        self._expander = LadderExpander()

    def ingest(self, account_name: str, file_bytes: bytes, today: date) -> IngestionSummary:
        """Process an uploaded ledger file for the given account.

        Args:
            account_name: The validated account identifier.
            file_bytes: Raw bytes of the uploaded XLSX file.
            today: Reference date for expansion (T-2 boundary calculation).

        Returns:
            IngestionSummary describing the result (status 'created' or 'unchanged').

        Raises:
            MergeNotSupportedError: If a ladder exists with a different checksum.
            SchemaValidationError: If the uploaded file fails schema validation.
            EmptyDateRangeError: If the expansion date range contains no business days.
        """
        checksum = hashlib.sha256(file_bytes).hexdigest()
        log = logger.bind(account_name=account_name, checksum=checksum[:8])

        if self._repository.exists(account_name):
            meta = self._repository.read_meta(account_name)
            if meta.checksum == checksum:
                log.info("ingest_no_op", reason="checksum_match")
                return self._summary_from_meta(meta, status="unchanged")
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
        self._repository.write(account_name, ladder_df, meta)
        log.info("ingest_complete", row_count=row_count)

        return self._summary_from_meta(meta, status="created")

    def _summary_from_meta(self, meta: AccountMeta, status: str) -> IngestionSummary:
        """Build an IngestionSummary from stored AccountMeta.

        Args:
            meta: The AccountMeta read from or written to the repository.
            status: Either 'created' or 'unchanged'.

        Returns:
            Populated IngestionSummary with HATEOAS links.
        """
        links = Links(
            self_=f"/v1/accounts/{meta.account_name}/ladder",
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
            links=links,
        )
