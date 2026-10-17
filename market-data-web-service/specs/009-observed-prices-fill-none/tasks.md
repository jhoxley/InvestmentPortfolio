# Tasks: Observed-Only Price History (`fill=none`)

**Input**: Design documents from `specs/009-observed-prices-fill-none/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/openapi-changes.md, quickstart.md
**Branch**: `026-mds-observed-prices-fill-none`

**Tests**: BDD Gherkin `.feature` files and their step definitions are MANDATORY per the project constitution (Principle III). They MUST be written and confirmed failing before any implementation task in the same user story begins. Additional unit tests are optional.

**Organization**: Tasks are grouped by user story. US1, US2 and US3 are mutually independent and can be built in parallel by different people. US4 and US5 are `fill=none` variants and therefore depend on US1 — this is stated explicitly rather than claimed away.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1–US5)
- Exact file paths are given in every task

## Path Conventions

Single FastAPI project. Production code under `app/`, tests under `tests/` (`tests/features/` for Gherkin, `tests/steps/` for step definitions, `tests/fixtures/` for data). Contract at `openapi.yaml` in the repository root. All paths are relative to `market-data-web-service/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Establish the baseline that "`fill=all` is unchanged" (SC-003) will later be measured against. The project is already initialised, linted and logging-configured, so there is nothing to scaffold.

- [X] T001 Run the full baseline and record the results in `specs/009-observed-prices-fill-none/baseline.md`: `.venv\Scripts\python -m pytest` (record passed/failed counts and the scenario total), `.venv\Scripts\python -m ruff check .`, `.venv\Scripts\python -m mypy app`. This file is the reference for the SC-003 regression check in T040.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The OpenAPI contract is the authoritative source of truth and MUST be written before any implementation (constitution VI). Both edits touch `openapi.yaml`, so they are sequential, not parallel.

**⚠️ CRITICAL**: No user story implementation task may begin until this phase is complete.

- [X] T002 In `openapi.yaml`, add the `FillMode` named schema component (`type: string`, `enum: [all, none]`) to `components.schemas`, and add the `fill` query parameter to `GET /securities/{ticker}/history` referencing it with `default: all`, per `specs/009-observed-prices-fill-none/contracts/openapi-changes.md` §1. Inline anonymous enums are prohibited by constitution VI.
- [X] T003 In `openapi.yaml`, add the nullable `first_observed_date` and `last_observed_date` properties to `components.schemas.PriceHistoryResponse` **without** extending its `required` list, replace the `200` and `404` descriptions on `GET /securities/{ticker}/history`, and bump `info.version` from `0.1.2` to `0.1.3`, per `contracts/openapi-changes.md` §2–§4. Verify the file still parses as valid OpenAPI.

**Checkpoint**: Contract published. User story work can now begin — US1, US2 and US3 in parallel if staffed.

---

## Phase 3: User Story 1 - Observed-Only Price History for Risk Calculations (Priority: P1) 🎯 MVP

**Goal**: `GET /securities/{ticker}/history?fill=none` returns only dates with a real observation; `fill=all` and the no-parameter default stay exactly as they are today.

**Independent Test**: Request a range containing a mid-week market holiday with `fill=none` and assert the holiday date is absent while every trading date is present with its own price; request the same range with no `fill` parameter and assert the holiday entry is present carrying the prior price.

### BDD Scenarios for User Story 1 (MANDATORY — write and confirm failing FIRST) ⚠️

> **MUST fail before any implementation task below begins (Red-Green-Refactor)**

- [X] T004 [P] [US1] Write the Gherkin feature file covering all 7 US1 scenarios from `spec.md` in `tests/features/observed_only_history.feature`: mid-series gap omitted, no back-fill before first observation, no forward-fill of a stale end of range, default unchanged, explicit `fill=all` identical to default, invalid `fill` value rejected with 422, and every returned date traceable to a real observation.
- [X] T005 [US1] Implement step definitions for all 7 scenarios in `tests/steps/observed_only_history_steps.py`, driving the endpoint through the existing `client_with_cache` fixture and `mock_inner_provider` pattern from `tests/steps/cache_full_hit_steps.py`. Run them and **confirm RED** — a `fill=none` request currently returns the gap-filled series, so the assertions must fail rather than error.

### Implementation for User Story 1

- [X] T006 [P] [US1] Create the `FillMode` string enum (`ALL = "all"`, `NONE = "none"`) in `app/models/fill.py` as an `enum.StrEnum`, per `data-model.md` § FillMode.
- [X] T007 [P] [US1] Create `app/services/series_fill.py` with the `SeriesFiller` Protocol (`fill(observations, from_date, to_date) -> list[tuple[date, float]]`), the `ObservedOnlyFiller` implementation (de-duplicate by date keeping the last value, sort ascending, keep only `from_date <= d <= to_date`, manufacture no dates, retain weekend-dated observations), and `FillStrategyResolver.resolve(mode) -> SeriesFiller`. Do **not** modify `app/services/gap_fill.py` — its existing `fill` signature already satisfies the protocol structurally.
- [X] T008 [US1] Modify `app/services/pricing_service.py`: accept a `FillStrategyResolver` in `PricingService.__init__`, add a `fill: FillMode = FillMode.ALL` parameter to `get_price_history`, replace the direct `self._gap_fill.fill(...)` call with the resolved strategy, and raise `DataNotFoundError(ticker)` when the post-fill series is empty (FR-009 — see the Behaviour Change note in `plan.md`; this also closes the existing 200-with-empty-`prices` gap for `fill=all`). Depends on T006, T007.
- [X] T009 [US1] Update **every** `PricingService(...)` construction in the test suite to pass the new resolver — the four fixtures in `tests/conftest.py` (`client_with_cache`, `client_with_fx`, `client_with_gap_fill`, `client_with_fallback`) **and** the 7 further sites inside 8 step files (`local_price_fallback_current_steps.py` ×2, `local_price_fallback_edge_steps.py`, `local_price_fallback_fx_steps.py`, `local_price_fallback_history_steps.py` ×2, `local_price_fallback_zero_price_steps.py`, `pence_normalisation_current_steps.py`, `pence_normalisation_fx_steps.py`, `pence_normalisation_history_steps.py`), which build the service directly rather than via a fixture. 11 sites in total. Must land together with T008, which changes a constructor they all call. *(Scope corrected during implementation: the original task named only conftest, which left 22 tests erroring.)*
- [X] T010 [US1] Modify `app/api/securities.py`: add `fill: FillMode = Query(default=FillMode.ALL)` to `get_price_history`, pass it to `service.get_price_history(...)`, and construct `FillStrategyResolver(GapFillService(), ObservedOnlyFiller())` inside the `get_pricing_service` factory. Typing the parameter as the enum makes FastAPI return a 422 naming `fill` during request parsing, before any data-source call (FR-004) — do not hand-write a validator.
- [X] T011 [US1] Add a structured `observed_only_applied` structlog event in `app/services/series_fill.py` carrying `from_date`, `to_date`, `raw_observations` and `returned_count`, mirroring the existing `gap_fill_applied` event in `app/services/gap_fill.py` (constitution V).
- [X] T012 [US1] Run `.venv\Scripts\python -m pytest` and confirm all 7 US1 scenarios are GREEN **and** every pre-existing test still passes against the T001 baseline — this is the primary evidence for SC-003.
- [X] T012a [US1] Add a scenario to `tests/features/observed_only_history.feature` and its step definition asserting FR-010: supplying `fill=none` to `GET /securities/{ticker}/price` and to `GET /fx/{pair}/history` leaves both responses byte-identical to the same request without the parameter. Unrecognised query parameters are ignored by the existing service, so "unchanged" means no effect — not rejection.

**Checkpoint**: `fill=none` works end to end and `fill=all` is provably unchanged. This is a shippable MVP on its own.

---

## Phase 4: User Story 2 - Known Observation Window Reported on Every Response (Priority: P2)

**Goal**: Every successful history response reports `first_observed_date` and `last_observed_date` for the instrument, in both fill modes, independent of the requested range.

**Independent Test**: Request a narrow range in the middle of an instrument's history and assert the reported first observed date is earlier than the requested start and the last is later than the requested end — in both fill modes. Requires no part of US1 beyond the default mode that already exists.

### BDD Scenarios for User Story 2 (MANDATORY — write and confirm failing FIRST) ⚠️

- [X] T013 [P] [US2] Write the Gherkin feature file covering all 7 US2 scenarios from `spec.md` in `tests/features/observation_window.feature`: window reported in observed-only mode, window reported in default mode, window reflects the instrument not the requested range, window widens after a request extends the known history, window reported for a local-only fallback instrument, window reported when the fallback file was triggered by an empty primary source (FR-017 — the case a configuration-flag-keyed implementation gets wrong), and existing response fields unchanged by the additive window fields (FR-016 — assert the pre-existing response keys and `PricePoint` field set are untouched).
- [X] T014 [US2] Implement step definitions for all 7 scenarios in `tests/steps/observation_window_steps.py`, asserting on the two new response fields. Run and **confirm RED** — the fields do not yet exist on the response.

### Implementation for User Story 2

- [X] T015 [P] [US2] Create `app/providers/observation_window.py` with the frozen `ObservationWindow` dataclass (`first_observed_date`, `last_observed_date`) and the `@runtime_checkable` `ObservationWindowSource` Protocol (`observation_window(ticker) -> ObservationWindow | None`), per `data-model.md`. Do **not** add this method to the `PricingProvider` ABC in `app/providers/__init__.py` — `YFinanceProvider` cannot answer it and every `MagicMock(spec=PricingProvider)` fixture would break.
- [X] T016 [P] [US2] Add the nullable `first_observed_date: date | None = None` and `last_observed_date: date | None = None` fields to `PriceHistoryResponse` in `app/models/pricing.py`, matching the contract from T003. Leave all existing fields and `PricePoint` untouched (FR-016).
- [X] T017 [US2] Implement `observation_window` on `CachedPricingProvider` in `app/providers/cached_provider.py`, deriving the window from the first and last row of the ticker's cache CSV via `CacheRepository.read`, returning `None` when no cache file exists.
- [X] T018 [P] [US2] Implement `observation_window` on `LocalPricingProvider` in `app/providers/local_provider.py` (first and last row of the configured fallback CSV) and on `FallbackPricingProvider` in `app/providers/fallback_provider.py`, returning the local file's window **whenever the local file served the request** — both for a `use_local_only` entry and for an entry whose file was used because the primary source returned no observations — and delegating to the inner provider only when the primary source supplied the prices. Keying this off `use_local_only` alone returns `None` for the fallback-triggered case, where the CSV supplied the data but no cache file exists to read a window from, breaking FR-017.
- [X] T019 [US2] Modify `app/services/pricing_service.py` to query the window **after** calling `get_price_history` (so a cache write performed during a partial-hit fetch is already reflected, satisfying FR-015 with no extra bookkeeping), falling back to deriving the extremes from the raw series just returned when the provider does not implement `ObservationWindowSource`, and populate the two response fields. Depends on T015, T016.
- [X] T020 [US2] Modify `CurrencyService.build_translated_history` in `app/services/currency_service.py` to copy `first_observed_date` and `last_observed_date` into the `PriceHistoryResponse` it constructs. It currently rebuilds the model from scratch and would silently drop them on any currency-converted request.
- [X] T021 [US2] Run the suite and confirm all 5 US2 scenarios are GREEN with no regression against the T001 baseline.

**Checkpoint**: Both new fields populated on every successful response, including currency-converted ones.

---

## Phase 5: User Story 3 - Remember That No History Exists Before the Earliest Observation (Priority: P2)

**Goal**: A repeated long-lookback request stops re-fetching a known-empty pre-history segment, the memory is invalidated when earlier data appears, and all three events are visible in the logs.

**Independent Test**: With the data source instrumented, request a range starting before an instrument's earliest observation twice and assert the source is called for the earlier segment on the first request only, with `cache_no_earlier_data_*` events in the log. Touches neither the fill mode nor the window fields.

### BDD Scenarios for User Story 3 (MANDATORY — write and confirm failing FIRST) ⚠️

- [X] T022 [P] [US3] Write the Gherkin feature file covering all 8 US3 scenarios from `spec.md` in `tests/features/cache_no_earlier_data.feature`: empty earlier segment fetched once then remembered, an even earlier request also served without a call, skip visible in logs, recording visible in logs, memory invalidated when earlier data is discovered, the remembered segment not suppressing a later-segment fetch, boundary recorded on the first request before any history is stored (FR-027), and a data source outage never recorded as absence of data (FR-028).
- [X] T023 [US3] Implement step definitions for all 8 scenarios in `tests/steps/cache_no_earlier_data_steps.py`, using the `mock_inner_provider` call-count pattern from `tests/steps/cache_partial_hit_steps.py` for the "not called" assertions and `structlog.testing.capture_logs` for the log assertions. Run and **confirm RED** — the earlier segment is currently re-fetched on every request.

### Implementation for User Story 3

- [X] T024 [US3] Add sidecar persistence to `CacheRepository` in `app/cache/repository.py`: `read_no_data_before(ticker) -> date | None`, `write_no_data_before(ticker, d)` and `clear_no_data_before(ticker)`, backed by `{sanitised-ticker}.meta.json` (`{"no_data_before": "YYYY-MM-DD"}`) written atomically via temp file + `os.replace`, reusing `_filename`'s existing sanitisation. Treat a missing or unparsable sidecar as "no boundary known", logging a WARNING for the unparsable case as `read` already does. Extend `delete` to remove the sidecar with the CSV, and extend `delete_all` to glob `*.meta.json` as well as `*.csv` — the current `*.csv` glob will not match sidecars and would leave them orphaned (FR-023).
- [X] T025 [US3] Implement the boundary policy in `CachedPricingProvider.get_price_history` in `app/providers/cached_provider.py`, per the decision table in `plan.md` § Design 3: clear the boundary if the cache CSV holds a row earlier than it; skip the `before` fetch when a boundary exists and `boundary <= cached_min`; record `cached_min` when the `before` fetch returns empty; move the boundary to `min(before dates)` when it returns rows. Emit `cache_no_earlier_data_skip`, `cache_no_earlier_data_recorded` and `cache_no_earlier_data_invalidated`, each with `ticker` and the date boundary (FR-024). Guard the `before` segment only — never the `after` segment (FR-020). Depends on T024.
- [X] T026 [US3] Satisfy FR-027: extend `CachedPricingProvider._fetch_and_cache` in `app/providers/cached_provider.py` to record `no_data_before = first fetched date` when a cold-cache populate returns rows starting after the requested `from_date`. Without this, the saving does not arrive until the third request, because the first long-lookback request is the one that creates the cache file.
- [X] T027 [US3] Satisfy FR-028: ensure no boundary is written or modified when a fetch raises `ProviderUnavailableError`, and verify via the outage scenario in `tests/features/cache_no_earlier_data.feature` that the request returns 503, **no** sidecar file is written, and a subsequent successful fetch of earlier data is not suppressed. `_fetch_segment` already re-raises `ProviderUnavailableError` while swallowing `DataNotFoundError`, so the distinction exists — this makes it an asserted guarantee rather than an implementation accident.
- [X] T028 [US3] Run the suite and confirm all US3 scenarios are GREEN, with `tests/features/cache_partial_hit.feature` and `tests/features/cache_management.feature` still passing unchanged.
- [X] T028a [US3] Measure SC-006 against a running service: time two identical five-year-lookback requests for an instrument whose history is shorter than the window, and record both elapsed times in `specs/009-observed-prices-fill-none/baseline.md`. The second must be at most 50% of the first. Keep this out of the automated suite — a wall-clock assertion in CI would be flaky; the pass/fail record belongs with the baseline evidence.

**Checkpoint**: Repeat long-lookback requests make zero data-source calls for the pre-history segment, with a full log trail.

---

## Phase 6: User Story 4 - Observed-Only History from Local Fallback Files (Priority: P3)

**Goal**: `fill=none` on a locally-sourced instrument returns exactly the CSV's rows inside the requested range.

**Independent Test**: Configure a `use_local_only` fallback file with observations on a subset of business days plus rows outside the test range, request observed-only history, and assert the response contains exactly the in-range rows.

**Depends on**: US1 (T006–T010) — this story exercises the `fill=none` path on the fallback provider chain.

### BDD Scenarios for User Story 4 (MANDATORY — write and confirm failing FIRST) ⚠️

- [X] T029 [P] [US4] Create the test fixture `tests/fixtures/priv01_sparse.csv` with rows on a sparse subset of business days **plus at least one row before and one row after** the range the scenarios request, so the range clip is actually exercised.
- [X] T030 [P] [US4] Create the fallback config fixture `tests/fixtures/fallback_config_sparse.json` mapping a test identifier to `priv01_sparse.csv` with `use_local_only: true` and a `GBP` currency, following the shape of `tests/fixtures/fallback_config_local_only.json`.
- [X] T031 [US4] Write the Gherkin feature file covering all 3 US4 scenarios from `spec.md` in `tests/features/observed_only_fallback.feature` (raw rows in range, out-of-range rows excluded, default mode still gap-fills) and implement step definitions in `tests/steps/observed_only_fallback_steps.py` using a `client_with_fallback`-style fixture pointed at the new config. Run and **confirm RED**.

### Implementation for User Story 4

- [X] T032 [US4] Confirm `ObservedOnlyFiller`'s range clip (T007) correctly handles `LocalPricingProvider.get_price_history`, which ignores the requested range and returns **every** row in the CSV — today the clip is only an incidental side effect of `GapFillService`'s `from`→`to` loop. Extend `ObservedOnlyFiller` if the out-of-range scenario fails. Do **not** add clipping inside `LocalPricingProvider`: that would change the existing `fill=all` fallback responses, which FR-003 requires to stay identical.
- [X] T033 [US4] Run the suite and confirm all 3 US4 scenarios are GREEN with the existing `local_price_fallback_*` features still passing.

**Checkpoint**: Privately-tracked instruments honour observed-only mode identically to exchange-traded ones.

---

## Phase 7: User Story 5 - Currency-Converted Observed-Only History (Priority: P3)

**Goal**: An observed-only series requested in a target currency contains the same dates as the unconverted request, each converted at its own date's gap-filled FX rate.

**Independent Test**: Request observed-only history with `currency=GBP` for a security with observations on a subset of business days and assert the response contains only those dates, each with an `fx_rate` reflecting its own date.

**Depends on**: US1 (T006–T010). Research R6 predicts **no** algorithmic change is needed here — this story's job is to prove that.

### BDD Scenarios for User Story 5 (MANDATORY — write and confirm failing FIRST) ⚠️

- [X] T034 [P] [US5] Write the Gherkin feature file covering all 3 US5 scenarios from `spec.md` in `tests/features/observed_only_fx.feature`: observed prices converted at each observation's own date rate, a missing raw FX rate on an observation date not dropping the observation, and conversion not reintroducing non-observed dates.
- [X] T035 [US5] Implement step definitions for all 3 scenarios in `tests/steps/observed_only_fx_steps.py` using the `client_with_fx` fixture and `mock_fx_provider`, following `tests/steps/currency_translation_history_steps.py`. Run and **confirm RED**.

### Implementation for User Story 5

- [X] T036 [US5] Verify the US5 scenarios pass with **no** change to `app/services/currency_service.py` or `app/services/fx_aligner.py` beyond the field pass-through already made in T020: `translate_history` gap-fills the FX series then aligns it onto `[p.date for p in records]`, so an observed-only `records` list yields each observation at its own date's filled rate (FR-025) and cannot gain dates (FR-026). If any scenario is still red, fix it here and record why research R6 was wrong in `research.md`.
- [X] T037 [US5] Run the suite and confirm all 3 US5 scenarios are GREEN with the existing `currency_translation_*`, `gap_fill_fx_conversion` and `pence_normalisation_fx` features still passing.

**Checkpoint**: All five stories independently functional.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T038 Verify the hand-maintained `openapi.yaml` matches what FastAPI generates at `/openapi.json` for the changed path and schemas — specifically the `FillMode` enum values and the two new nullable date properties — and that Swagger UI at `/docs` renders `fill` as a dropdown with `all` preselected.
- [X] T039 Run `.venv\Scripts\python -m ruff check .` and `.venv\Scripts\python -m mypy app` and resolve every finding. Pay attention to `@runtime_checkable` Protocol narrowing in `app/services/pricing_service.py`, which needs explicit handling to stay clean under `mypy --strict`.
- [X] T040 Run the full suite and diff the result against `specs/009-observed-prices-fill-none/baseline.md` from T001: every pre-existing scenario must still pass, which is the evidence for SC-003.
- [X] T041 Walk through `specs/009-observed-prices-fill-none/quickstart.md` manually against a running service, including the sidecar inspection, the `DELETE /cache/{ticker}` invalidation check and the log-event greps.
- [X] T042 [P] Update `README.md` with the `fill` parameter, the two new response fields and the observed-versus-filled distinction, noting the Value-at-Risk consumer in `portfolio-analysis-service`.
- [X] T043 [P] Verify the empty-range 404 behaviour change is documented where consumers will see it — the `404` description in `openapi.yaml` (T003) and the README (T042) — since it is the one non-additive change in this feature.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup. **Blocks all user stories** (OpenAPI-First, constitution VI).
- **US1 (Phase 3)**, **US2 (Phase 4)**, **US3 (Phase 5)**: All depend only on Phase 2. Mutually independent — can run in parallel.
- **US4 (Phase 6)** and **US5 (Phase 7)**: Depend on US1 completing (they are `fill=none` variants). US4 and US5 are independent of each other.
- **Polish (Phase 8)**: Depends on all desired stories being complete.

### User Story Dependencies

```
Phase 2 (openapi.yaml)
   │
   ├──► US1 (P1, MVP) ──┬──► US4 (P3)
   │                    └──► US5 (P3)
   ├──► US2 (P2)
   └──► US3 (P2)
```

US2 is independent of US1 because the observation window applies in both fill modes. US3 is independent of both because the cache boundary is orthogonal to response shaping.

### Cross-Story File Contention

Three files are touched by more than one story. Sequence these, or expect a merge:

| File | Stories | Note |
|---|---|---|
| `app/providers/cached_provider.py` | US2 (T017), US3 (T025, T026) | Different methods; US2 adds `observation_window`, US3 edits `get_price_history`. |
| `app/services/pricing_service.py` | US1 (T008), US2 (T019) | US1 changes the constructor and fill resolution; US2 adds window population. |
| `openapi.yaml` | Phase 2 only (T002, T003) | Deliberately confined to Phase 2 so no story edits the contract. |

### Within Each User Story

- BDD feature file and step definitions first, confirmed RED, before any implementation task.
- Models and protocols before services; services before endpoints.
- Each story ends with a green-plus-no-regression task.

### Parallel Opportunities

- T002 and T003 are **not** parallel — both edit `openapi.yaml`.
- Once Phase 2 is done, US1, US2 and US3 can be worked simultaneously by three people.
- Within US1: T006 and T007 are parallel. T008 and T009 must land together.
- Within US2: T015, T016 and T018 are parallel; T017 and T019 follow.
- Within US4: T029 and T030 are parallel.
- Polish: T042 and T043 are parallel.

---

## Parallel Example: User Story 1

```bash
# After T004/T005 are RED, launch the two independent new files together:
Task: "Create FillMode StrEnum in app/models/fill.py"                                   # T006
Task: "Create SeriesFiller + ObservedOnlyFiller + FillStrategyResolver in app/services/series_fill.py"  # T007

# Then sequentially (shared constructor, then endpoint):
Task: "PricingService fill mode + empty→404 in app/services/pricing_service.py"          # T008
Task: "Update 4 PricingService constructions in tests/conftest.py"                       # T009
Task: "fill query param + resolver wiring in app/api/securities.py"                      # T010
```

## Parallel Example: Three Stories at Once

```bash
# Developer A — US1:  T004 → T005 (RED) → T006/T007 → T008/T009 → T010 → T011 → T012 → T012a
# Developer B — US2:  T013 → T014 (RED) → T015/T016/T018 → T017 → T019 → T020 → T021
# Developer C — US3:  T022 → T023 (RED) → T024 → T025 → T026 → T027 → T028 → T028a
# Coordinate on app/providers/cached_provider.py (B's T017 vs C's T025/T026)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1: baseline recorded (T001).
2. Phase 2: contract published (T002–T003).
3. Phase 3: US1 (T004–T012).
4. **STOP and VALIDATE**: `fill=none` returns observations only; the entire existing suite still passes.
5. Shippable — the Value-at-Risk consumer can start work against it, without the window fields.

### Incremental Delivery

1. Setup + Foundational → contract ready.
2. **US1** → observed-only prices → the VaR calculation becomes correct. **MVP.**
3. **US2** → window fields → the consumer can size its lookback and reject short-history securities.
4. **US3** → cache boundary → long-lookback requests stop re-fetching empty pre-history.
5. **US4** → fallback instruments honour observed-only mode.
6. **US5** → non-GBP holdings honour observed-only mode.
7. Polish → contract parity, quality gates, regression evidence, docs.

Each step adds value without breaking the previous one. US2 and US3 can be delivered in either order, or before US1 if the window fields or the performance saving are wanted first.

### Risk Notes

- **The one non-additive change** is the empty-range 404 (T008), carved out explicitly in FR-002. A grep of `tests/` found no assertion of a 200-with-empty-`prices` response, but T012 and T040 must confirm this rather than assume it.
- **`FallbackPricingProvider.observation_window` must key off which source served the request**, not off the `use_local_only` flag (T018). The flag-keyed version returns `None` for the fallback-triggered case and silently breaks FR-017 — and would appear to work, because `PricingService`'s raw-series fallback masks it for most inputs.
- **`delete_all`'s `*.csv` glob** (T024) is an easy miss that would silently orphan sidecars and break FR-023's invalidation guarantee.
- **Recording the boundary on the cold populate** (T026) is what makes US3 pay off on the second request instead of the third; skipping it makes the feature look ineffective in exactly the scenario that motivated it.
- **Do not touch `app/services/gap_fill.py`.** It is shared with the FX path, which must keep gap-filling in both modes (FR-025). Leaving it alone makes that guarantee structural.

---

## Task Summary

| Phase | Story | Tasks | Count |
|---|---|---|---|
| 1 Setup | — | T001 | 1 |
| 2 Foundational | — | T002–T003 | 2 |
| 3 | US1 (P1) 🎯 | T004–T012a | 10 |
| 4 | US2 (P2) | T013–T021 | 9 |
| 5 | US3 (P2) | T022–T028a | 8 |
| 6 | US4 (P3) | T029–T033 | 5 |
| 7 | US5 (P3) | T034–T037 | 4 |
| 8 Polish | — | T038–T043 | 6 |
| **Total** | | | **45** |

BDD coverage: 29 Gherkin scenarios across 5 feature files — 28 from `spec.md` plus the FR-010 cross-endpoint check added in T012a. By story: 8 for US1, 7 for US2, 8 for US3, 3 for US4, 3 for US5. SC-006 is verified by measurement (T028a) rather than a scenario, deliberately kept out of the automated suite.

---

## Notes

- `[P]` tasks touch different files and have no dependency on incomplete work.
- `[Story]` labels give traceability from task to user story to functional requirement.
- Verify the new scenarios are RED — failing on assertions, not erroring on import — before implementing.
- Commit after each task or logical group; T008 and T009 must be one commit.
- Stop at any checkpoint to validate a story independently.
