---
description: "Task list for Position & Portfolio-Weighted Daily Returns feature"
---

# Tasks: Position & Portfolio-Weighted Daily Returns

**Input**: Design documents from `/specs/006-ladder-daily-returns/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/openapi.yaml ✅

**Tests**: Required — Constitution Principle I mandates TDD with BDD/Gherkin. Test tasks appear
before their corresponding implementation tasks in every phase.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to ([US1]–[US4])
- Exact file paths included in all descriptions

---

## Phase 1: Setup

**Purpose**: Project initialization and configuration scaffolding.

No tasks required. This feature introduces no new runtime dependency, no new `config.yaml`
section, and no new pytest marker — BDD scenarios reuse the existing `us1`–`us4` markers already
registered in `pyproject.toml` (feature 005). Proceed directly to Phase 2.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The pure return-computation core, shared by every user story (US1's `position_return`
and US2's `weighted_position_return` are produced by the same vectorized pass over the same
grouped/sorted DataFrame — splitting them into two services would duplicate the groupby/shift
setup for no benefit, mirroring how feature 005 built `PositionsService` once in Foundational for
both of its consuming stories).

**⚠️ CRITICAL**: All user story phases depend on this phase being fully complete.

- [X] T001 Write failing unit tests in `tests/unit/test_returns_enrichment_service.py`, importing
  `ReturnsEnrichmentService` from `app/services/returns_enrichment_service.py` (fails at import
  until T002). Build small hand-built DataFrames (same shape as
  `tests/unit/test_pricing_enrichment_service.py`'s fixtures: `date`, `sub_account`, `book_cost`,
  `quantity`, `total_income`, `price`, `market_value`, `portfolio_weight`) and assert:
  `test_first_recorded_date_has_zero_position_return_and_zero_weighted_return()` (a sub-account's
  first row → both columns exactly `0.0`); `test_position_return_matches_price_change_plus_income_per_share()`
  (multi-date single-sub-account series with varying price and one income event — assert
  `position_return` equals `(price_t - price_{t-1} + income_per_share_t) / price_{t-1}` with
  `income_per_share_t = (total_income_t - total_income_{t-1}) / quantity_t`, matching spec.md's
  User Story 1 worked example: prices `100.0, 102.0, 101.0, 103.0`, `total_income`
  `0.0, 0.0, 5.0, 5.0`, `quantity` constant `10.0` → returns
  `0.02, (101-102+0.5)/102, (103-101+0)/101` for rows 2–4); `test_weighted_return_uses_previous_row_portfolio_weight_not_same_row()`
  (**the critical regression test for the T-1 correction** — build two sub-accounts across two
  dates where `portfolio_weight` visibly changes between the two dates for at least one
  sub-account; assert `weighted_position_return` on the second date equals `position_return *`
  that sub-account's **first-date** `portfolio_weight`, and explicitly assert it does NOT equal
  `position_return *` the second date's own `portfolio_weight`, using the worked numbers from
  spec.md User Story 2: weight 0.55→0.6, `position_return=0.02` → `weighted_position_return ==
  pytest.approx(0.011)`, not `0.012`); `test_zero_quantity_treats_income_per_share_as_zero()`
  (FR-005 — a row with `quantity=0.0` must not raise `ZeroDivisionError`/produce `inf`/`NaN`;
  `income_per_share` contribution is `0`); `test_zero_previous_price_yields_zero_return_not_division_error()`
  (defensive edge case per spec.md Edge Cases — a crafted row with `price_{t-1}=0.0` yields
  `0.0`, not an exception or `inf`); `test_cash_naturally_returns_zero_with_no_special_case()`
  (a `Cash` sub-account with constant `price=1.0` and `total_income=0.0` across multiple dates —
  assert both columns are `0.0` on every non-first row, confirming no special-cased branch is
  needed); `test_gap_in_history_treated_as_new_first_date()` (a sub-account with a date gap in
  its rows — e.g. rows on 2024-01-02 and 2024-01-03, then a gap, then a row on 2024-03-01 with no
  row on 2024-02-29 — assert the row immediately after the gap has `position_return == 0.0` and
  `weighted_position_return == 0.0`, i.e. the previous *chronological* row for that sub-account,
  not an assumed-adjacent-business-day row, is what `shift(1)` naturally uses — this documents
  defensive behaviour per data-model.md even though `LadderExpander`'s current closure rule
  doesn't produce such a gap from a single ingestion today); `test_multiple_sub_accounts_computed_independently()`
  (two interleaved sub-accounts in one DataFrame — assert `shift(1)` never crosses sub-account
  boundaries, i.e. sub-account B's first row is never treated as following sub-account A's last
  row, regardless of row order in the input)

- [X] T002 Implement `app/services/returns_enrichment_service.py` — `ReturnsEnrichmentService`
  (no constructor dependencies, mirroring `PositionsService`'s shape) with
  `enrich(priced_df: pd.DataFrame) -> pd.DataFrame`: input has columns
  `[date, sub_account, book_cost, quantity, total_income, price, market_value, portfolio_weight]`
  (the output of `PricingEnrichmentService.enrich()`); sort by `["sub_account", "date"]` and
  `groupby("sub_account", sort=False)` (mirroring `PricingEnrichmentService`'s grouping style);
  within each group compute `prev_price = group["price"].shift(1)`,
  `prev_total_income = group["total_income"].shift(1)`,
  `prev_portfolio_weight = group["portfolio_weight"].shift(1)`; compute
  `income_per_share = ((group["total_income"] - prev_total_income) / group["quantity"]).where(group["quantity"] != 0, other=0.0)`
  (FR-002, FR-005 — zero-quantity guard, same `Series.where` idiom as
  `PricingEnrichmentService`'s `portfolio_weight` zero-guard, per research.md §3);
  compute `position_return = ((group["price"] - prev_price + income_per_share) / prev_price).where(prev_price.notna() & (prev_price != 0), other=0.0)`
  (FR-001, FR-004 — `prev_price.isna()` covers the first-recorded-date rule for free via
  `shift(1)`'s natural `NaN`, `prev_price != 0` covers the defensive zero-previous-price edge
  case); compute `weighted_position_return = position_return * prev_portfolio_weight.fillna(0.0)`
  (FR-003 — always uses the T-1 weight, `fillna(0.0)` covers the first-recorded-date case where
  no prior weight exists, consistent with `position_return` already being `0.0` there); concat
  all groups back with `pd.concat(..., ignore_index=True)`, restoring the original row order via
  `sort_values(["date", "sub_account"])` (matching `PricingEnrichmentService`'s output row order
  convention) `.reset_index(drop=True)`; emit a `structlog` info event `returns_enrich_complete`
  with `row_count` and `sub_account_count` (Constitution IV, mirroring
  `pricing_enrichment_service.py`'s `enrich_complete` event); full type annotations, Google-style
  docstring; depends on T001; run `pytest tests/unit/test_returns_enrichment_service.py` to
  verify all tests pass

**Checkpoint**: Foundation complete — the pure computation core is implemented and unit-tested in
isolation from the ingestion pipeline. All user story phases may now proceed.

---

## Phase 3: User Story 1 — Daily Return Recorded for Every Priced Position (Priority: P1) 🎯 MVP

**Goal**: Every row of a position ladder, once ingested, carries a `position_return` value
reflecting price change plus per-share income relative to the previous ladder date, persisted
to `ladder.xlsx`.

**Independent Test**: Ingest a ledger for an account with one non-Cash sub-account active across
several consecutive business days with varying prices and at least one income event; download the
resulting ladder and verify each row's `position_return` matches the FR-001/FR-002 formula, and
that the sub-account's first row is exactly `0.0`.

### Tests for User Story 1 ⚠️ Write and verify FAILING before implementing

- [X] T003 [P] [US1] Write Gherkin feature file `tests/features/ladder_returns.feature` (new
  file — shared across US1, US2, and US3 per research.md §6) with a `Feature: Position and
  Portfolio-Weighted Daily Returns` header and the two `@us1` scenarios verbatim from spec.md's
  User Story 1: "Daily position return reflects price change and income" (prices `100.0, 102.0,
  101.0, 103.0` on 2024-01-02 through 2024-01-05, `total_income` `0.0` through 2024-01-03 then
  `5.0` from 2024-01-04, `quantity 10.0` throughout, asserting `position_return` for
  2024-01-03/04/05 against the three formula expressions) and "First recorded date for a
  position has zero return" (sub-account "Equities B" first appearing 2024-02-01 →
  `position_return == 0.0`)

### Implementation for User Story 1

- [X] T004 [US1] Modify `app/services/ingestion_service.py`: add a `returns_service:
  ReturnsEnrichmentService` constructor parameter to `IngestionService.__init__`; on both the
  checksum-match refresh path and the new-ladder path, call
  `enriched_df = self._returns_service.enrich(enriched_df)` immediately after the existing
  `enriched_df = self._enrichment_service.enrich(...)` call, before `self._repository.write(...)`;
  renumber the class docstring's pipeline steps as a full 1–9 list to insert the new stage in
  place (e.g. "...6. Enrich with price/market_value/portfolio_weight via
  PricingEnrichmentService. 7. Enrich with position_return/weighted_position_return via
  ReturnsEnrichmentService. 8. Persist via LadderRepository. 9. Return IngestionSummary."),
  rather than inserting a "6b" sub-step into the existing plain-integer numbering; add
  `ReturnsEnrichmentService` to the module's imports; depends on T002
- [X] T005 [US1] Modify `app/api/ladder.py`'s `_get_ingestion_service` dependency function: import
  `ReturnsEnrichmentService` from `app.services.returns_enrichment_service`; construct
  `returns_service = ReturnsEnrichmentService()` (no injected dependencies, like
  `PositionsService()` in `app/api/position_timeseries.py`) and pass it as
  `IngestionService(repository=repository, enrichment_service=enrichment_service,
  returns_service=returns_service)`; depends on T004
- [X] T006 [US1] Write BDD step implementations in `tests/steps/ladder_returns_steps.py` for the
  two `@us1` scenarios: reuse the `_make_multipart`/`_download_ladder` helper pattern from
  `tests/steps/ladder_pricing_steps.py` (define locally in this new file, following the same
  shape); build the four-date ledger row-by-row with explicit `date`/`sub_account`/`book_cost`/
  `quantity`/`total_income` values matching the scenario; use
  `fake_market_data_service.configure_prices(identifier, [PriceHistoryPoint(date=..., close=...),
  ...])` (the shared `conftest.py` fixture) to make the fake market-data service return the
  scenario's exact varying prices (`100.0, 102.0, 101.0, 103.0`) instead of the fixture's
  default flat `100.0`; after ingestion, download the ladder via `GET
  .../ladder/download` and assert `position_return` values with `pytest.approx(...)` against the
  three formula expressions from the scenario, and that the "Equities B" first-date row (built as
  a separate one-row-then-continuing ledger) has `position_return == 0.0`; additionally assert
  SC-001 directly — `df["position_return"].notna().all()` and
  `df["weighted_position_return"].notna().all()` across every row of the downloaded ladder, not
  just the specific scenario rows — mirroring `ladder_pricing_steps.py`'s
  `check_every_row_priced` blanket-coverage pattern for feature 002's columns; run `pytest
  tests/features/ladder_returns.feature -m us1` to confirm all green; depends on T003, T005

**Checkpoint**: US1 complete — `position_return` is computed, persisted, and independently
BDD-tested via full ingestion.

---

## Phase 4: User Story 2 — Portfolio-Weighted Return for Allocation-Level Analysis (Priority: P1)

**Goal**: Every row also carries `weighted_position_return`, computed using the sub-account's
**previous** ladder date's `portfolio_weight` (start-of-day weight), not its own date's weight.

**Independent Test**: Ingest a ledger for an account with two sub-accounts across two consecutive
dates where at least one sub-account's `portfolio_weight` changes between the two dates; verify
`weighted_position_return` on the second date uses the *first* date's `portfolio_weight`, not the
second date's.

**Note**: `ReturnsEnrichmentService` (T002) already computes `weighted_position_return` using the
correct T-1 weight — it cannot be separated from `position_return`'s computation without
duplicating the groupby/shift setup (research.md §1–2). This phase's tasks are therefore
test-only, exercising already-implemented behaviour end-to-end via ingestion; this mirrors how
feature 005 delivered some of its later-priority stories almost entirely as test coverage over
already-built Foundational infrastructure.

### Tests for User Story 2 ⚠️ Write and verify FAILING before implementing

- [X] T007 [P] [US2] Append the two `@us2` scenarios verbatim from spec.md's User Story 2 to the
  existing `tests/features/ladder_returns.feature` (created in T003): "Weighted return uses the
  previous date's (start-of-day) portfolio weight" (sub-accounts "Equities A"/"Equities B" on
  2024-03-03 with weights 0.55/0.45, then 2024-03-04 with `position_return` 0.02/-0.01 and
  weights 0.6/0.4 — asserting `weighted_position_return` uses the **2024-03-03** weights,
  `0.011` and `-0.0045`, not the 2024-03-04 weights) and "First recorded date for a position has
  zero weighted return"

### Implementation for User Story 2

- [X] T008 [US2] Write BDD step implementations in `tests/steps/ladder_returns_steps.py` (same
  file as T006) for the two `@us2` scenarios: build a two-sub-account, two-date ledger via
  `fake_market_data_service.configure_prices(...)` with distinct per-sub-account price/quantity
  combinations engineered so `portfolio_weight` differs meaningfully between the two dates for at
  least one sub-account (e.g. differing quantities or a price move on one sub-account only);
  after ingestion, download the ladder and — rather than hand-deriving the exact prices needed to
  produce literal `position_return`/`portfolio_weight` values matching spec.md's illustrative
  numbers — compute the expected `weighted_position_return` **from the downloaded DataFrame
  itself** as the test oracle:
  `expected = df.sort_values("date").groupby("sub_account")["portfolio_weight"].shift(1) * df["position_return"]`,
  and assert `df["weighted_position_return"]` matches `expected` (`pytest.approx`, `NaN`→`0.0`
  on first rows) — this directly encodes "T-1 weight, not same-date weight" as the regression
  assertion, and additionally assert it does **not** equal
  `df["portfolio_weight"] * df["position_return"]` (the same-date weight) wherever
  `portfolio_weight` actually changed date-over-date, to positively rule out the original (bugged)
  formula regressing; run `pytest tests/features/ladder_returns.feature -m us2` to confirm all
  green; depends on T007, T006 (same file)

**Checkpoint**: US2 complete — `weighted_position_return`'s T-1 weighting is independently
BDD-tested via full ingestion, with an explicit regression guard against the same-date-weight bug
that the earlier spec correction fixed.

---

## Phase 5: User Story 3 — Returns Are Computed Once, at Ingestion Time (Priority: P1)

**Goal**: Retrieving `position_return`/`weighted_position_return` after ingestion is a plain read
— identical values across repeated reads, no re-ingestion or recomputation.

**Independent Test**: Ingest a ladder once; retrieve it twice in a row; both retrievals report
identical `position_return`/`weighted_position_return` values.

**⚠️ Ordering note**: spec.md's own Gherkin scenario for this story exercises the position time
series endpoint (`GET /v1/accounts/{account_name}/position`) requesting `position_return`/
`weighted_position_return` as attributes — which only becomes a valid request once User Story 4
(Phase 6) extends the attribute registry. T009 (authoring the scenario) has no such dependency
and can be done any time; **T010 (implementing and running its steps) must be sequenced after
T011 (Phase 6), despite this phase's earlier priority-ordered position** — record this explicitly
in the Dependencies section below rather than silently reordering the phases, since the
user-story *priority* (P1 vs P2) and the task *execution* order are not the same thing here.

### Tests for User Story 3 ⚠️ Write and verify FAILING before implementing

- [X] T009 [P] [US3] Append the one `@us3` scenario verbatim from spec.md's User Story 3 to
  `tests/features/ladder_returns.feature`: "Returns are stable across repeated reads without
  re-ingestion"

### Implementation for User Story 3

- [X] T010 [US3] Write BDD step implementations in `tests/steps/ladder_returns_steps.py` (same
  file as T006/T008) for the `@us3` scenario: ingest a ladder once via the existing `/ladder`
  POST helper; issue two separate `GET /v1/accounts/{account}/position?attribute=position_return&attribute=weighted_position_return`
  requests (reusing/adapting the request-building step from
  `tests/steps/retrieve_position_timeseries_steps.py` if a matching signature exists, else adding
  a small local step) with no ingestion call in between; assert both responses' `entries` are
  identical for `position_return` and `weighted_position_return` on every matching
  `(date, position)` pair; additionally assert no second write occurs by comparing
  `meta.json`'s `ingested_at` timestamp (via `GET .../ladder`) before and after the two reads,
  confirming it is unchanged (a plain read never re-triggers ingestion); run `pytest
  tests/features/ladder_returns.feature -m us3` to confirm green; **depends on T011 (Phase 6)**,
  not merely T009 — see the ordering note above

**Checkpoint**: US3 complete — persistence/no-recomputation is independently BDD-tested (once
T011 has landed).

---

## Phase 6: User Story 4 — Retrieve Returns Through the Position Time Series API (Priority: P2)

**Goal**: `position_return` and `weighted_position_return` are requestable as `attribute` query
values on the existing `GET /v1/accounts/{account_name}/position` endpoint, and documented on
`GET /v1/positions/attributes`.

**Independent Test**: Ingest a return-enriched ladder; request
`attribute=position_return&attribute=weighted_position_return` from the position time series
endpoint; both values appear on each entry, matching the values stored at ingestion; the
attribute metadata endpoint describes both.

### Tests for User Story 4 ⚠️ Write and verify FAILING before implementing

- [X] T011 [P] [US4] Modify `app/services/position_attributes.py`: add two entries to
  `ATTRIBUTE_DEFINITIONS` — `AttributeDefinition(name="position_return", description="The
  position's daily return: price change plus per-share income, relative to the previous day's
  price. Zero on the position's first recorded ladder date.", source="position_ladder")` and
  `AttributeDefinition(name="weighted_position_return", description="position_return scaled by
  the position's start-of-day (previous ladder date's) portfolio weight, for account- or
  theme-level contribution analysis.", source="position_ladder")`; add matching entries to
  `COLUMN_FOR_ATTRIBUTE`: `"position_return": "position_return"` and
  `"weighted_position_return": "weighted_position_return"` (both attribute names equal their
  stored column names, consistent with the `market_value`/`income` etc. pattern of explicit
  entries even where names already match); `SUPPORTED_ATTRIBUTES` picks up both automatically
  since it's derived from `ATTRIBUTE_DEFINITIONS`; no other code in this module changes
- [X] T012 [P] [US4] Append a new `@us4` scenario to `tests/features/retrieve_position_timeseries.feature`
  (feature 005's file, per research.md §6), phrased using that file's existing step vocabulary
  (`Given account "..." has an ingested position ladder containing position "..."` /
  `Then the response status is 200` / `And every entry contains a "X" value and a "Y" value`):
  a scenario asserting a request for `attribute=position_return` and `attribute=weighted_position_return`
  against a known position returns entries carrying both values (covers spec.md's "Position and
  weighted returns are retrievable as time series attributes"); if no existing `When` step
  matches a single-position, two-attribute request signature, note that a new step binding will
  be needed in T013 rather than forcing an ill-fitting reuse of the existing two-position variant
- [X] T013 [P] [US4] Modify `tests/features/position_attribute_metadata.feature`'s existing `@us3`
  (feature 005's numbering — leave its tag as-is, do not renumber) scenario "Retrieve the list of
  supported position-attribute names": update the step text from "the response lists all six
  supported attributes: market_value, income, book_cost, pnl, close_price, and quantity" to "the
  response lists all eight supported attributes: market_value, income, book_cost, pnl,
  close_price, quantity, position_return, and weighted_position_return" (the existing step
  implementation's assertion, `names == SUPPORTED_ATTRIBUTES`, already derives correctly from the
  updated registry — only the human-readable scenario text and the corresponding
  `@then` step's parser string in `tests/steps/position_attribute_metadata_steps.py` need
  updating to match the new wording; do not change the underlying assertion logic)

### Implementation for User Story 4

- [X] T014 [US4] Write BDD step implementations in `tests/steps/retrieve_position_timeseries_steps.py`
  for the new `@us4` scenario from T012 (add a new step binding only if T012 determined the
  existing two-position step doesn't fit — a single-position, two-named-attribute variant of
  `request_two_attributes_two_positions_with_range`, following its existing pattern exactly);
  assert the response's `entries` each carry `position_return` and `weighted_position_return`
  keys with values matching what a direct ladder download for the same account/position/dates
  shows; run `pytest tests/features/retrieve_position_timeseries.feature -m us4` to confirm
  green; depends on T011, T012
- [X] T015 [US4] Update `tests/steps/position_attribute_metadata_steps.py`'s `@then` parser string
  to match T013's updated scenario wording ("all eight supported attributes: ...
  position_return, and weighted_position_return") — the assertion body itself
  (`names == SUPPORTED_ATTRIBUTES`) requires no change since it already derives dynamically from
  the updated registry (T011); run `pytest tests/features/position_attribute_metadata.feature -m us3`
  to confirm green; depends on T011, T013
- [X] T016 [US4] Return to Phase 5 and complete T010 now that T011 has landed; run `pytest
  tests/features/ladder_returns.feature -m us3` to confirm US3 is now green end-to-end

**Checkpoint**: US4 complete — both new metrics are retrievable through the existing position
time series API and documented in its attribute metadata. All four user stories are now
independently functional and BDD-tested (US3's test, though authored earlier, only becomes
executable once this phase lands — see the Phase 5 ordering note).

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Code quality gates, contract sync, edge-case coverage, and a full regression gate.

- [X] T017 [P] Run `ruff check app/ tests/` and `ruff format app/ tests/` on all new/changed files
  (`app/services/returns_enrichment_service.py`, `app/services/ingestion_service.py`,
  `app/services/position_attributes.py`, `app/api/ladder.py`, and all new/changed test files);
  fix all reported issues including any `D` (pydocstyle) violations (Constitution III); run
  `mypy --strict app/`; resolve all type errors; confirm zero errors in all three checks
- [X] T018 [P] Verify OpenAPI spec accuracy: start the server, fetch
  `http://localhost:8000/openapi.json`, compare the `/positions/attributes` response shape and
  the `/accounts/{account_name}/position` path's `attribute` parameter against
  `specs/006-ladder-daily-returns/contracts/openapi.yaml`. Note: the live route types `attribute`
  as plain `list[str]` (validated at the service layer via `position_attributes.validate_attributes`,
  not via a Pydantic/FastAPI `Literal`/enum), so the generated `/openapi.json` will not itself
  list the 8-value enum that `contracts/openapi.yaml` documents for readability — this is a
  pre-existing divergence inherited from feature 005 (not introduced by this feature); confirm it
  still holds and record it as an accepted, known gap rather than a regression to fix here

- [X] T019 Run `quickstart.md` validation end-to-end: start the service, ingest (or reuse
  already-ingested) real position ladder data, execute each documented `curl` command from
  `specs/006-ladder-daily-returns/quickstart.md`, confirm responses match the documented examples
  including the first-row-zero and T-1-weighting sanity checks, and record/fix any discrepancies
  in `quickstart.md`
- [X] T020 [P] Add the remaining edge-case scenario not already covered by US1–US4's Gherkin to
  the existing shared `tests/features/validation.feature` (reusing the `@validation` tag): a
  sub-account whose `quantity` reaches `0.0` on some ladder date (a genuine divestment, via
  `LadderExpander`'s existing closure-rule row) still ingests successfully with
  `position_return`/`weighted_position_return` recorded (not null, not raising) on that closure
  date, with `income_per_share` treated as `0` per FR-005; add a corresponding step to
  `tests/steps/validation_steps.py`; run `pytest tests/features/validation.feature -m validation`
  to confirm all green
- [X] T021 Run the full test suite (`pytest -q`) and confirm zero regressions against the
  pre-existing baseline (including the one already-documented pre-existing timing-flaky test
  noted in feature 004/005's tasks.md, `test_idempotent_resubmit_within_1_second`, which is
  unrelated to this feature)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No tasks — nothing to wait on
- **Foundational (Phase 2)**: Blocks all user stories. T001 → T002 (test-first)
- **US1 (Phase 3)**: Depends on Phase 2 — MVP delivery point
- **US2 (Phase 4)**: Depends on Phase 2 and T006 (same steps file as T008) — otherwise
  independent of US1's own scenarios
- **US3 (Phase 5)**: T009 depends only on Phase 2 (can be authored any time); **T010 depends on
  T011 (Phase 6)**, an exception to normal phase ordering — see the note in Phase 5
- **US4 (Phase 6)**: Depends on Phase 2. T011 has no dependency on US1–US3 and could technically
  be done as early as Phase 2, but is kept in Phase 6 to preserve US4's independent-delivery
  framing (P2, "closes the loop" per spec.md) — T016 explicitly loops back to unblock T010
- **Polish (Phase 7)**: Depends on all four user story phases being complete

### Within-Phase Dependencies

- T001 → T002 (Phase 2, test-first)
- T003 [P] with T001/T002 (no code dependency — pure Gherkin authoring); T004 → T002; T005 → T004;
  T006 → T003, T005
- T007 [P] with any Phase 3 implementation task; T008 → T007, T006 (same steps file)
- T009 [P] with any earlier phase; T010 → T011 (cross-phase — see ordering note)
- T011 [P] with Phase 3–5 implementation tasks; T012 [P] with T011; T013 [P] with T011/T012;
  T014 → T011, T012; T015 → T011, T013; T016 → T011 (unblocks T010)

### Parallel Opportunities

```
Phase 2: T001 then T002 (sequential, test-first)

Phase 3 test-writing: T003 (parallel with T001/T002 — no code dependency)
Phase 4 test-writing: T007 (parallel with any Phase 3 implementation task)
Phase 5 test-writing: T009 (parallel with any earlier phase)
Phase 6 test-writing: T011, T012, T013 (all independent files, fully parallel)

T006, T008, T010 all touch tests/steps/ladder_returns_steps.py (same file) — sequence them
in order (T006 → T008 → T010) even though they belong to different story phases

Phase 7 parallel group: T017, T018, T020 (independent); T019 and T021 are sequential final gates
```

---

## Parallel Example: User Story 1

```bash
# Phase 2 must complete first (T001 → T002).
# Then, in parallel:
Task: "Write Gherkin feature file tests/features/ladder_returns.feature with @us1 scenarios"
# ...while T004/T005 (pipeline wiring) proceed on their own file dependencies (T002 → T004 → T005)

# T006 (steps) needs both T003 (scenarios exist) and T005 (wiring complete) before it can pass.
```

---

## Implementation Strategy

### MVP: User Story 1 Only

1. Complete Phase 2: Foundational (CRITICAL — blocks everything; Phase 1 has no tasks)
2. Complete Phase 3: User Story 1
3. **STOP and VALIDATE**:
   - `pytest tests/unit/test_returns_enrichment_service.py tests/features/ladder_returns.feature -m us1`
   - POST a real ledger via curl; download the ladder; confirm `position_return` values and the
     first-date-zero rule by hand
4. Proceed to Phase 4 (US2), then Phase 6 (US4) before completing Phase 5 (US3) — see the
   ordering note in Phase 5

### Incremental Delivery

1. Phase 2 → Foundation ready (both metrics' computation core exists and is unit-tested)
2. Phase 3 (US1) → `position_return` works end-to-end via ingestion → **demo-able MVP**
3. Phase 4 (US2) → `weighted_position_return`'s T-1 weighting independently regression-tested
4. Phase 6 (US4) → both metrics retrievable via the existing position time series API
5. Phase 5 (US3, completed via T016 after Phase 6) → persistence/no-recomputation confirmed via
   the now-available API attributes
6. Phase 7 → code quality gates pass, OpenAPI/quickstart verified, edge case covered, full-suite
   regression gate passes

### Parallel Team Strategy

With multiple developers:

1. Team completes Phase 2 together (T001 → T002 is a short, sequential critical path)
2. Once Phase 2 is done:
   - Developer A: Phase 3 (US1) → then Phase 4 (US2), since both touch
     `tests/steps/ladder_returns_steps.py` sequentially
   - Developer B: Phase 6 (US4) in parallel — no file overlap with Developer A until T016
3. Once both land, either developer completes T016 (Phase 5's deferred step implementation)

---

## Notes

- `[P]` = parallelisable (different files, no blocking dependency)
- `[Story]` maps task to user story for traceability
- BDD test tasks MUST be written and verified to FAIL before implementation tasks begin
- Use `pytest -m us1` / `-m us2` / `-m us3` / `-m us4` to run one story's tests in isolation; the
  `us1`–`us4` markers registered in `pyproject.toml` (feature 005) are reused here — no new
  marker registration needed
- Commit after each checkpoint (end of each user story phase)
- `data/` and `logs/` remain gitignored — never commit runtime artefacts
- This feature makes **zero** additional market-data-service calls (unlike feature 002) — all
  computation is over columns already present after existing price enrichment (plan.md,
  research.md §1)
- User Story 3 is the one place this feature's task order deliberately departs from strict
  priority order (P1 before P2): its own spec.md Gherkin scenario exercises attributes that User
  Story 4 (P2) introduces. This is called out explicitly (Phase 5's ordering note, T010's and
  T016's dependency notes) rather than silently resolved, so the discrepancy between "priority
  order" and "execution order" is traceable back to a real, spec-level cause rather than a
  planning oversight
- T002's `weighted_position_return = position_return * prev_portfolio_weight.fillna(0.0)` line is
  the single most important line in this feature — it is the corrected formula from spec.md's
  "Correction 2026-07-26" entry (previously, incorrectly, same-date `portfolio_weight`). T001's
  `test_weighted_return_uses_previous_row_portfolio_weight_not_same_row` and T008's BDD assertion
  against the *non*-T-1 formula are both permanent regression guards for this specific defect and
  MUST NOT be weakened or removed
