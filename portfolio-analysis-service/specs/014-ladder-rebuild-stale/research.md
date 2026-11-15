# Phase 0 Research: On-Demand Ladder Rebuild for Stale Requests

## R1. Where staleness currently goes unnoticed

**Decision**: Introduce the staleness check and rebuild trigger as a shared pre-read step invoked by every date-range-bearing read service (`TimeSeriesService`, `PositionTimeSeriesService`, `PerformanceService`, `DailyReturnSeriesLoader`), immediately after `TimeseriesDateResolver.resolve()` produces `resolved_end` and before `LadderRepository.read_full_df()` / `CapitalRepository.read_df()` is called.

**Rationale**: Every one of these services already follows the identical pipeline — resolve dates, read the full stored frame, call `expand_business_days()` to flat-fill through `resolved_end`. `expand_business_days()` (`app/services/business_day_expansion.py`) is a pure, stateless reindex/ffill helper with no knowledge of persistence or "today" — it is the wrong layer to own a rebuild decision. The right layer is the point where each service already knows the account, the resource (ladder vs. capital ledger), and `resolved_end`.

**Alternatives considered**:
- Push the check into `expand_business_days()` itself — rejected: it has no repository access, no market-data client, and is shared/pure by design (SOLID: single responsibility).
- Push it into the repositories (`LadderRepository`/`CapitalRepository`) — rejected: repositories are pure filesystem I/O with no business rules today, and mixing in market-data orchestration would violate their single responsibility.
- A new shared `StalenessGate` service, injected into each read service alongside the repositories — **adopted**. This keeps each read service's own orchestration logic unchanged except for one additional call.

## R2. What a position-ladder rebuild actually does

**Decision**: A position-ladder rebuild re-runs the same pipeline `IngestionService` already uses for a brand-new ingestion — `LadderExpander.expand()` → `PricingEnrichmentService.enrich()` → `ReturnsEnrichmentService.enrich()` — but seeded from the *stored* ladder's last known rows (via `LadderRepository.read_ladder_df()`, which already strips price/market_value/portfolio_weight for exactly this kind of re-enrichment) rather than a freshly uploaded ledger, and targeting a new `end_date` of "prior business day" instead of `LadderExpander`'s existing T-2 convention.

**Rationale**: `LadderExpander.expand()` already carries the last known (book_cost, quantity, total_income) forward via `expand_business_days()` for every business day through its `end_date` parameter — exactly the "last known positions continue forward" behaviour the feature calls for. No new position-projection logic is needed; only the `end_date` input needs to change from "T-2 relative to ingestion's `today`" to "T-1 relative to the request's `today`" for this call path specifically.

**Alternatives considered**:
- Write a brand-new rebuild-specific expansion routine — rejected: duplicates `LadderExpander`'s forward-fill-with-closure-rule logic (SOLID: avoid duplicating a single responsibility).
- Reuse `LadderExpander` unmodified — not possible as-is because its `end_date` is hardcoded to the ingestion T-2 convention; it needs a parameter (or an overload) for the caller to supply the target end date, keeping the closure-rule/per-sub-account behaviour identical.

## R3. What a capital-ladder rebuild actually does

**Decision**: A capital-ladder "rebuild" is a persistence-only extension: re-run the same reindex/forward-fill `expand_business_days()` already uses, from the stored series' last date through the new target end date, and persist the result with an updated `CapitalMeta.to_date`. No market-data call is involved.

**Rationale**: Unlike the position ladder, capital/income/book_value are driven only by ledger transactions, never by market pricing (`CapitalLedgerExpander`'s docstring is explicit: "NOT extended forward to today, since there is no pricing step requiring that freshness boundary"). Flat-filling the capital series forward is already *correct* — there is no new information to source. The only defect for this resource is that nothing persists the extension, so `CapitalMeta.to_date` never advances and every request re-does the same in-memory flat-fill. Persisting it is still valuable: it satisfies FR-004/FR-006 (single rebuild, no repeated work) and keeps `AccountMeta.to_date`/`CapitalMeta.to_date` meaningful as the "last ingested-or-rebuilt date" used by the staleness check (R1) and by `TimeSeriesService`'s inner join on `date` between the capital and market-value frames.

**Alternatives considered**:
- Treat the capital ladder as exempt from rebuilding entirely — rejected: FR-006 explicitly requires parity, and without it `CapitalMeta.to_date` would permanently lag `AccountMeta.to_date`, which is confusing operationally even though the values themselves are already correct.

## R4. Tracking rebuild provenance (projected vs. ledger-ingested)

**Decision**: Add a `provenance` column (`"ingested"` | `"projected"`) to the stored ladder/capital frames, written per row at persistence time, plus a lightweight `rebuilt_through: date | None` field on `AccountMeta`/`CapitalMeta` recording the current rebuild high-water mark (distinct from `to_date`, which already means "latest date with any row", ingested or projected).

**Rationale**: FR-008/FR-009 require detecting, on a later ledger ingestion, whether any previously-persisted date within the newly ingested ledger's range was a projection that must now be superseded. A per-row provenance column is the simplest mechanism that survives a direct read of the stored XLSX (consistent with this repository's existing "the XLSX is the source of truth, meta.json is derived/denormalised" pattern) and needs no new file. `rebuilt_through` on meta gives the staleness check (R1) an O(1) comparison point without re-deriving it from the full per-row frame on every read.

**Alternatives considered**:
- A separate "coverage ranges" side-file — rejected: more moving parts than a single column, and this service already keeps everything about one account's ladder in one XLSX + one meta.json pair.
- Infer provenance implicitly from `ingested_at` vs. row dates — rejected: not robust across multiple ingestions and rebuilds over time; an explicit column is unambiguous and directly testable.

## R5. Detecting and applying supersession on re-ingestion

**Decision**: In `IngestionService.ingest()`'s "new ledger, checksum differs" path (today this is `MergeNotSupportedError` — merge is not currently supported for the *ingestion* case at all, only checksum-match refresh), add a new branch: if the uploaded ledger's own date range overlaps any `provenance == "projected"` rows in the currently stored ladder, re-run `LadderExpander.expand()` over the union of the new ledger's rows and any stored *ingested* rows outside its range, then re-run pricing/returns enrichment and persist — replacing the projected rows for the overlapping span. If the uploaded ledger's range does not overlap any projected span, today's existing checksum-mismatch-is-unsupported behaviour is unchanged.

**Rationale**: This is exactly the scenario in the spec's worked example — a ledger uploaded 2026-11-01 containing an October trade must supersede a 2026-09-23→2026-11-06 projected span. The existing ingestion endpoint is already the only path that accepts a new ledger; extending its conflict-handling branch (rather than inventing a second ingestion endpoint) keeps `POST /v1/accounts/{account}/ladder` the single entry point for ledger data, consistent with FR-007 ("ingestion path continues to function unchanged for its existing responsibilities").

**Alternatives considered**:
- Require the caller to delete and re-create the account — rejected: contradicts the spec's explicit requirement that re-ingestion "must be correctly rebuilt" automatically.
- Always reject any new ledger once projected rows exist (today's blanket `MergeNotSupportedError`) — rejected: this is precisely the defect the spec calls out; it would leave October's corporate actions permanently unreflected.

## R6. Preventing duplicate concurrent rebuilds

**Decision**: An in-process, per-`(account_name, resource)` `threading.Lock` registry (resource ∈ {ladder, capital}), held for the duration of "check staleness → rebuild → persist", with the second-or-later concurrent caller blocking on the same lock and then re-reading the now-current `AccountMeta`/`CapitalMeta` rather than rebuilding again.

**Rationale**: This mirrors the existing `ThreadRunScheduler` pattern (`app/services/var/run_scheduler.py`) — a single-process FastAPI deployment (no evidence of multi-instance/distributed deployment anywhere in config or docs) already relies on in-memory `threading.Lock`/`ThreadPoolExecutor` for serialising VaR runs per account. A per-(account, resource) lock is the minimal extension of an already-accepted pattern, and avoids introducing a new distributed-locking dependency (file locks, Redis, etc.) the constitution's SOLID/simplicity expectations don't call for at this service's current scale (two known accounts).

**Alternatives considered**:
- A file-based lock in `data_dir` — rejected: no other part of this service uses file locking, and the in-memory pattern above is already proven in this exact codebase for the identical "only one of this work item in flight" requirement.
- No locking, rely on atomic `os.replace` write and accept duplicate rebild work — rejected: duplicate concurrent market-data calls to a potentially rate-limited upstream, and FR-005 explicitly requires exactly one rebuild.

## R7. Partial vs. total market-data unavailability

**Decision**: `PricingEnrichmentService.enrich()` already collects every `(sub_account, date)` pricing gap into `coverage_problems` before raising `PriceCoverageError`. The rebuild orchestration catches `PriceCoverageError` and `MarketDataServiceError` and classifies the failure using that same per-date information: if every business day in the targeted rebuild span is missing pricing for at least one sub-account, treat it as *total* unavailability (FR-013 — fall back silently to the prior flat-filled read, persist nothing); otherwise treat it as *partial* (FR-010 — persist the rebuildable prefix, and for any date that still has a coverage problem, record a null `market_value` for that row instead of raising).

**Rationale**: Reuses the existing, already-tested enrichment service's problem-detection unchanged; the rebuild orchestration layer only needs to interpret the exception it already raises today, rather than duplicating "which dates are missing" logic. `PricingEnrichmentService.enrich()` itself does not need to change its all-or-nothing contract for the *ingestion* call path (which still wants a hard failure — ingesting a ledger with unpriceable dates should fail loudly, per its existing behaviour and tests); the rebuild path wraps/interprets the same exception differently rather than loosening the service's contract for every caller.

**Alternatives considered**:
- Change `PricingEnrichmentService.enrich()` to natively support a "tolerate gaps" mode — rejected: would add a second, conditionally-tolerant contract to a service whose single responsibility today is "price fully or fail clearly" (SOLID: Open/Closed — extend via the caller's handling, don't modify the shared enrichment contract for one caller's need).

## R8. Representing null values in API responses

**Decision**: `TimeSeriesEntry` (and the analogous position/performance entry models) gain `float | None` typing for the affected attribute fields, serialised as JSON `null`, for any date whose rebuild could not source pricing.

**Rationale**: Matches the Clarifications decision (partial-unavailability dates appear with a null/absent value) and is a minimal, additive typing change — Pydantic v2 already serialises `None` as JSON `null`, no custom encoding needed.

**Alternatives considered**: None — this follows directly from the clarification answer; no competing approach was evaluated.
