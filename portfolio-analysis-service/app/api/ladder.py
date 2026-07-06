"""API router for position ladder ingestion and retrieval endpoints."""

import re
from datetime import date
from pathlib import Path

import structlog
from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from app.config import Settings, get_settings
from app.exceptions import AccountNotFoundError, InvalidAccountNameError
from app.models.ladder import IngestionSummary, LadderSummary, Links
from app.repositories.ladder_repository import LadderRepository
from app.services.ingestion_service import IngestionService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/accounts", tags=["Ladder"])

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


def _get_repository(settings: Settings = Depends(get_settings)) -> LadderRepository:
    """Dependency that returns a LadderRepository bound to the configured data directory.

    Args:
        settings: Application settings (injected by FastAPI).

    Returns:
        LadderRepository instance.
    """
    return LadderRepository(data_dir=settings.data.directory)


def _get_ingestion_service(
    repository: LadderRepository = Depends(_get_repository),
) -> IngestionService:
    """Dependency that returns a wired IngestionService.

    Args:
        repository: LadderRepository instance (injected by FastAPI).

    Returns:
        IngestionService instance.
    """
    return IngestionService(repository=repository)


@router.post(
    "/{account_name}/ladder",
    summary="Ingest a sub-account ledger and generate a daily position ladder",
    status_code=201,
    response_model=IngestionSummary,
    responses={
        200: {"model": IngestionSummary, "description": "Checksum matched — no reprocessing"},
        409: {"description": "Different file submitted for existing account"},
        422: {"description": "Validation failed"},
    },
)
async def ingest_ladder(
    account_name: str,
    file: UploadFile = File(..., description="XLSX sub-account ledger file"),
    service: IngestionService = Depends(_get_ingestion_service),
) -> JSONResponse:
    """Accept and process an uploaded sub-account ledger XLSX.

    Args:
        account_name: Path parameter identifying the account. Must match
            ``^[A-Za-z0-9_-]{1,64}$``.
        file: The uploaded XLSX file produced by create_subaccount_ledger.
        service: Injected IngestionService.

    Returns:
        201 Created on first successful ingestion; 200 OK on idempotent re-submit.

    Raises:
        InvalidAccountNameError: Account name fails pattern check.
        SchemaValidationError: Uploaded file fails schema validation.
        EmptyDateRangeError: Expansion range contains no business days.
        MergeNotSupportedError: A different file was submitted for an existing account.
    """
    _validate_account_name(account_name)
    file_bytes = await file.read()
    today = date.today()
    summary = service.ingest(account_name=account_name, file_bytes=file_bytes, today=today)
    status_code = 201 if summary.status == "created" else 200
    return JSONResponse(
        status_code=status_code,
        content=summary.model_dump(by_alias=True, mode="json"),
    )


@router.get(
    "/{account_name}/ladder",
    summary="Retrieve summary of a stored position ladder",
    response_model=LadderSummary,
    responses={404: {"description": "No ladder found for this account"}},
)
async def get_ladder_summary(
    account_name: str,
    repository: LadderRepository = Depends(_get_repository),
) -> JSONResponse:
    """Return a JSON summary of a previously ingested position ladder.

    Args:
        account_name: Path parameter identifying the account.
        repository: Injected LadderRepository.

    Returns:
        200 with LadderSummary JSON body.

    Raises:
        InvalidAccountNameError: Account name fails pattern check.
        AccountNotFoundError: No ladder has been stored for this account.
    """
    _validate_account_name(account_name)
    if not repository.exists(account_name):
        raise AccountNotFoundError(account_name=account_name)
    meta = repository.read_meta(account_name)
    links = Links(
        self_=f"/v1/accounts/{account_name}/ladder",
        download=f"/v1/accounts/{account_name}/ladder/download",
    )
    summary = LadderSummary(
        account_name=meta.account_name,
        row_count=meta.row_count,
        from_date=meta.from_date,
        to_date=meta.to_date,
        sub_accounts=meta.sub_accounts,
        ingested_at=meta.ingested_at,
        links=links,
    )
    return JSONResponse(
        status_code=200,
        content=summary.model_dump(by_alias=True, mode="json"),
    )


@router.get(
    "/{account_name}/ladder/download",
    summary="Download the full position ladder as an XLSX binary",
    responses={404: {"description": "No ladder found for this account"}},
)
async def download_ladder(
    account_name: str,
    repository: LadderRepository = Depends(_get_repository),
) -> FileResponse:
    """Return the stored position ladder XLSX file as a binary download.

    Args:
        account_name: Path parameter identifying the account.
        repository: Injected LadderRepository.

    Returns:
        FileResponse with application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
        content type and an attachment Content-Disposition header.

    Raises:
        InvalidAccountNameError: Account name fails pattern check.
        AccountNotFoundError: No ladder has been stored for this account.
    """
    _validate_account_name(account_name)
    if not repository.exists(account_name):
        raise AccountNotFoundError(account_name=account_name)
    xlsx_path: Path = repository.read_xlsx(account_name)
    return FileResponse(
        path=str(xlsx_path),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{account_name}-ladder.xlsx"'},
    )
