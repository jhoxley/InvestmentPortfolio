# Implementation Plan: Observed-Only Price History (`fill=none`)

**Branch**: `026-mds-observed-prices-fill-none` | **Date**: 2026-10-03 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/009-observed-prices-fill-none/spec.md`

## Summary

The security history endpoint gains a `fill` query parameter (`all` — today's gap-filled default, or
`none` — observations only), two additive response fields reporting the instrument's known observation
window, and a cache that remembers when the data source has nothing before an instrument's earliest
observation so repeat long-lookback requests stop paying for the same empty fetch.

The technical approach keeps `GapFillService` untouched and adds a sibling strategy. A narrow
`SeriesFiller` protocol — whose signature `GapFillService.fill` already satisfies structurally — gains a
second implementation, `ObservedOnlyFiller`, which clips observations to the requested range and
manufactures nothing. `PricingService.get_price_history` takes a `FillMode` and picks the strategy. The
observation window is a separate optional capability protocol (`ObservationWindowSource`) implemented by
the cache and fallback providers, queried *after* the fetch so a widened window is reported for free. The
no-earlier-data boundary is a per-ticker sidecar JSON file in the existing cache directory, consulted and
maintained inside `CachedPricingProvider`, which already owns segment planning. Currency conversion needs
no algorithmic change: `CurrencyService` already aligns gap-filled FX rates onto whatever price dates it
is given, so handing it an observed-only list produces exactly the required behaviour.

## Technical Context

**Language/Version**: Python 3.11+ (local venv runs 3.14.4)
**Primary Dependencies**: FastAPI 0.115, pydantic v2, yfinance 0.2, structlog, pytest + pytest-bdd — no new dependencies
**Storage**: Per-ticker CSV cache files on local disk (`./cache/{ticker}.csv`), plus a new per-ticker sidecar `./cache/{ticker}.meta.json`
**Testing**: pytest + pytest-bdd, BDD-first with Gherkin `.feature` files under `tests/features/` and step definitions under `tests/steps/`
**Target Platform**: Local HTTP service (Windows dev host, Linux-compatible)
**Project Type**: HTTP web service (FastAPI), single project
**Performance Goals**: Eliminate the repeated data-source call for a known-empty earlier segment — a repeat five-year lookback on a two-year-old instrument must make zero data-source calls for the pre-history segment. Observed-only mode is strictly less work than gap-fill (no business-day grid generation).
**Constraints**: `fill=all` output must be byte-identical to today's; the two new response fields must be additive; a provider outage must never be recorded as "no data exists"; the sidecar must die with the cache file it describes
**Scale/Scope**: One endpoint (`GET /securities/{ticker}/history`); 5 user stories; ~5 new source files and ~6 modified; 5 new `.feature` files

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design — see Post-Design Re-check below.*

| Principle | Check | Notes |
|-----------|-------|-------|
| I. SOLID Design | ✅ | `ObservedOnlyFiller` is a new class, not a modification of `GapFillService` (Open/Closed). `SeriesFiller` and `ObservationWindowSource` are narrow protocols — no provider is forced to implement a method it cannot answer (Interface Segregation). Both fillers are substitutable behind one signature (Liskov). The strategy is injected into `PricingService` via its existing constructor pattern (Dependency Inversion). Boundary persistence sits in `CacheRepository`; boundary *policy* sits in `CachedPricingProvider` (Single Responsibility). |
| II. Standard Dependencies | ✅ | Nothing added. Uses stdlib `enum.StrEnum`, `json`, `os.replace`, `typing.Protocol`. All existing deps remain pinned in `pyproject.toml`. |
| III. BDD Test-First | ✅ | Five `.feature` files, one per user story, authored and confirmed RED before any implementation task. Every endpoint-level scenario exercises the full request/response lifecycle via `TestClient`. |
| IV. Code Quality Standards | ✅ | Existing root-level `ruff` (line-length 100, `ANN` enabled) and `mypy --strict` configs apply unchanged; full type annotations on all new code, test code included. |
| V. Observability & Logging | ✅ | Three new structured `structlog` events for the boundary lifecycle (`cache_no_earlier_data_recorded` / `_skip` / `_invalidated`), each carrying ticker and date boundary — this is FR-024, a functional requirement, not just hygiene. One event for observed-only filtering (`observed_only_applied`). |
| VI. OpenAPI-First | ✅ | `openapi.yaml` is updated first: the `fill` parameter with its enum, the two new `PriceHistoryResponse` properties as named-component fields, and the revised 200 description. Implementation follows the contract. |

No unchecked items. **Gate passed.**

## Project Structure

### Documentation (this feature)

```text
specs/009-observed-prices-fill-none/
├── plan.md                      ← this file
├── spec.md
├── research.md                  ← Phase 0
├── data-model.md                ← Phase 1
├── quickstart.md                ← Phase 1
├── contracts/
│   └── openapi-changes.md       ← Phase 1
├── checklists/
│   └── requirements.md
└── tasks.md                     ← generated by /speckit-tasks
```

### Source Code (affected paths)

```text
app/
├── models/
│   ├── fill.py                      ← NEW: FillMode StrEnum
│   └── pricing.py                   ← MODIFY: first_observed_date / last_observed_date on PriceHistoryResponse
├── services/
│   ├── series_fill.py               ← NEW: SeriesFiller protocol + ObservedOnlyFiller + FillStrategyResolver
│   ├── gap_fill.py                  ← UNCHANGED (already satisfies SeriesFiller structurally)
│   ├── pricing_service.py           ← MODIFY: fill mode param, strategy resolution, window population, empty→404
│   └── currency_service.py          ← MODIFY: carry window fields through build_translated_history
├── providers/
│   ├── observation_window.py        ← NEW: ObservationWindow dataclass + ObservationWindowSource protocol
│   ├── cached_provider.py           ← MODIFY: boundary skip/record/invalidate; observation_window()
│   ├── fallback_provider.py         ← MODIFY: delegate observation_window() to inner or local
│   └── local_provider.py            ← MODIFY: observation_window() from CSV extremes
├── cache/
│   └── repository.py                ← MODIFY: read/write/delete sidecar; delete_all globs *.meta.json
└── api/
    └── securities.py                ← MODIFY: fill query param, pass through to service

tests/
├── features/
│   ├── observed_only_history.feature          ← NEW (US1)
│   ├── observation_window.feature             ← NEW (US2)
│   ├── cache_no_earlier_data.feature          ← NEW (US3)
│   ├── observed_only_fallback.feature         ← NEW (US4)
│   └── observed_only_fx.feature               ← NEW (US5)
├── steps/
│   ├── observed_only_history_steps.py         ← NEW
│   ├── observation_window_steps.py            ← NEW
│   ├── cache_no_earlier_data_steps.py         ← NEW
│   ├── observed_only_fallback_steps.py        ← NEW
│   └── observed_only_fx_steps.py              ← NEW
├── fixtures/
│   └── priv01_sparse.csv                      ← NEW: sparse rows + rows outside the test range
└── conftest.py                                ← MODIFY: pass the new resolver into PricingService in 4 fixtures

openapi.yaml                                   ← MODIFY: fill param, 2 response fields, 200 description; bump version
```

**Structure Decision**: Single FastAPI project, existing layered layout retained
(`api` → `services` → `providers` → `cache`). The feature adds no new layer: the fill strategy joins
`app/services/`, the window capability joins `app/providers/`, and boundary persistence extends the
existing `app/cache/repository.py`. No directory is introduced.

## Design

### 1. Fill mode selection

```python
# app/models/fill.py
class FillMode(StrEnum):
    ALL = "all"
    NONE = "none"

# app/services/series_fill.py
class SeriesFiller(Protocol):
    def fill(
        self, observations: list[tuple[date, float]], from_date: date, to_date: date
    ) -> list[tuple[date, float]]: ...

class ObservedOnlyFiller:
    """Returns only real observations, clipped to the requested range."""
    def fill(self, observations, from_date, to_date): ...
        # de-dupe by date, sort, keep from_date <= d <= to_date, manufacture nothing

class FillStrategyResolver:
    def __init__(self, gap_fill: GapFillService, observed_only: ObservedOnlyFiller) -> None: ...
    def resolve(self, mode: FillMode) -> SeriesFiller: ...
```

`GapFillService` is not edited — its existing `fill` signature already satisfies `SeriesFiller`.
`ObservedOnlyFiller` keeps weekend-dated observations (a real observation is an observation); only the
business-day *grid* is a gap-fill construct.

### 2. Observation window

```python
# app/providers/observation_window.py
@dataclass(frozen=True)
class ObservationWindow:
    first_observed_date: date
    last_observed_date: date

@runtime_checkable
class ObservationWindowSource(Protocol):
    def observation_window(self, ticker: str) -> ObservationWindow | None: ...
```

- `CachedPricingProvider.observation_window` → first/last row of the cache CSV.
- `LocalPricingProvider.observation_window` → first/last row of the fallback CSV.
- `FallbackPricingProvider.observation_window` → the local file's window whenever the local file served
  the request: both for a `use_local_only` entry **and** for an entry whose file was used because the
  primary source returned nothing. It delegates to its inner provider only when the primary source
  actually supplied the prices. Keying this off the configuration flag alone would return `None` for the
  fallback-triggered case, where the file supplied the data but no cache file exists — breaking FR-017.
- `PricingService` calls it **after** `get_price_history`, so the cache write performed during a
  partial-hit fetch is already reflected (FR-015 satisfied with no extra bookkeeping). If the provider
  does not implement the protocol, the window is derived from the raw series just returned — which keeps
  every existing `MagicMock(spec=PricingProvider)` fixture working.

### 3. No-earlier-data boundary

Persistence (`CacheRepository`): `read_no_data_before(ticker)`, `write_no_data_before(ticker, d)`,
`clear_no_data_before(ticker)`, backed by `{sanitised-ticker}.meta.json` written atomically via temp
file + `os.replace`. `delete()` removes the sidecar with the CSV; `delete_all()` must glob
`*.meta.json` in addition to its current `*.csv` — the existing glob would otherwise leave sidecars
behind.

Policy (`CachedPricingProvider.get_price_history`), applied only to the `before` segment:

```
boundary = repo.read_no_data_before(ticker)

if cached_min < boundary:                     → clear boundary          (log _invalidated)
if from_date < cached_min:
    if boundary and boundary <= cached_min:   → skip the fetch          (log _skip)
    else: fetch the segment
        if empty:                             → write cached_min        (log _recorded)
        else:                                 → write min(before dates) (log _invalidated)

# cold-cache populate:
if fetched and first fetched date > from_date → write first fetched date (log _recorded)
```

The `after` segment is never guarded (FR-020). `_fetch_segment` already converts `DataNotFoundError`
into an empty list while re-raising `ProviderUnavailableError`, so a provider outage reaches this logic
as an exception, never as "no data exists" — the distinction FR-018 depends on.

### 4. Currency conversion

No algorithmic change. `CurrencyService.translate_history` already gap-fills the FX series and aligns it
onto `[p.date for p in records]`; an observed-only `records` list therefore yields each observation at
that date's gap-filled rate (FR-025) and cannot gain dates, since the output is built by iterating
`records` (FR-026). The single required edit: `build_translated_history` must copy
`first_observed_date` / `last_observed_date` into the `PriceHistoryResponse` it constructs, rather than
dropping them.

### 5. Endpoint

```python
@router.get("/{ticker}/history", response_model=PriceHistoryResponse)
async def get_price_history(
    ...,
    fill: FillMode = Query(default=FillMode.ALL),
    ...
)
```

Typing the parameter as the enum makes FastAPI reject an unknown value with a 422 naming `fill` during
request parsing — before the endpoint body, and therefore before any data-source call (FR-004), with no
hand-written validator.

## Behaviour Change to Flag

`PricingService.get_price_history` will raise `DataNotFoundError` (→ 404) when the post-fill series is
empty, in **both** modes. Feature 006's FR-008 and this spec's FR-009 both already require that, but the
current code answers 200 with an empty `prices` list in one path: when a cache file exists and holds
nothing inside the requested range. FR-002 carries an explicit carve-out for this, and it is the only
non-additive change in the feature. This is required for `fill=none` (where an out-of-range request is
common) and aligns `fill=all` with its own documented contract. A grep of `tests/` found no assertion of
a 200-with-empty-`prices` response, so the existing suite is not expected to break — but this is a real,
if narrow, behaviour change for `fill=all` and should be confirmed green rather than assumed.

## BDD Scenario → Feature File Mapping

| User Story | Feature File | Step File | Scenarios |
|---|---|---|---|
| US1 — Observed-only history | `observed_only_history.feature` | `observed_only_history_steps.py` | 7 |
| US2 — Observation window | `observation_window.feature` | `observation_window_steps.py` | 5 |
| US3 — No-earlier-data memory | `cache_no_earlier_data.feature` | `cache_no_earlier_data_steps.py` | 6 |
| US4 — Observed-only fallback | `observed_only_fallback.feature` | `observed_only_fallback_steps.py` | 3 |
| US5 — Observed-only + FX | `observed_only_fx.feature` | `observed_only_fx_steps.py` | 3 |

US3's log assertions use `structlog`'s capture facility; US3's "data source not called" assertions use
the existing `mock_inner_provider` call-count pattern from `cache_partial_hit_steps.py`.

## Dependency Graph

```
T001 openapi.yaml contract (fill param, 2 fields, descriptions)   [OpenAPI-First gate]
  │
  ├─► T002 five .feature files + fixture CSV
  │     └─► T003 step definition stubs — confirm RED            [BDD-First gate]
  │           │
  │           ├─► T004 FillMode enum + SeriesFiller/ObservedOnlyFiller/FillStrategyResolver
  │           ├─► T005 ObservationWindow + ObservationWindowSource protocol
  │           ├─► T006 CacheRepository sidecar read/write/clear/delete/delete_all
  │           │     └─► T007 CachedPricingProvider boundary policy + logs + observation_window()
  │           ├─► T008 LocalPricingProvider + FallbackPricingProvider observation_window()
  │           ├─► T009 PriceHistoryResponse new fields
  │           │     └─► T010 PricingService: fill mode, window, empty→404
  │           │           ├─► T011 CurrencyService carries window fields
  │           │           └─► T012 securities.py fill param + resolver wiring
  │           │                 └─► T013 conftest.py fixture updates
  │                                       │
  │                                       ▼
  │                                 T014 full suite GREEN (new + existing)
  │                                       │
  └───────────────────────────────────────┴─► T015 ruff + mypy --strict clean; README/quickstart notes
```

No implementation task (T004 onward) may begin until T002 and T003 are complete and the new scenarios
are confirmed failing.

## Constitution Check — Post-Design Re-check

Re-evaluated after Phase 1 (`research.md`, `data-model.md`, `contracts/openapi-changes.md`,
`quickstart.md`). All six principles still pass; the design surfaced three points worth recording:

| Principle | Status | Post-design finding |
|-----------|--------|---------------------|
| I. SOLID Design | ✅ | Confirmed by design: `GapFillService` needs **zero** edits because its existing `fill` signature already satisfies `SeriesFiller`. `CurrencyService` needs no algorithmic change — only field pass-through. The two protocols stay separate deliberately: merging `ObservationWindowSource` into `PricingProvider` would force an unanswerable method onto `YFinanceProvider`. |
| II. Standard Dependencies | ✅ | Design closed with **no new dependency**. Everything new is stdlib (`enum.StrEnum`, `json`, `os.replace`, `typing.Protocol`) or already pinned. |
| III. BDD Test-First | ✅ | All 24 spec scenarios mapped to five `.feature` files (see mapping table). The `tasks.md` dependency graph gates every implementation task behind a confirmed-RED run. |
| IV. Code Quality Standards | ✅ | No new config; existing `ruff` + `mypy --strict` apply. Note for implementation: `@runtime_checkable` Protocol narrowing needs explicit handling to keep `mypy --strict` clean. |
| V. Observability & Logging | ✅ | Four new structured events specified with their exact fields. Three of them (`cache_no_earlier_data_recorded` / `_skip` / `_invalidated`) are FR-024 — test-asserted behaviour, not optional hygiene. |
| VI. OpenAPI-First | ✅ | `contracts/openapi-changes.md` is complete and is task T001, before any code. `FillMode` is a **named** component, not an inline enum, per the principle's explicit prohibition. Version bumped 0.1.2 → 0.1.3 (additive, so no major bump). |

**Gate re-passed.** One item is carried forward as a deliberate, documented behaviour change rather than a
violation: the empty-range 404 alignment (see "Behaviour Change to Flag" above). It brings the code into
line with an already-published contract, so it needs no constitutional exception — but it must be
verified green, not assumed.

## Complexity Tracking

No constitution violations; the table is intentionally empty. Two design choices that could look like
added complexity are justified above rather than waived: the second *protocol*
(`ObservationWindowSource`, kept separate from `PricingProvider` to avoid forcing an unanswerable method
onto `YFinanceProvider` — Interface Segregation), and the sidecar *file* (kept out of the cache CSV to
preserve its `date,close` contract).
