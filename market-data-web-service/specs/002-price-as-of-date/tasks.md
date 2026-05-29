---
description: "Task list for Add As-Of Date to Current Price Response — 002-price-as-of-date"
---

# Tasks: Add As-Of Date to Current Price Response

**Input**: Design documents from `/specs/002-price-as-of-date/`
**Prerequisites**: plan.md ✅ spec.md ✅ data-model.md ✅ contracts/openapi-diff.md ✅ research.md ✅

**Tests**: BDD Gherkin `.feature` files and step definitions are MANDATORY per the project constitution (Principle III — NON-NEGOTIABLE). They MUST be written and confirmed failing before any implementation task begins.

**Organization**: Single user story (P1). Tasks flow: OpenAPI contract → BDD red → model → provider → service → green.

## Format: `[ID] [P?] [Story?] Description with file path`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to
- All tasks include exact file paths

---

## Phase 1: Foundational (OpenAPI-First — Principle VI)

**Purpose**: Update the API contract before any implementation begins, per the project constitution.

- [ ] T001 Update `openapi.yaml` at project root: add `as_of_date` to `PriceResponse` component properties (type: string, format: date, with description) and to the `required` list; update the 200 example response for `GET /securities/{ticker}/price` to include `as_of_date` (see `specs/002-price-as-of-date/contracts/openapi-diff.md` for the exact change)

---

## Phase 2: User Story 1 — Know What Date a Price Is For (Priority: P1)

**Goal**: The current price response always includes `as_of_date` — the trading date the price is sourced from — and this date reconciles with the most recent entry from the history endpoint for the same ticker.

**Independent Test**: `pytest tests/steps/current_price_as_of_date_steps.py -v` — all 3 BDD scenarios green.

### BDD Scenarios for User Story 1 (MANDATORY — write and confirm failing FIRST) ⚠️

> **All 3 scenarios MUST fail before any implementation task below begins (Red-Green-Refactor)**

- [x] T002 [P] [US1] Write `tests/features/current_price_as_of_date.feature` — 3 Gherkin scenarios: (1) price response contains `as_of_date` in YYYY-MM-DD format, (2) `as_of_date` is not a future date and not a Saturday or Sunday, (3) `as_of_date` matches the `date` of the last entry in `/securities/MSFT/history` with no date parameters (copy scenarios verbatim from `specs/002-price-as-of-date/spec.md`)
- [x] T003 [P] [US1] Write `tests/steps/current_price_as_of_date_steps.py` — implement `@given`, `@when`, `@then` step functions using the shared `client` fixture from `tests/conftest.py`; the reconciliation scenario uses two `@when` steps each with `target_fixture` (`price_response`, `history_response`) so the `@then` step can access both; add `scenarios("current_price_as_of_date.feature")` and ensure pytest discovers the file; confirm all 3 scenarios FAIL before proceeding

### Implementation for User Story 1

- [x] T004 [US1] Update `app/models/pricing.py` — add `as_of_date: date` as a required field on `PriceResponse` (import `date` from `datetime`; field has no default value so it is always required); no changes to any other model
- [x] T005 [US1] Update `app/providers/yfinance_provider.py` — rewrite `get_current_price()`: replace `fast_info.last_price` price source with `Ticker.history(period="5d")`; filter rows where `Close <= 0`; take the last row for both `price = float(last_row["Close"])` and `as_of_date = df.index[-1].date()`; fix `market_state` by calling `t.info.get("marketState")` instead of `getattr(fast_info, "market_state", None)`; keep the same `_NETWORK_ERRORS` exception mapping; return dict now includes `"as_of_date"` key
- [x] T006 [US1] Update `app/services/pricing_service.py` — in `get_current_price()`, pass `as_of_date=raw["as_of_date"]` when constructing `PriceResponse`; update `market_status` logic to handle `"REGULAR"` (yfinance value for open market) mapping to `"open"` in addition to the existing `"open"` check

**Checkpoint**: `pytest tests/steps/current_price_as_of_date_steps.py -v` — all 3 US1 scenarios PASS.
Then run `pytest tests/ -v` — all 12 scenarios (9 existing + 3 new) PASS together.

---

## Phase 3: Polish & Cross-Cutting Concerns

**Purpose**: Update derived artifacts and confirm the full quality gate passes.

- [x] T007 [P] Regenerate `openapi.yaml` from the live FastAPI schema: start the TestClient in a Python one-liner, fetch `/openapi.json`, dump to YAML, overwrite `openapi.yaml` at project root (same approach as feature 001, T033)
- [x] T008 [P] Run `mypy app/ --ignore-missing-imports` — 0 errors; fix any type annotation issues introduced by the new `as_of_date: date` field or the provider dict change
- [x] T009 [P] Update `README.md` — in Section 2 (Programmatic Use), update the `PriceResponse` example JSON under "Current price" snippets to include `"as_of_date": "2026-05-06"`; update the `get_price_history` DataFrame helper if any inline comments reference the price response shape

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundational (Phase 1)**: No dependencies — start immediately (T001 is independent)
- **User Story 1 BDD (T002, T003)**: Depends on Phase 1 complete; run in parallel with each other
- **Implementation (T004–T006)**: Depends on T002 + T003 (all 3 BDD scenarios confirmed FAILING); run sequentially — model first (T004), then provider (T005), then service (T006)
- **Polish (Phase 3)**: Depends on all 12 tests passing (checkpoint after T006)

### Within User Story 1 (strict ordering)

1. Write `.feature` file (T002) → 2. Write step definitions (T003) → 3. **Confirm all 3 FAIL** → 4. Update model (T004) → 5. Update provider (T005) → 6. Update service (T006) → 7. **Confirm all 12 PASS**

### Parallel Opportunities

```bash
# Phase 1 (only one task):
Task: "T001 Update openapi.yaml"

# BDD — T002 and T003 run in parallel (different files):
Task: "T002 Write current_price_as_of_date.feature"
Task: "T003 Write current_price_as_of_date_steps.py"

# Implementation — sequential (model → provider → service):
Task: "T004 Update PriceResponse model"
  → Task: "T005 Update YFinanceProvider.get_current_price()"
    → Task: "T006 Update PricingService.get_current_price()"

# Polish — all three parallel (different files):
Task: "T007 Regenerate openapi.yaml"
Task: "T008 Run mypy"
Task: "T009 Update README.md"
```

---

## Implementation Strategy

### MVP (Single Story — All Tasks)

This feature has one user story. All 9 tasks constitute the complete delivery:

1. T001 — Update OpenAPI contract (Principle VI gate)
2. T002 + T003 — BDD scenarios (confirmed red)
3. T004 → T005 → T006 — Model, provider, service (green)
4. T007 + T008 + T009 — Polish and quality gate

**Validation command after T006:**
```powershell
pytest tests/ -v
# Expected: 12 passed (9 existing + 3 new)
```

---

## Summary

| Phase | Tasks | Parallel | User Story |
|-------|-------|----------|------------|
| Foundational | T001 | — | — |
| US1 BDD | T002–T003 | 2 of 2 | P1 |
| US1 Implementation | T004–T006 | 0 of 3 (sequential) | P1 |
| Polish | T007–T009 | 3 of 3 | — |
| **Total** | **9** | | |

**BDD scenarios**: 3 total — all executable via `pytest tests/steps/current_price_as_of_date_steps.py -v`
