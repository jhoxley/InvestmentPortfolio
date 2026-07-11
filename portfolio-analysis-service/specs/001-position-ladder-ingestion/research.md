# Research: Position Ladder Ingestion

**Feature**: 001-position-ladder-ingestion
**Date**: 2026-07-06

## Technology Stack

### Decision: Python 3.11
**Rationale**: Pinned in the market-data-web-service `pyproject.toml`; consistent across
the monorepo. Full type union syntax (`X | Y`) and `tomllib` available.
**Alternatives considered**: 3.12 — rejected to stay aligned with existing services.

### Decision: FastAPI 0.115 + uvicorn
**Rationale**: Direct match to market-data-web-service. File upload handled via FastAPI's
`UploadFile` + `File(...)` dependency. Automatic OpenAPI schema generation included.
**Alternatives considered**: Flask — rejected; async support weaker, no automatic OpenAPI.

### Decision: pandas + openpyxl for XLSX I/O
**Rationale**: `pandas.read_excel` / `DataFrame.to_excel` with `openpyxl` engine handles
both read and write of `.xlsx` with named columns. pandas is already used throughout the
AccountPreparationPipeline.
**Alternatives considered**: `openpyxl` direct — more verbose, no DataFrame semantics.

### Decision: SHA-256 checksum of raw file bytes
**Rationale**: Deterministic, collision-resistant, no extra dependencies (`hashlib` is stdlib).
Computing the digest on the raw `UploadFile` bytes before parsing avoids any
normalisation ambiguity.
**Alternatives considered**: MD5 — deprecated for integrity use; CRC32 — weaker collision
resistance.

### Decision: structlog with JSONRenderer
**Rationale**: Exact pattern from `market-data-web-service/app/logging_config.py`.
Copy verbatim to keep log format consistent across services.
**Alternatives considered**: stdlib logging — no structured key=value support out of the box.

### Decision: pytest-bdd 7 with `.feature` / `_steps.py` pairs
**Rationale**: Already in market-data-web-service dev dependencies. Tests live in
`tests/features/*.feature` with matching `tests/steps/*_steps.py`. `conftest.py` wires
the FastAPI `TestClient`.
**Alternatives considered**: behave — separate runner, inconsistent with existing CI setup.

## Storage Layout

### Decision: Filesystem store — one directory per account
```
data/
  {account_name}/
    ladder.xlsx      # expanded daily position ladder
    meta.json        # {"checksum": "...", "row_count": N, "from_date": "...",
                     #  "to_date": "...", "sub_accounts": [...]}
```
**Rationale**: Human-readable (XLSX openable in Excel), no database dependency, trivially
inspectable for support. `meta.json` enables O(1) checksum comparison and provides the
summary payload for JSON responses without re-reading the XLSX.
**Alternatives considered**: SQLite — adds migration complexity; single flat XLSX — cannot
distinguish meta from data.

## HATEOAS Link Pattern

All response models include a `_links: dict[str, str]` field following the pattern:
```json
{
  "_links": {
    "self":     "/v1/accounts/{name}/ladder",
    "download": "/v1/accounts/{name}/ladder/download"
  }
}
```
This matches Constitution Principle V and keeps links discoverable without hardcoding URLs
in clients.

## Business Day Calculation

`pandas.bdate_range(start, end)` generates business days (Mon–Fri) natively with no
holiday calendar. This matches the spec's definition of "business days = Mon–Fri only."

## Position Expansion Algorithm

```
for each account in sub-account ledger:
    event_dates = sorted unique dates with activity
    full_range = bdate_range(min_date, today - 2 bdays)
    for each business_day in full_range:
        for each sub_account with last_known_quantity > 0 OR sub_account == "Cash":
            emit row with forward-filled values
```

Forward-fill is implemented as `reindex(full_range).ffill()` per sub-account group, then
filter out rows where `quantity == 0` for non-Cash sub-accounts.

## API Versioning

All routes prefixed `/v1/` to match Constitution Principle V mandate for explicit versioning.

## Error Handling

Custom exception classes (matching market-data-web-service pattern) registered as FastAPI
exception handlers returning RFC 7807 Problem Details (`application/problem+json`).
