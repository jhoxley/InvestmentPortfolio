"""API router for capital ledger ingestion and retrieval endpoints."""

import re
from pathlib import Path

import structlog
from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from app.config import Settings, get_settings
from app.exceptions import AccountNotFoundError, InvalidAccountNameError
from app.models.capital import CapitalIngestionSummary, CapitalSummary
from app.models.ladder import Links
from app.repositories.capital_repository import CapitalRepository
from app.services.capital_ingestion_service import CapitalIngestionService
from app.services.capital_ledger_expander import CapitalLedgerExpander
from app.validators.capital_ledger import CapitalLedgerValidator

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/accounts", tags=["Capital"])

_ACCOUNT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _validate_account_name(account_name: str) -> None:
    """Raise InvalidAccountNameError if the account name does not match the allowed pattern.

    Args:
        account_name: The account identifier to validate.

    Raises:
        InvalidAccountNameError: If the name contains illegal characters or exceeds 64 chars.
    """
    if not _ACCOUNT_NAME_PATTERN.match(account_name):
        raise InvalidAccountNameError(
            account_name=account_name,
            pattern=_ACCOUNT_NAME_PATTERN.pattern,
        )


def _get_capital_repository(settings: Settings = Depends(get_settings)) -> CapitalRepository:
    """Dependency that returns a CapitalRepository bound to the configured data directory.

    Args:
        settings: Application settings (injected by FastAPI).

    Returns:
        CapitalRepository instance.
    """
    return CapitalRepository(data_dir=settings.data.directory)


def _get_capital_ingestion_service(
    repository: CapitalRepository = Depends(_get_capital_repository),
) -> CapitalIngestionService:
    """Dependency that returns a wired CapitalIngestionService.

    Args:
        repository: CapitalRepository instance (injected by FastAPI).

    Returns:
        CapitalIngestionService instance.
    """
    return CapitalIngestionService(
        repository=repository,
        validator=CapitalLedgerValidator(),
        expander=CapitalLedgerExpander(),
    )


@router.post(
    "/{account_name}/capital",
    summary="Ingest a capital ledger and expand it into a daily business-day series",
    status_code=201,
    response_model=CapitalIngestionSummary,
    responses={
        200: {
            "model": CapitalIngestionSummary,
            "description": "Checksum matched — ledger confirmed current, nothing recomputed",
        },
        409: {"description": "Different file submitted for existing account"},
        422: {
            "description": (
                "Validation failed, or the recorded date range contains no business days"
            )
        },
    },
)
async def ingest_capital_ledger(
    account_name: str,
    file: UploadFile = File(..., description="XLSX capital ledger file"),
    service: CapitalIngestionService = Depends(_get_capital_ingestion_service),
) -> JSONResponse:
    """Accept and process an uploaded capital ledger XLSX.

    Args:
        account_name: Path parameter identifying the account. Must match
            ``^[A-Za-z0-9_-]{1,64}$``.
        file: The uploaded XLSX file produced by create_capital_ledger.
        service: Injected CapitalIngestionService.

    Returns:
        201 Created on first successful ingestion; 200 OK on idempotent re-submit.

    Raises:
        InvalidAccountNameError: Account name fails pattern check.
        SchemaValidationError: Uploaded file fails schema validation.
        EmptyCapitalDateRangeError: Recorded date range contains no business days.
        MergeNotSupportedError: A different file was submitted for an existing account.
    """
    _validate_account_name(account_name)
    file_bytes = await file.read()
    summary = service.ingest(account_name=account_name, file_bytes=file_bytes)
    status_code = 201 if summary.status == "created" else 200
    return JSONResponse(
        status_code=status_code,
        content=summary.model_dump(by_alias=True, mode="json"),
    )


@router.get(
    "/{account_name}/capital",
    summary="Retrieve summary of a stored capital ledger",
    response_model=CapitalSummary,
    responses={404: {"description": "No capital ledger found for this account"}},
)
async def get_capital_ledger_summary(
    account_name: str,
    repository: CapitalRepository = Depends(_get_capital_repository),
) -> JSONResponse:
    """Return a JSON summary of a previously ingested capital ledger.

    Args:
        account_name: Path parameter identifying the account.
        repository: Injected CapitalRepository.

    Returns:
        200 with CapitalSummary JSON body.

    Raises:
        InvalidAccountNameError: Account name fails pattern check.
        AccountNotFoundError: No capital ledger has been stored for this account.
    """
    _validate_account_name(account_name)
    if not repository.exists(account_name):
        raise AccountNotFoundError(
            account_name=account_name,
            message=f"No capital ledger found for account '{account_name}'.",
        )
    meta = repository.read_meta(account_name)
    links = Links(
        self=f"/v1/accounts/{account_name}/capital",
        download=f"/v1/accounts/{account_name}/capital/download",
    )
    summary = CapitalSummary(
        account_name=meta.account_name,
        row_count=meta.row_count,
        from_date=meta.from_date,
        to_date=meta.to_date,
        ingested_at=meta.ingested_at,
        _links=links,
    )
    return JSONResponse(
        status_code=200,
        content=summary.model_dump(by_alias=True, mode="json"),
    )


@router.get(
    "/{account_name}/capital/download",
    summary="Download the full capital ledger as an XLSX binary",
    responses={404: {"description": "No capital ledger found for this account"}},
)
async def download_capital_ledger(
    account_name: str,
    repository: CapitalRepository = Depends(_get_capital_repository),
) -> FileResponse:
    """Return the stored capital ledger XLSX file as a binary download.

    Args:
        account_name: Path parameter identifying the account.
        repository: Injected CapitalRepository.

    Returns:
        FileResponse with application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
        content type and an attachment Content-Disposition header.

    Raises:
        InvalidAccountNameError: Account name fails pattern check.
        AccountNotFoundError: No capital ledger has been stored for this account.
    """
    _validate_account_name(account_name)
    if not repository.exists(account_name):
        raise AccountNotFoundError(
            account_name=account_name,
            message=f"No capital ledger found for account '{account_name}'.",
        )
    xlsx_path: Path = repository.read_xlsx(account_name)
    return FileResponse(
        path=str(xlsx_path),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{account_name}-capital.xlsx"'},
    )
