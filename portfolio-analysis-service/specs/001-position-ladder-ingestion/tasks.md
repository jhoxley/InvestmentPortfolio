---
description: "Task list for Position Ladder Ingestion feature"
---

# Tasks: Position Ladder Ingestion

**Input**: Design documents from `/specs/001-position-ladder-ingestion/`
**Prerequisites**: plan.md âœ…, spec.md âœ…, research.md âœ…, data-model.md âœ…, contracts/openapi.yaml âœ…

**Tests**: Required â€” Constitution Principle I mandates TDD with BDD/Gherkin. Test tasks appear
before their corresponding implementation tasks in every phase.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to ([US1]â€“[US4])
- Exact file paths included in all descriptions

---

## Phase 1: Setup

**Purpose**: Project initialization and basic structure â€” no dependencies, start immediately.

- [X] T001 Create portfolio-analysis-service project directory structure: `app/`, `app/api/`, `app/models/`, `app/services/`, `app/repositories/`, `app/validators/`, `tests/`, `tests/features/`, `tests/steps/`, `tests/unit/`, `data/`, `logs/`; add `.gitignore` entries for `data/` and `logs/`
- [X] T002 [P] Create `pyproject.toml` mirroring market-data-web-service: project name `portfolio-analysis-service`, Python â‰¥3.11, runtime deps (fastapi==0.115.*, uvicorn[standard]>=0.29, pandas>=2.0, openpyxl>=3.1, pydantic>=2.0, structlog>=24.0, pyyaml>=6.0), dev deps (pytest>=8.0, pytest-bdd>=7.0, ruff>=0.4, mypy>=1.10, httpx>=0.27); include ruff and mypy config sections matching market-data-web-service settings; in `[tool.ruff.lint]` add `"D"` (pydocstyle) to `select` to enforce docstrings on all public symbols (Constitution III); in `[tool.pytest.ini_options]` set `bdd_features_base_dir = "tests/features"` and `markers = ["us1: User Story 1 scenarios", "us2: User Story 2 scenarios", "us3: User Story 3 scenarios", "us4: User Story 4 scenarios", "validation: Validation edge-case scenarios"]`
- [X] T003 [P] Create `config.yaml` (runtime config: `data.directory: ./data`) and `app/config.py` â€” Pydantic `Settings` model with `DataSettings(directory: Path)`, `load_settings()`, and `get_settings()` singleton; mirrors market-data-web-service `app/config.py` pattern
- [X] T004 [P] Create `requirements.txt` pinning all runtime dependencies to exact versions (`pip freeze` after install into a clean venv); add `requirements-dev.txt` pinning dev dependencies

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared infrastructure required by every user story. No user story work begins until this phase is complete.

**âš ï¸ CRITICAL**: All user story phases depend on this phase being fully complete.

- [X] T005 Implement `app/logging_config.py` â€” copy `setup_logging()` pattern verbatim from `market-data-web-service/app/logging_config.py`; change log file name to `portfolio-analysis-api.log`; structlog JSONRenderer with ISO timestamps
- [X] T006 [P] Define domain exception classes in `app/exceptions.py`: `InvalidAccountNameError(account_name: str, pattern: str)`, `SchemaValidationError(fields: list[str], message: str)`, `AccountNotFoundError(account_name: str)`, `MergeNotSupportedError(account_name: str)`, `EmptyDateRangeError(account_name: str, earliest_date: date)`; each with a `message` attribute
- [X] T007 [P] Define all Pydantic response models in `app/models/ladder.py`: `Links(self_: str, download: str)` with `model_config = ConfigDict(populate_by_name=True)` and `Field(alias="self")` on `self_`; `IngestionSummary`; `LadderSummary`; `ProblemDetail`; match schemas in `contracts/openapi.yaml` exactly
- [X] T008 [P] Implement `app/repositories/ladder_repository.py` â€” `LadderRepository(data_dir: Path)` class with methods: `exists(account_name: str) -> bool`, `read_meta(account_name: str) -> AccountMeta`, `write(account_name: str, df: pd.DataFrame, meta: AccountMeta) -> None` (writes `ladder.xlsx` via openpyxl + `meta.json`), `read_xlsx(account_name: str) -> Path`; `AccountMeta` is a Pydantic model matching `data-model.md`; use atomic write (write to `.tmp` then `os.replace`)
- [X] T009 Create `app/main.py` â€” FastAPI app (`title="Portfolio Analysis API"`, `version="0.1.0"`); lifespan that calls `setup_logging()`, initialises settings, creates data directory; HTTP request/response logging middleware that generates a `correlation_id = str(uuid.uuid4())` per request, binds it to the structlog context via `structlog.contextvars.bind_contextvars(correlation_id=correlation_id)`, and logs method, path, status, duration_ms, and correlation_id on every response (Constitution IV); register exception handlers for `InvalidAccountNameError` (422), `SchemaValidationError` (422), `AccountNotFoundError` (404), `MergeNotSupportedError` (409), `EmptyDateRangeError` (422), all returning `ProblemDetail` as `application/problem+json`; include routers from `app/api/ladder.py` and `app/api/health.py`
- [X] T010 [P] Create `app/api/health.py` â€” `GET /health` returns `{"status": "ok"}`; `GET /ready` checks that `settings.data.directory` exists and is a directory, returns `{"status": "ready"}` (200) or `ProblemDetail` (503) if not accessible; prefix both with no version prefix (operational endpoints)
- [X] T011 [P] Create `tests/conftest.py` â€” pytest fixtures: `app_client` (FastAPI `TestClient` with a `tmp_path`-backed data directory injected via dependency override on `get_settings`); `sample_ledger_df` (minimal valid DataFrame with columns date/sub_account/book_cost/quantity/total_income); `sample_ledger_bytes(sample_ledger_df)` (serialise DataFrame to XLSX bytes in memory using `BytesIO`); `sample_ledger_file(sample_ledger_bytes)` (wrap bytes as an `UploadFile`-compatible dict for TestClient multipart POST)

**Checkpoint**: Foundation complete â€” all user story phases may now proceed.

---

## Phase 3: User Story 1 â€” New Ledger Submission (Priority: P1) ðŸŽ¯ MVP

**Goal**: Accept, validate, expand, and persist a new sub-account ledger; return ingestion summary with download link.

**Independent Test**: `POST /v1/accounts/test-portfolio/ladder` with a valid XLSX â†’ 201 Created with JSON summary; `data/test-portfolio/ladder.xlsx` exists with correct rows; `data/test-portfolio/meta.json` contains matching checksum.

### Tests for User Story 1 âš ï¸ Write and verify FAILING before implementing

- [X] T012 [P] [US1] Write Gherkin feature file `tests/features/ingest_ladder.feature` containing US1 scenarios from `spec.md`: "Successful ingestion of a new sub-account ledger", "Position forward-fill across days with no activity", "Closed equity positions are excluded from subsequent dates", "Cash sub-account always appears regardless of balance" â€” use exact Gherkin from spec; add `@us1` tag to each scenario
- [X] T013 [P] [US1] Write failing unit tests for schema validation in `tests/unit/test_ledger_validator.py`: `test_valid_file_passes()`, `test_missing_column_raises()` (each of the 5 required columns), `test_non_numeric_book_cost_raises()`, `test_unparseable_date_raises()`, `test_empty_dataframe_raises()`, `test_earliest_date_within_t2_raises()`; import `LedgerValidator` from `app/validators/ledger.py` (will fail at import until T015)
- [X] T014 [P] [US1] Write failing unit tests for ladder expansion in `tests/unit/test_ladder_expander.py`: `test_forward_fill_across_gap_days()`, `test_equity_excluded_after_quantity_zero()`, `test_cash_always_present_at_zero_balance()`, `test_only_business_days_in_output()`, `test_date_range_ends_at_t_minus_2()`, `test_all_sub_accounts_closed_before_t_minus_2_stores_partial_ladder()` (verifies that a ledger where all equities hit quantity=0 well before T-2 is accepted; stored ladder contains rows only through the final closure date; no error is raised); import `LadderExpander` from `app/services/ladder_expander.py` (will fail at import until T016)

### Implementation for User Story 1

- [X] T015 [P] [US1] Implement `app/validators/ledger.py` â€” `LedgerValidator` class with `validate(df: pd.DataFrame, account_name: str, today: date) -> None`; check required columns present (raise `SchemaValidationError` listing missing); check `date` column parseable (raise `SchemaValidationError`); check `book_cost`, `quantity`, `total_income` numeric (raise `SchemaValidationError`); check at least one data row; compute expansion end date as `today - 2 business days` and raise `EmptyDateRangeError` if `min(date) >= end_date`; all raising specific exception types from `app/exceptions.py`; run `T013` tests to verify they pass after implementation
- [X] T016 [P] [US1] Implement `app/services/ladder_expander.py` â€” `LadderExpander` class with `expand(df: pd.DataFrame, today: date) -> pd.DataFrame`; use `pandas.bdate_range(min_date, today - 2 business days)` for date range; for each sub-account group: reindex to full date range, `ffill()` all value columns; filter out rows where `sub_account != "Cash"` and `quantity == 0`; return DataFrame with columns `[date, sub_account, book_cost, quantity, total_income]` sorted by `(date, sub_account)`; run `T014` tests to verify they pass
- [X] T017 [US1] Implement `app/services/ingestion_service.py` â€” `IngestionService(repository: LadderRepository)` with `ingest(account_name: str, file_bytes: bytes, today: date) -> IngestionSummary`; compute SHA-256 hex digest of `file_bytes`; if account exists: compare checksum â€” if match return `IngestionSummary(status="unchanged", ...)` populated from `meta.json`; if mismatch raise `MergeNotSupportedError`; if new: parse bytes to DataFrame via `pandas.read_excel(BytesIO(file_bytes))`; validate via `LedgerValidator`; expand via `LadderExpander`; build `AccountMeta` (row_count, from_date, to_date, sub_accounts, ingested_at=datetime.now(timezone.utc)) â€” use `from datetime import timezone` not the deprecated `datetime.utcnow()`; write via `LadderRepository`; return `IngestionSummary(status="created", ...)` with `_links` populated using account name; depends on T015, T016, T008
- [X] T018 [US1] Add `POST /v1/accounts/{account_name}/ladder` handler to `app/api/ladder.py` â€” validate `account_name` matches `^[A-Za-z0-9_-]{1,64}$` (raise `InvalidAccountNameError(account_name=account_name, pattern="^[A-Za-z0-9_-]{1,64}$")` if not â€” use `InvalidAccountNameError`, not `SchemaValidationError`, as they are distinct error domains); read `UploadFile` bytes; call `IngestionService.ingest()`; return 201 for `created`, 200 for `unchanged`; router prefix `/v1/accounts`, tag `Ladder`; wire `IngestionService` via `Depends`; depends on T009, T017
- [X] T019 [US1] Write BDD step implementations in `tests/steps/ingest_ladder_steps.py` â€” implement all `@given`, `@when`, `@then` steps for the four US1 scenarios in `ingest_ladder.feature`; use `app_client` fixture; verify HTTP status, response JSON shape, presence of `_links.download`, and stored XLSX row counts via `pandas.read_excel`; run `pytest tests/features/ingest_ladder.feature -m us1` to confirm all green

**Checkpoint**: US1 complete â€” POST ingestion fully functional and BDD-tested independently.

---

## Phase 4: User Story 2 â€” Retrieve Position Ladder (Priority: P2)

**Goal**: Return a JSON summary of a stored ladder; provide XLSX binary via download endpoint.

**Independent Test**: After ingesting, `GET /v1/accounts/test-portfolio/ladder` â†’ 200 with summary JSON + `_links`; `GET /v1/accounts/test-portfolio/ladder/download` â†’ 200 binary XLSX with correct Content-Disposition.

### Tests for User Story 2 âš ï¸ Write and verify FAILING before implementing

- [X] T020 [P] [US2] Write Gherkin feature file `tests/features/retrieve_ladder.feature` with US2 scenarios from spec: "Retrieve summary of an existing position ladder" (200, JSON summary, `_links.self` and `_links.download` present), "Retrieve a ladder for an unknown account" (404); add `@us2` tag; add scenario "Download XLSX binary for a known account" (200, content-type header)

### Implementation for User Story 2

- [X] T021 [US2] Add `GET /v1/accounts/{account_name}/ladder` handler to `app/api/ladder.py` â€” validate account name; call `LadderRepository.read_meta()`; raise `AccountNotFoundError` if not found; return `LadderSummary` populated from `AccountMeta` with `_links.self` and `_links.download`; depends on T018 (same router file)
- [X] T022 [US2] Add `GET /v1/accounts/{account_name}/ladder/download` handler to `app/api/ladder.py` â€” validate account name; call `LadderRepository.read_xlsx()` to get path; raise `AccountNotFoundError` if not found; return `FileResponse` with `media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"` and `Content-Disposition: attachment; filename="{account_name}-ladder.xlsx"`; depends on T021
- [X] T023 [US2] Write BDD step implementations in `tests/steps/retrieve_ladder_steps.py` â€” implement all steps for `retrieve_ladder.feature`; verify JSON summary fields (row_count, from_date, to_date, sub_accounts), `_links` presence, 404 body, and XLSX Content-Disposition header; run `pytest tests/features/retrieve_ladder.feature` to confirm all green

**Checkpoint**: US2 complete â€” retrieval and download endpoints independently tested.

---

## Phase 5: User Story 3 â€” Idempotent Re-submission (Priority: P2)

**Goal**: Re-submitting the same file for an existing account returns 200 with `status: unchanged`; no reprocessing; stored XLSX unchanged.

**Independent Test**: Ingest a file; record stored XLSX mtime; re-submit same file; verify 200 `status: unchanged`, mtime unchanged, same `_links.download`.

**Note**: The idempotent path is already implemented in `IngestionService` (T017). This phase adds Gherkin coverage and step wiring only.

### Tests for User Story 3 âš ï¸ Write and verify FAILING before implementing

- [X] T024 [P] [US3] Add Gherkin scenario `@us3` "Re-submitting the same file is a no-op" to `tests/features/ingest_ladder.feature` â€” matches scenario from spec exactly; verify `status: unchanged` and `_links.download` present

### Implementation for User Story 3

- [X] T025 [US3] Add step implementations for US3 scenario to `tests/steps/ingest_ladder_steps.py` â€” reuse existing `when` steps; add `then` steps for `status == "unchanged"`, stored file mtime unchanged, `_links.download` present; run `pytest tests/features/ingest_ladder.feature -m us3` to confirm green

**Checkpoint**: US3 complete â€” idempotency verified via BDD.

---

## Phase 6: User Story 4 â€” Merge Not Supported (Priority: P3)

**Goal**: Submitting a changed file for an existing account returns 409 with a clear error message; existing stored ladder is untouched.

**Independent Test**: Ingest file A; re-submit file B (same account); verify 409 body contains `merge-not-supported` type; `data/test-portfolio/ladder.xlsx` is unchanged.

**Note**: The 409 conflict path is already implemented in `IngestionService` (T017). This phase adds Gherkin coverage and step wiring only.

### Tests for User Story 4 âš ï¸ Write and verify FAILING before implementing

- [X] T026 [US4] Add Gherkin scenario `@us4` "Submitting a changed file returns a merge-not-supported error" to `tests/features/ingest_ladder.feature` â€” matches spec scenario; verify 409, problem detail body, unchanged stored file

### Implementation for User Story 4

- [X] T027 [US4] Add step implementations for US4 scenario to `tests/steps/ingest_ladder_steps.py` â€” steps to submit a modified XLSX (add a data row to existing fixture); assert 409 response; assert `type` contains `merge-not-supported`; assert stored file unchanged (compare SHA-256 before and after); run `pytest tests/features/ingest_ladder.feature -m us4` to confirm green

**Checkpoint**: All user stories complete and independently tested.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Validation edge cases, code quality gates, and quickstart validation.

- [X] T028 [P] Write Gherkin scenarios in `tests/features/validation.feature` covering all edge cases from spec: invalid account name format, account name exceeds 64 chars, non-XLSX upload, XLSX missing required column, XLSX with non-numeric value in numeric column, XLSX with unparseable date, empty XLSX (no data rows), earliest date within 2 business days of today; tag each with `@validation`
- [X] T029 Write BDD step implementations in `tests/steps/validation_steps.py` for all `validation.feature` scenarios; assert correct HTTP status (422) and RFC 7807 `ProblemDetail` body with `type`, `title`, `status`, `detail`, `instance` fields; run `pytest tests/features/validation.feature` to confirm all green
- [X] T030 [P] Run `ruff check app/ tests/` and `ruff format app/ tests/`; fix all reported issues including any `D` (pydocstyle) violations â€” all public classes, functions, and methods in `app/` MUST have docstrings (Constitution III); run `mypy --strict app/`; resolve all type errors; confirm zero errors in all three checks before proceeding
- [X] T031 [P] Verify OpenAPI spec accuracy: start server (`uvicorn app.main:app --port 8001`), fetch `http://localhost:8001/openapi.json`, compare schema definitions against `contracts/openapi.yaml`; update `openapi.yaml` at project root if any discrepancies exist
- [X] T032 Run quickstart.md validation end-to-end: start server; execute each `curl` command from `specs/001-position-ladder-ingestion/quickstart.md`; confirm responses match documented examples; record any discrepancies and update quickstart.md
- [X] T033 Write performance smoke tests in `tests/unit/test_performance.py`: using `time.perf_counter`, time a `POST` of a synthetic 5,000-row ledger XLSX â€” assert completion within 10 s (SC-001); time idempotent re-submit of the same file â€” assert within 1 s (SC-002); time `POST` of an intentionally invalid schema file â€” assert rejection within 1 s (SC-003); generate the 5,000-row synthetic fixture programmatically using pandas; these are NOT BDD tests â€” plain pytest functions that call `app_client` directly

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies â€” start immediately; all tasks parallelisable
- **Foundational (Phase 2)**: Depends on Phase 1 completion â€” blocks all user stories
- **US1 (Phase 3)**: Depends on Phase 2 â€” MVP delivery point
- **US2 (Phase 4)**: Depends on Phase 2 â€” may start in parallel with US1 (different files until T018/T021 touch `ladder.py`)
- **US3 (Phase 5)**: Depends on US1 (T017 provides idempotency implementation)
- **US4 (Phase 6)**: Depends on US1 (T017 provides 409 path implementation)
- **Polish (Phase 7)**: Depends on all user story phases complete

### Within Phase 3 (US1) Dependencies

- T012, T013, T014 â†’ parallel (write tests first; no app code needed)
- T015, T016 â†’ parallel (independent modules; make T013 and T014 pass)
- T017 â†’ after T015, T016, T008
- T018 â†’ after T017, T009
- T019 â†’ after T018 (steps call app endpoints)

### Within Phase 4 (US2) Dependencies

- T020 â†’ parallel with US1 implementation (Gherkin only)
- T021 â†’ after T018 (same `ladder.py` file)
- T022 â†’ after T021
- T023 â†’ after T022

### Parallel Opportunities

```
Phase 1 parallel group: T002, T003, T004 (all can run simultaneously)

Phase 2 parallel group: T005, T006, T007, T008, T010, T011 (after T001)
  (T009/main.py is written last in Phase 2 as it imports all others)

Phase 3 test-writing group: T012, T013, T014 (all parallel)
Phase 3 implementation group: T015, T016 (parallel; both unblock T017)

Phase 4 test-writing: T020 (parallel with any Phase 3 implementation task)

Phase 7 parallel group: T028, T030, T031 (independent)
```

---

## Implementation Strategy

### MVP: User Story 1 Only

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL â€” blocks everything)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**:
   - `pytest tests/unit/ tests/features/ingest_ladder.feature -m us1`
   - `POST` a real ledger file via curl; verify stored XLSX in `data/`
5. Proceed to Phase 4 (US2) once US1 is green

### Incremental Delivery

1. Phase 1 + 2 â†’ Foundation ready
2. Phase 3 (US1) â†’ POST ingestion works end-to-end â†’ **demo-able MVP**
3. Phase 4 (US2) â†’ GET + download works â†’ consumers can retrieve stored ladder
4. Phase 5 (US3) â†’ idempotency verified with tests
5. Phase 6 (US4) â†’ conflict path covered
6. Phase 7 â†’ code quality gates pass, quickstart verified

---

## Notes

- `[P]` = parallelisable (different files, no blocking dependency)
- `[Story]` maps task to user story for traceability
- BDD test tasks MUST be written and verified to FAIL before implementation tasks begin
- Use `pytest -m us1` / `-m us2` etc. to run one story's tests in isolation (Gherkin `@usN` tags map to pytest marks â€” filter with `-m`, not `-k`)
- Commit after each checkpoint (end of each user story phase)
- `data/` and `logs/` are gitignored â€” never commit runtime artefacts
