---
description: "Task list for Account Performance Retrieval Endpoints feature"
---

# Tasks: Account Performance Retrieval Endpoints

**Input**: Design documents from `/specs/007-performance-endpoints/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/openapi.yaml ✅

**Tests**: Required — Constitution Principle I mandates TDD with BDD/Gherkin. Test tasks appear
before their corresponding implementation tasks in every phase.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

**⚠️ Story ordering note**: spec.md lists User Story 1 (Daily Portfolio Return) before User Story 2
(Retrieve Charting-Ready Performance Measures), both P1. User Story 1's own Independent Test is a
pure computation check with no HTTP surface of its own (there is no "get me just the daily
portfolio return" endpoint — it's an internal input to every measure), so it is fully satisfied by
Foundational's unit tests (T001). Its BDD acceptance-level coverage, however, can only be observed
through the `/performance` endpoint itself, which is what User Story 2 builds. This plan therefore
implements **User Story 2 before User Story 1's BDD phase** — the reverse of spec.md's listed
order — exactly as feature 006 did for its own US3/US4 (see that feature's tasks.md Phase 5 note
for precedent). This is recorded here rather than silently reordered.

**Revision note (post `/speckit-analyze`)**: This revision closes four coverage gaps and one
consistency nit found by analysis: FR-014 (no attribute / unsupported attribute rejection) and
FR-013 (unknown account / missing ladder rejection) had no test coverage at all for the
`/performance` endpoint (new T008/T009/T014 below); SC-002 (all five measures populate together
for a 5+-year account) and SC-003 (short-tenure trailing measures are all omitted together while
inception measures still populate) had no dedicated scenario (T005 and T017 extended below).
Docstring/type-annotation expectations are now stated explicitly on every implementation task
(T006, T007, T010, T011, T020), not just the Foundational ones.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to ([US1]–[US4])
- Exact file paths included in all descriptions

---

## Phase 1: Setup

**Purpose**: Project initialization and configuration scaffolding.

No tasks required. This feature introduces no new runtime dependency, no new `config.yaml`
section, and no new pytest marker — BDD scenarios reuse the existing `us1`–`us4`/`validation`
markers already registered in `pyproject.toml` (features 005/006), scoped per-file via
`scenarios(...)` in each new/extended steps module. Proceed directly to Phase 2.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The pure computation core — daily portfolio return aggregation and the five
performance-measure formulas — shared by every user story. Nothing in Phase 3 onward can be
implemented without these two modules existing.

**⚠️ CRITICAL**: All user story phases depend on this phase being fully complete.

- [X] T001 [P] Write failing unit tests in `tests/unit/test_daily_portfolio_return.py` for a
  `compute_daily_portfolio_return(ladder_df: pd.DataFrame, from_date: date, through_date: date) ->
  pd.DataFrame` function imported from `app/services/daily_portfolio_return.py` (fails at import
  until T002). Build small hand-built ladder DataFrames (columns: `date`, `sub_account`,
  `weighted_position_return`, plus placeholder values for any other columns the real ladder
  carries) and assert: `test_sums_weighted_position_return_across_positions_per_date()` (two
  sub-accounts on the same date, e.g. `0.011` and `-0.0045` — matching spec.md User Story 1's
  worked example — assert the returned `daily_return` for that date equals `0.0065`);
  `test_zero_fills_dates_with_no_ladder_rows_not_forward_fill()` (a ladder with a date gap between
  two recorded dates — assert the gap date's `daily_return` is exactly `0.0`, and explicitly assert
  it is NOT the previous date's non-zero value, positively ruling out a forward-fill
  implementation per research.md §2); `test_never_pads_before_ladders_earliest_date()` (assert the
  returned DataFrame's first row's `date` equals the given `from_date` exactly, never earlier —
  this is what makes FR-011's look-back cutoff correct in T003/T004); `test_extends_through_date_beyond_ladders_last_recorded_row_as_zero()`
  (a `through_date` later than the ladder's last recorded row — assert the trailing extra business
  days are present with `daily_return == 0.0`, consistent with `TimeSeriesService`'s
  forward-filled-`market_value`-implies-flat-price-implies-zero-return reasoning in research.md §2);
  `test_single_position_ladder_matches_that_positions_weighted_return()` (one sub-account only —
  `daily_return` equals that sub-account's own `weighted_position_return` for every date, sanity
  check for the groupby-sum reducing to identity with one group)

- [X] T002 Implement `app/services/daily_portfolio_return.py` —
  `compute_daily_portfolio_return(ladder_df: pd.DataFrame, from_date: date, through_date: date) ->
  pd.DataFrame`: `ladder_df.groupby("date", as_index=False)["weighted_position_return"].sum()`
  (long-format ladder, one row per (date, sub_account) — mirrors
  `TimeSeriesService.get_series()`'s `market_value` aggregation exactly), rename the summed column
  to `daily_return`; reindex over `pd.bdate_range(start=from_date, end=through_date)` and
  `.fillna(0.0)` (NOT `.ffill()` — per research.md §2, a date with no ladder rows sums to `0.0` by
  definition of "sum over an empty set", never a repeat of the prior day's return); return columns
  `["date", "daily_return"]` sorted by date; emit a `structlog` info event
  `daily_portfolio_return_complete` with `row_count` (Constitution IV); full type annotations,
  Google-style docstring; depends on T001; run `pytest tests/unit/test_daily_portfolio_return.py`
  to verify all tests pass

- [X] T003 [P] Write failing unit tests in `tests/unit/test_performance_metrics.py` for a
  `compute_performance_measures(daily_returns_df: pd.DataFrame) -> pd.DataFrame` function imported
  from `app/services/performance_metrics.py` (fails at import until T004), taking the
  `["date", "daily_return"]` output shape of T002. Build a hand-built `daily_return` series (e.g.
  a small constant or varying sequence long enough to exercise every window) and assert:
  `test_itd_is_expanding_cumulative_product_minus_one()` (assert `ITD` at each date equals
  `(1 + daily_return).expanding().apply(lambda w: w.prod()) - 1`, computed independently in the
  test via a plain Python loop, not by re-deriving pandas' own `.expanding()` call, to avoid a
  tautological test); `test_itd_is_zero_on_first_recorded_date()` (first row's `daily_return` is
  `0.0` — assert `ITD` and `"ITD (Ann.)"` on that row are both exactly `0.0`);
  `test_itd_annualized_uses_260_day_year_and_elapsed_row_count()` (assert
  `"ITD (Ann.)"` at row index `i` (0-indexed) equals `(1 + ITD[i]) ** (260 / (i + 1)) - 1`, per
  FR-007's "1-indexed row position since inception" elapsed-day count);
  `test_1y_is_rolling_260_day_cumulative_product_not_annualized()` (a series of at least 261 rows
  with a known pattern — assert `"1Y"` at the last row equals the cumulative product of
  `(1 + daily_return)` over exactly the trailing 260 rows, minus 1, with no power scaling applied);
  `test_3y_is_rolling_780_day_cumulative_product_annualized_by_one_third_power()` and
  `test_5y_is_rolling_1300_day_cumulative_product_annualized_by_one_fifth_power()` (same pattern,
   780/1300-row windows, each additionally raised to `1/3` or `1/5` power per FR-009);
  `test_trailing_measures_are_nan_before_enough_history_exists()` (**the core FR-011 mechanism** —
  a series shorter than 260 rows — assert `"1Y"` is `NaN` for every row of that series, and once
  the series reaches exactly 260 rows, assert the 260th row's `"1Y"` is a real number, not `NaN`;
  repeat conceptually for `"3Y"`/780 and `"5Y"`/1300 with appropriately sized fixtures — this
  documents that pandas `rolling(window=N)`'s default `min_periods=N` is what produces the
  "not yet computable" signal, with no custom look-back bookkeeping);
  `test_narrow_window_slice_matches_wide_window_computation_for_same_date()` (SC-004 — build one
  long `daily_return` series, compute `compute_performance_measures` once over the whole series,
  then again over a sliced-down copy that starts partway through — for any date present in the
  *narrower* input series where the window measures should still be `NaN` due to insufficient
  *input* history, confirm this differs correctly from the wide-input case where the same date has
  a real value; this is the regression guard for User Story 3's "look-back must use the full
  history, not just what's in the requested window" requirement — establishing why
  `PerformanceService`, not this module, is responsible for always passing the *full* history in)

- [X] T004 Implement `app/services/performance_metrics.py` —
  `compute_performance_measures(daily_returns_df: pd.DataFrame) -> pd.DataFrame`: input has columns
  `["date", "daily_return"]` (T002's output), sorted by `date`; `growth = 1 + daily_returns_df["daily_return"]`;
  `itd = growth.expanding().apply(lambda w: w.prod(), raw=True) - 1` (FR-006); `elapsed =
  pd.Series(range(1, len(growth) + 1))`; `itd_ann = (1 + itd) ** (260 / elapsed) - 1` (FR-007);
  `one_y = growth.rolling(window=260).apply(lambda w: w.prod(), raw=True) - 1` (FR-008, no
  annualization); `three_y_cumprod = growth.rolling(window=780).apply(lambda w: w.prod(), raw=True)`;
  `three_y = (three_y_cumprod) ** (1 / 3) - 1` (FR-009); `five_y_cumprod =
  growth.rolling(window=1300).apply(lambda w: w.prod(), raw=True)`; `five_y = (five_y_cumprod) **
  (1 / 5) - 1` (FR-009); assemble and return a DataFrame with columns
  `["date", "ITD", "ITD (Ann.)", "1Y", "3Y", "5Y"]` (literal display-label column names per
  research.md §7 — NOT snake_case), each rolling/expanding column left as `NaN` wherever pandas'
  own `min_periods` behaviour produces it (no manual NaN-filling or dropping here — that happens
  when `PerformanceService` builds response entries); full type annotations, Google-style
  docstring; depends on T003; run `pytest tests/unit/test_performance_metrics.py` to verify all
  tests pass

**Checkpoint**: Foundation complete — daily portfolio return aggregation and all five performance
formulas are implemented and unit-tested in isolation, with no dependency on any API surface.

---

## Phase 3: User Story 2 — Retrieve Charting-Ready Performance Measures for an Account (Priority: P1) 🎯 MVP

*(Implemented before User Story 1's BDD phase — see the ordering note above.)*

**Goal**: `GET /v1/accounts/{account_name}/performance` accepts the same arguments as
`GET /v1/accounts/{account_name}/timeseries` and returns a response in the same shape, carrying
`ITD`/`ITD (Ann.)`/`1Y`/`3Y`/`5Y` per business day — including correctly rejecting a request with
no attribute, an unsupported attribute, an unknown account, or a known account with no ingested
position ladder.

**Independent Test**: Request `ITD` and `1Y` for an account with more than a year of ingested
history over an explicit date range; verify one entry per business day, each carrying `ITD` and
(where enough history exists) `1Y`, using the same field names as the existing time series
response.

### Tests for User Story 2 ⚠️ Write and verify FAILING before implementing

- [X] T005 [P] [US2] Write Gherkin feature file `tests/features/retrieve_performance.feature` (new
  file — shared across US1, US2, and US3, mirroring how feature 006 shared one feature file across
  its first three stories) with a `Feature: Account Performance` header and three `@us2`
  scenarios: "Requesting performance measures returns a timeseries-shaped response" (ingest a
  ladder spanning 2020-01-02 through 2025-06-02, request
  `attribute=ITD&attribute=1Y&start=2025-01-02&end=2025-01-10`, assert `account_name`,
  `attributes == ["ITD", "1Y"]`, `from_date`/`to_date` match the requested range, one entry per
  business day each with a numeric `ITD` and `1Y`, and `_links` present); "Same request arguments
  and defaults as the existing timeseries endpoint" (no `start`/`end` supplied — assert the
  resolved range defaults exactly as `/timeseries` would: start = ladder's earliest date, end =
  business day before today); and, closing coverage gap E3/SC-002, "All five performance measures
  populate for an account with more than 5 years of history" (using the same 2020-01-02–onward
  ladder, request `attribute=ITD&attribute=ITD (Ann.)&attribute=1Y&attribute=3Y&attribute=5Y` for
  the account's most recent business day and assert every one of the five keys is present and
  numeric on that single entry — a request combining all five measures together is never exercised
  by the other two scenarios, each of which only requests a subset)

### Implementation for User Story 2

- [X] T006 [P] [US2] Implement `app/models/performance.py`: `PerformanceEntry(BaseModel)` with
  `model_config = ConfigDict(extra="allow")` and a single declared `date: date` field (mirrors
  `TimeSeriesEntry`); `PerformanceResponse(BaseModel)` with `model_config =
  ConfigDict(populate_by_name=True)` and fields `account_name: str`, `attributes: list[str]`,
  `from_date: date`, `to_date: date`, `entries: list[PerformanceEntry]`, `links: dict[str, str] =
  Field(alias="_links")` (mirrors `TimeSeriesResponse` field-for-field, per research.md §6 — a
  distinct class, not a reuse of `TimeSeriesResponse`); `PerformanceAttributeDefinition(BaseModel)`
  with `name: str`, `description: str`, `source: str` (mirrors `AttributeDefinition`);
  `PerformanceAttributeMetadataResponse(BaseModel)` with `model_config =
  ConfigDict(populate_by_name=True)`, `attributes: list[PerformanceAttributeDefinition]`, `links:
  dict[str, str] = Field(alias="_links")`; full `Field(description=...)` docstrings on every field
  matching `data-model.md`'s tables; full type annotations and a class-level Google-style docstring
  on each of the four classes, consistent with `app/models/timeseries.py`

- [X] T007 [P] [US2] Implement `app/services/performance_attributes.py`: `ATTRIBUTE_DEFINITIONS:
  list[PerformanceAttributeDefinition]` with exactly five entries named `"ITD"`, `"ITD (Ann.)"`,
  `"1Y"`, `"3Y"`, `"5Y"` (literal labels, matching `performance_metrics.py`'s column names exactly
  — per research.md §7), each `description` naming its formula in plain English (see
  `contracts/openapi.yaml`'s example payload for exact wording) and `source="position_ladder"` for
  all five; `SUPPORTED_ATTRIBUTES: frozenset[str] = frozenset(a.name for a in
  ATTRIBUTE_DEFINITIONS)`; `validate_attributes(attributes: list[str]) -> None` — raises
  `NoAttributesRequestedError()` if `attributes` is empty, else `UnsupportedAttributeError(requested=invalid,
  supported=sorted(SUPPORTED_ATTRIBUTES))` for any name outside `SUPPORTED_ATTRIBUTES` (mirrors
  `timeseries_attributes.py`'s `validate_attributes` line-for-line); full type annotations and a
  module/function-level Google-style docstring, consistent with `app/services/timeseries_attributes.py`

- [X] T008 [P] [US2] Closes coverage gaps E1 (FR-014) and E2 (FR-013) at the HTTP level: append
  four new `@validation` scenarios to the existing shared `tests/features/validation.feature`
  (reusing that file's established generic step vocabulary — `the validation response status is
  {status_code:d}` / `the response is a problem detail with type "{type_slug}"` — exactly as its
  existing timeseries/position scenarios already do): "Missing mandatory attribute is rejected for
  the performance endpoint" (`Given account "perf-missing-attr-val" has only a position ladder
  ingested for validation` / `When a performance request is made with no attribute for account
  "perf-missing-attr-val"` / `Then ... status is 422` / `... type "no-attributes-requested"`); "An
  unsupported attribute name is rejected for the performance endpoint" (same `Given`, `When a
  performance request is made for attribute "bogus_measure" for account
  "perf-unsupported-attr-val"` / `422` / `"unsupported-attribute"`); "Unknown account name is
  rejected for the performance endpoint" (no `Given` needed — a fresh account name has no ingested
  resource of any kind, mirroring `validation.feature`'s existing no-`Given` account-name-format
  scenarios — `When a performance request is made for attribute "ITD" for account
  "perf-unknown-val"` / `404` / `"account-not-found"`); "A known account without a position ladder
  is rejected for the performance endpoint" (`Given account "perf-capital-only-val" has an ingested
  capital ledger for validation` (the exact existing step at
  `tests/steps/validation_steps.py:344`) / `When a performance request is made for attribute "ITD"
  for account "perf-capital-only-val"` / `422` / `"missing-required-source"`); no code dependency,
  parallel with any other Phase 2/3 task

### Implementation for User Story 2 (continued)

- [X] T009 [US2] Write failing unit tests in `tests/unit/test_performance_service.py` for
  `PerformanceService` imported from `app/services/performance_service.py` (fails at import until
  T010). Using the same `tmp_path`-backed `LadderRepository` + `AccountsService` +
  `TimeseriesDateResolver` fixture pattern as `tests/unit/test_timeseries_service.py`, assert:
  `test_returns_populated_response_for_known_account()` (a written ladder with
  `weighted_position_return` values → `get_performance()` returns a `PerformanceResponse` with one
  entry per business day and the requested measure keys present where computable);
  `test_unknown_account_raises_account_not_found_error()` (no ladder or capital ledger written for
  this account name → `AccountNotFoundError`); `test_known_account_without_ladder_raises_missing_required_source_error()`
  (a capital-ledger-only account, written via `CapitalRepository` directly, requesting any
  performance attribute → `MissingRequiredSourceError` naming `source="position_ladder"`, mirroring
  `TimeSeriesService`'s dual-error logic per research.md §5); `test_date_resolution_matches_timeseries_date_resolver_defaults()`
  (no explicit `start`/`end` → resolved dates equal calling `TimeseriesDateResolver.resolve()`
  directly with the ladder's own `from_date` as the only required-source earliest date);
  `test_entry_omits_key_for_not_yet_computable_measure()` (request `"5Y"` on an account with under
  5 years of history → the early entries' dicts do not contain a `"5Y"` key at all, confirming the
  `NaN`-to-omitted-key translation, per FR-011 and the resolved Clarification); **closing coverage
  gap E1 at the unit level**: `test_no_attributes_raises_no_attributes_requested_error()` (calling
  `get_performance()` with `attributes=[]` → `NoAttributesRequestedError`, exercising
  `performance_attributes.validate_attributes()` through the service, mirroring
  `TimeSeriesService`'s own attribute-validation call) and
  `test_unsupported_attribute_raises_unsupported_attribute_error()` (calling `get_performance()`
  with `attributes=["bogus_measure"]` → `UnsupportedAttributeError` naming `"bogus_measure"` in
  `requested`)

- [X] T010 [US2] Implement `app/services/performance_service.py` — `PerformanceService.__init__(self,
  ladder_repo: LadderRepository, accounts_service: AccountsService, date_resolver:
  TimeseriesDateResolver) -> None` (no `capital_repo` — every performance measure requires only
  `position_ladder`, unlike `TimeSeriesService`); `get_performance(self, account_name: str,
  attributes: list[str], start: date | None, end: date | None, today: date) ->
  PerformanceResponse`: call `performance_attributes.validate_attributes(attributes)`; call
  `self._accounts_service.get_summary(account_name)`; if both `capital_ledger` and
  `position_ladder` are `None`, raise `AccountNotFoundError`; if `position_ladder` is `None` (but
  some other resource exists), raise `MissingRequiredSourceError(account_name=account_name,
  attribute=attributes[0], source="position_ladder")`; call `self._date_resolver.resolve(raw_start=start,
  raw_end=end, today=today, required_source_earliest_dates=[summary.position_ladder.from_date])`;
  if `resolved_start < summary.position_ladder.from_date`, raise `MissingRequiredSourceError` with
  an explanatory message (mirrors `TimeSeriesService`'s equivalent explicit check); read
  `ladder_df = self._ladder_repo.read_full_df(account_name)`; call
  `daily_portfolio_return.compute_daily_portfolio_return(ladder_df,
  from_date=summary.position_ladder.from_date, through_date=resolved_end)` (always the account's
  **entire** history through `resolved_end`, never just `[resolved_start, resolved_end]` — this is
  what makes the look-back "free", per research.md §1); call
  `performance_metrics.compute_performance_measures(daily_returns_df)`; slice the result to rows
  where `resolved_start <= date <= resolved_end`; for each row, build a `dict` of
  `{attr: float(row[attr]) for attr in attributes if pd.notna(row[attr])}` (the `pd.notna` filter
  is FR-011's key-omission mechanism) and construct `PerformanceEntry(date=row["date"], **values)`;
  emit a `structlog` info event `performance_request` (account_name, attributes, resolved dates,
  row_count), mirroring `TimeSeriesService.get_series()`'s `timeseries_request` event; return
  `PerformanceResponse(account_name=account_name, attributes=attributes, from_date=resolved_start,
  to_date=resolved_end, entries=entries, _links={"self": f"/v1/accounts/{account_name}/performance",
  "attributes": "/v1/performance/attributes", "accounts": "/v1/accounts"})`; full type annotations
  and a Google-style docstring on the class and `get_performance()`; depends on T002, T004, T006,
  T007, T009

- [X] T011 [US2] Implement `app/api/performance.py`: `router = APIRouter(prefix="/v1",
  tags=["Performance"])`; `_get_performance_service(ladder_repo: LadderRepository =
  Depends(get_ladder_repository), capital_repo: CapitalRepository =
  Depends(get_capital_repository)) -> PerformanceService` dependency function (constructs
  `AccountsService(ladder_repo=ladder_repo, capital_repo=capital_repo)` and
  `TimeseriesDateResolver()` internally, mirrors `timeseries.py`'s `_get_timeseries_service`);
  `GET /accounts/{account_name}/performance` route handler with `account_name: str` path param,
  `attribute: list[str] = Query(default_factory=list, ...)`, `start: date | None = Query(default=None)`,
  `end: date | None = Query(default=None)`, `service: PerformanceService =
  Depends(_get_performance_service)`; call `validate_account_name(account_name)`, then
  `service.get_performance(account_name=account_name, attributes=attribute, start=start, end=end,
  today=date.today())`, return `JSONResponse(status_code=200,
  content=response.model_dump(by_alias=True, mode="json"))` (mirrors
  `get_account_timeseries` in `app/api/timeseries.py` exactly); full type annotations and
  Google-style docstrings on the dependency function and route handler; leave the
  `/performance/attributes` route for T020 (Phase 6) — do not add it here; depends on T010

- [X] T012 [US2] Modify `app/main.py`: add `performance` to the `from app.api import ...` line;
  add `app.include_router(performance.router)` alongside the other routers; no new exception
  handler needed (`AccountNotFoundError`, `MissingRequiredSourceError`,
  `NoAttributesRequestedError`, `UnsupportedAttributeError`, `FutureEndDateError`,
  `InvalidDateRangeError` are all already registered); depends on T011

- [X] T013 [US2] Write BDD step implementations in `tests/steps/retrieve_performance_steps.py` for
  the three `@us2` scenarios from T005: reuse the `_ladder_bytes`/ingestion-helper pattern from
  `tests/steps/retrieve_timeseries_steps.py` (define locally in this new file), building a ladder
  with `fake_market_data_service.configure_prices(...)` varying prices across enough business days
  to span 2020-01-02 through 2025-06-02; issue `GET
  /v1/accounts/{account}/performance?attribute=...` requests via `app_client`; assert response
  shape (`account_name`, `attributes`, `from_date`, `to_date`, one entry per business day,
  `_links`), the no-args default-date-range scenario, and the all-five-measures scenario (E3); run
  `pytest tests/features/retrieve_performance.feature -m us2` to confirm all green; depends on T005,
  T012

- [X] T014 [US2] Write BDD step implementations in `tests/steps/validation_steps.py` for the four
  new `@validation` scenarios from T008: add a `@when(parsers.parse('a performance request is made
  for attribute "{attribute}" for account "{account_name}"'), target_fixture="val_response")` step
  and a `@when(parsers.parse('a performance request is made with no attribute for account
  "{account_name}"'), target_fixture="val_response")` step, each issuing a `GET
  /v1/accounts/{account_name}/performance` request via `app_client` (mirroring
  `request_timeseries_attribute`'s shape at `tests/steps/validation_steps.py:360`) — no new `Then`
  steps needed, both already-generic `check_val_status`/`check_problem_type` steps apply
  unchanged; run `pytest tests/features/validation.feature -m validation` to confirm all green
  (including the pre-existing scenarios, to guard against a regression from this file's edit);
  depends on T008, T012

**Checkpoint**: US2 complete — the performance endpoint is live and independently BDD-tested for
its core request/response contract, its all-five-measures happy path, and its four rejection
paths (MVP delivery point).

---

## Phase 4: User Story 1 — Daily Return Recorded for Every Priced Position (Priority: P1)

**Goal**: The account's daily portfolio return (the sum of `weighted_position_return` across every
position on a date) is what every performance measure is built from — verified both at the unit
level (Phase 2) and, now that the endpoint exists (Phase 3), at the acceptance level.

**Independent Test**: For an account with two or more positions active on the same business day,
verify the account's daily portfolio return for that day equals the sum of
`weighted_position_return` across every position present in that day's position ladder.

**Note**: `compute_daily_portfolio_return` (T002) is already fully implemented and unit-tested;
this phase adds the BDD acceptance-level scenario now that `/performance` (Phase 3) exists to
observe it through, mirroring the ordering note at the top of this file.

### Tests for User Story 1 ⚠️ Write and verify FAILING before implementing

- [X] T015 [P] [US1] Append a `@us1` scenario to `tests/features/retrieve_performance.feature`
  (same file as T005) adapted from spec.md's User Story 1: two sub-accounts present on the same
  date; rather than engineering exact input prices to hit an illustrative
  `0.011`/`-0.0045`-style figure through the full pricing+returns pipeline, use the downloaded
  ladder's own summed `weighted_position_return` for that date as the test oracle (mirrors feature
  006 research.md's precedent of deriving the expected value from the system's own output rather
  than hand-computing it); assert the performance endpoint's `ITD` value on the account's very
  first ingested date equals that same sum exactly (the first date's `ITD` is definitionally its
  single-day daily portfolio return, since a one-term cumulative product compounds to itself)

### Implementation for User Story 1

- [X] T016 [US1] Write BDD step implementations in `tests/steps/retrieve_performance_steps.py`
  (same file as T013) for the `@us1` scenario: after ingesting the two-sub-account ladder, download
  it via `GET /v1/accounts/{account}/ladder/download`, compute
  `expected = df[df["date"] == first_date]["weighted_position_return"].sum()` as the oracle,
  request `attribute=ITD` from `/performance` for that single date, and assert the returned `ITD`
  equals `expected` (`pytest.approx`); run `pytest tests/features/retrieve_performance.feature -m
  us1` to confirm green; depends on T015, T013 (same file)

**Checkpoint**: US1 complete — the daily portfolio return aggregation is independently verified at
both the unit level and, now, the full-stack acceptance level.

---

## Phase 5: User Story 3 — Trailing and Annualized Returns Look Back Beyond the Requested Window (Priority: P1)

**Goal**: A trailing measure (`1Y`/`3Y`/`5Y`) requested for a narrow date window still reflects the
full trailing period, reaching back before the requested `start` as needed; a measure is simply
absent from an entry where not enough history exists yet — and multiple not-yet-computable
measures are omitted together, consistently, while shorter-window measures on the same entry still
populate.

**Independent Test**: Request a `3Y` value for a single date where the account has at least 3
years of daily portfolio returns recorded strictly before that date but the request's `start`
equals the requested date; verify the returned `3Y` value still reflects the full trailing 3-year
window.

### Tests for User Story 3 ⚠️ Write and verify FAILING before implementing

- [X] T017 [P] [US3] Append three `@us3` scenarios to `tests/features/retrieve_performance.feature`:
  the two adapted verbatim from spec.md's User Story 3 — "3Y return for a narrow window still uses
  the full trailing history" (an account with continuous daily portfolio returns from 2019-01-01
  onward; request `attribute=3Y&start=2022-01-01&end=2022-01-01`; assert the single returned `3Y`
  value equals the same value obtained by requesting `attribute=3Y` with a wide window that also
  includes 2022-01-01 — the cross-check that makes the "used the full history, not just the
  requested window" assertion concrete without hand-deriving the exact cumulative product) and
  "Trailing return has no value before enough history exists" (an account whose first recorded
  daily portfolio return is 2021-06-01; request `attribute=3Y&start=2021-06-01&end=2021-06-01`;
  assert the entry for 2021-06-01 has no `"3Y"` key) — plus a third scenario closing coverage gap
  E4/SC-003, "Short-tenure trailing measures are omitted together while inception measures still
  populate": an account with continuous daily portfolio returns spanning between 1 and 3 years
  ending on its most recent date; request
  `attribute=ITD&attribute=ITD (Ann.)&attribute=1Y&attribute=3Y&attribute=5Y` for that most recent
  date; assert the single returned entry has numeric `ITD`, `"ITD (Ann.)"`, and `"1Y"` values, and
  has **neither** a `"3Y"` **nor** a `"5Y"` key (the earlier "no value" scenario only checked `3Y`
  in isolation and never confirmed `5Y`'s omission or the other three measures' simultaneous
  presence on the same entry)

### Implementation for User Story 3

- [X] T018 [US3] Write BDD step implementations in `tests/steps/retrieve_performance_steps.py`
  (same file as T013/T016) for the three `@us3` scenarios: issue the narrow-window and wide-window
  requests and compare the two `3Y` values for the shared date (`pytest.approx`); issue the
  insufficient-history request and assert the key is absent from the single returned entry's dict;
  issue the 1–3-year, all-five-attribute request and assert `ITD`/`"ITD (Ann.)"`/`"1Y"` are present
  and numeric while `"3Y"`/`"5Y"` are both absent from that same entry; run `pytest
  tests/features/retrieve_performance.feature -m us3` to confirm all green; depends on T017, T013/T016
  (same file)

**Checkpoint**: US3 complete — look-back-beyond-the-window is independently BDD-tested, including
an explicit regression guard against silently computing trailing measures only from in-window data,
and against only one of two simultaneously-omitted measures being checked.

---

## Phase 6: User Story 4 — Discover Available Performance Measures (Priority: P2)

**Goal**: `GET /v1/performance/attributes` lists all five measures with a description and source,
mirroring `GET /v1/timeseries/attributes`.

**Independent Test**: Call the performance metadata endpoint and verify it lists an entry for each
of `ITD`, `ITD (Ann.)`, `1Y`, `3Y`, and `5Y`, each with a description and a source.

### Tests for User Story 4 ⚠️ Write and verify FAILING before implementing

- [X] T019 [P] [US4] Write Gherkin feature file `tests/features/performance_attribute_metadata.feature`
  with a `Feature: Performance Attribute Metadata` header and one `@us4` scenario adapted from
  spec.md's User Story 4: "Performance attribute metadata lists all five measures" — request
  `/v1/performance/attributes`, assert exactly five entries named `ITD`, `"ITD (Ann.)"`, `1Y`,
  `3Y`, `5Y`, each with a non-empty description and a source, and that `_links.self` is present

### Implementation for User Story 4

- [X] T020 [US4] Modify `app/api/performance.py` (same file as T011): add a
  `GET /performance/attributes` route handler with no parameters, returning
  `JSONResponse(status_code=200, content=PerformanceAttributeMetadataResponse(
  attributes=performance_attributes.ATTRIBUTE_DEFINITIONS,
  _links={"self": "/v1/performance/attributes"}).model_dump(by_alias=True, mode="json"))` (mirrors
  `get_timeseries_attribute_metadata` in `app/api/timeseries.py` exactly); full type annotations
  and a Google-style docstring on the route handler; depends on T007, T011

- [X] T021 [US4] Write BDD step implementations in `tests/steps/performance_attribute_metadata_steps.py`
  for the `@us4` scenario from T019: request the endpoint via `app_client`, assert the five names,
  descriptions, sources, and `_links.self`; run `pytest
  tests/features/performance_attribute_metadata.feature -m us4` to confirm green; depends on T019,
  T020

**Checkpoint**: US4 complete — all four user stories are now independently functional and
BDD-tested.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Code quality gates, contract sync, and a full regression gate.

- [X] T022 [P] Run `ruff check app/ tests/` and `ruff format app/ tests/` on all new/changed files
  (`app/models/performance.py`, `app/services/daily_portfolio_return.py`,
  `app/services/performance_metrics.py`, `app/services/performance_attributes.py`,
  `app/services/performance_service.py`, `app/api/performance.py`, `app/main.py`,
  `tests/steps/validation_steps.py`, and all new test files); fix all reported issues including
  any `D` (pydocstyle) violations (Constitution III); run `mypy --strict app/`; resolve all type
  errors; confirm zero errors in all three checks

- [X] T023 [P] Verify OpenAPI spec accuracy: start the server, fetch
  `http://localhost:8000/openapi.json`, compare the `/accounts/{account_name}/performance` and
  `/performance/attributes` paths' shapes against
  `specs/007-performance-endpoints/contracts/openapi.yaml`; note the same pre-existing divergence
  documented in feature 006's tasks.md (the live route types `attribute` as plain `list[str]`,
  validated at the service layer, not via a Pydantic/FastAPI enum) applies here too — record it as
  an accepted, known gap rather than a regression to fix

- [X] T024 Run `quickstart.md` validation end-to-end: start the service, ingest (or reuse
  already-ingested) real return-enriched position ladder data, execute each documented `curl`
  command from `specs/007-performance-endpoints/quickstart.md`, confirm responses match the
  documented examples including the day-1-`ITD`-is-zero and narrow-vs-wide-window sanity checks,
  and record/fix any discrepancies in `quickstart.md`

- [X] T025 Run the full test suite (`pytest -q`) and confirm zero regressions against the
  pre-existing baseline (including the one already-documented pre-existing timing-flaky test noted
  in feature 004/005/006's tasks.md, `test_idempotent_resubmit_within_1_second`, which is unrelated
  to this feature)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No tasks — nothing to wait on
- **Foundational (Phase 2)**: Blocks all user stories. T001 → T002; T003 → T004 (both pairs
  test-first; T003/T004 do not depend on T001/T002 code-wise but are listed second for readability)
- **US2 (Phase 3)**: Depends on Phase 2 — MVP delivery point (implemented first — see ordering
  note at the top of this file)
- **US1 (Phase 4)**: Its unit-level Independent Test is already satisfied by Phase 2 (T001); this
  phase's BDD scenario additionally depends on Phase 3 (the endpoint must exist to observe it)
- **US3 (Phase 5)**: Depends on Phase 3 (same endpoint, same steps file)
- **US4 (Phase 6)**: Depends on Phase 3 (T007's registry, T011's router file both already exist)
- **Polish (Phase 7)**: Depends on all four user story phases being complete

### Within-Phase Dependencies

- T001 → T002; T003 → T004 (both test-first pairs, independent of each other, so [P] across pairs)
- T005 [P] with T001–T004, T006, T007, T008 (no code dependency — pure Gherkin authoring); T006
  [P] with T007 and T008 (different files); T008 [P] with T005/T006/T007 (different file, no code
  dependency); T009 → T002, T004, T006, T007; T010 → T009; T011 → T010; T012 → T011; T013 → T005,
  T012; T014 → T008, T012
- T015 [P] with any Phase 3 task (no code dependency); T016 → T015, T013 (same steps file)
- T017 [P] with any earlier phase; T018 → T017, T013/T016 (same steps file)
- T019 [P] with any earlier phase; T020 → T007, T011; T021 → T019, T020

### Parallel Opportunities

```
Phase 2: T001 → T002 (sequential); T003 → T004 (sequential); the two pairs are mutually parallel

Phase 3 test-writing: T005, T008 (parallel with T001–T004, T006, T007, and each other — no code
  dependency)
Phase 3 models/registry: T006, T007 (independent files, fully parallel)
Phase 4 test-writing: T015 (parallel with any Phase 3 implementation task)
Phase 5 test-writing: T017 (parallel with any earlier phase)
Phase 6 test-writing: T019 (parallel with any earlier phase)

T013, T016, T018 all touch tests/steps/retrieve_performance_steps.py (same file) — sequence them
in order (T013 → T016 → T018) even though they belong to different story phases

T014 touches tests/steps/validation_steps.py (a file shared with prior features' scenarios) — no
ordering conflict with T013/T016/T018 (different file), but run the full validation.feature suite
(not just the new scenarios) after T014 to guard against a regression in the pre-existing content

Phase 7 parallel group: T022, T023 (independent); T024 and T025 are sequential final gates
```

---

## Parallel Example: User Story 2 (MVP)

```bash
# Phase 2 must complete first (T001 → T002, T003 → T004, in either order relative to each other).
# Then, in parallel:
Task: "Write Gherkin feature file tests/features/retrieve_performance.feature with @us2 scenarios"
Task: "Append four @validation scenarios to tests/features/validation.feature"
Task: "Implement app/models/performance.py"
Task: "Implement app/services/performance_attributes.py"
# ...then sequentially: T009 → T010 → T011 → T012 → T013/T014
```

---

## Implementation Strategy

### MVP: User Story 2 Only

1. Complete Phase 2: Foundational (CRITICAL — blocks everything; Phase 1 has no tasks)
2. Complete Phase 3: User Story 2
3. **STOP and VALIDATE**:
   - `pytest tests/unit/test_daily_portfolio_return.py tests/unit/test_performance_metrics.py tests/unit/test_performance_service.py tests/features/retrieve_performance.feature -m us2 tests/features/validation.feature -m validation`
   - `curl` the live endpoint against a real ingested account; confirm the response shape matches
     `/timeseries`'s pattern by hand
4. Proceed to Phase 4 (US1), Phase 5 (US3), then Phase 6 (US4) — see the ordering note at the top
   of this file for why US1 (P1, listed first in spec.md) is implemented third here

### Incremental Delivery

1. Phase 2 → Foundation ready (daily return aggregation + all five formulas exist and are
   unit-tested)
2. Phase 3 (US2) → the endpoint works end-to-end, including its rejection paths and its
   all-five-measures happy path → **demo-able MVP**
3. Phase 4 (US1) → daily portfolio return aggregation additionally verified at the acceptance level
4. Phase 5 (US3) → look-back-beyond-the-window independently regression-tested, including the
   combined-omission case
5. Phase 6 (US4) → the metadata endpoint documents all five measures
6. Phase 7 → code quality gates pass, OpenAPI/quickstart verified, full-suite regression gate
   passes

### Parallel Team Strategy

With multiple developers:

1. Team completes Phase 2 together (two short, independent test-first pairs)
2. Once Phase 2 is done:
   - Developer A: Phase 3 (US2) → then Phase 4 (US1) → then Phase 5 (US3), since all three touch
     `tests/steps/retrieve_performance_steps.py` sequentially
   - Developer B: T008/T014 (the `validation.feature` additions) and Phase 6 (US4) in parallel —
     T014 needs T012 (Developer A's router registration); T020 needs T007 and T011
3. Developer B waits for T011/T012 (Developer A's Phase 3) before starting T014/T020

---

## Notes

- `[P]` = parallelisable (different files, no blocking dependency)
- `[Story]` maps task to user story for traceability
- BDD test tasks MUST be written and verified to FAIL before implementation tasks begin
- Use `pytest -m us1` / `-m us2` / `-m us3` / `-m us4` / `-m validation` to run one story's (or the
  shared validation suite's) tests in isolation; the `us1`–`us4`/`validation` markers registered in
  `pyproject.toml` (features 005/006) are reused here — no new marker registration needed
- Commit after each checkpoint (end of each user story phase)
- `data/` and `logs/` remain gitignored — never commit runtime artefacts
- This feature makes **zero** additional market-data-service calls and introduces **zero** new
  persisted storage — every value is computed at request time from the already-stored position
  ladder (plan.md, research.md §1)
- User Story 1 is the one place this feature's task order deliberately departs from spec.md's
  listed order (US1 before US2, both P1): its own BDD acceptance scenario exercises the
  `/performance` endpoint that User Story 2 builds. This is called out explicitly (the ordering
  note at the top of this file, and again in Phase 4) rather than silently resolved
- T002's zero-fill (not forward-fill) of gap dates and T004's reliance on pandas `rolling`'s
  default `min_periods` for the NaN-omission mechanism are the two most important design choices in
  this feature (research.md §2–3) — they are what make "look back as far as needed" and "omit a
  not-yet-computable measure" fall out of the formulas themselves rather than requiring separate
  bookkeeping. T003's `test_trailing_measures_are_nan_before_enough_history_exists` and T001's
  `test_never_pads_before_ladders_earliest_date` are the permanent regression guards for these two
  choices and MUST NOT be weakened or removed
- T008/T009/T014 exist specifically to close two coverage gaps (`/speckit-analyze` findings E1/E2)
  that would otherwise leave FR-013 and FR-014's rejection behaviour completely untested at the
  HTTP level for this endpoint, despite being explicitly called out in spec.md's Edge Cases and
  tested for the sibling `/timeseries` endpoint. T005's third scenario and T017's third scenario
  close the equivalent gaps for SC-002/SC-003 (findings E3/E4). None of these four additions
  should be removed or skipped without re-confirming the corresponding FR/SC is covered elsewhere
