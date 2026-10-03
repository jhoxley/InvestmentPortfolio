# Phase 0 Research: Observed-Only Price History (`fill=none`)

**Feature**: `specs/009-observed-prices-fill-none` | **Date**: 2026-10-03

All Technical Context items were resolved by reading the existing implementation; no external research
or NEEDS CLARIFICATION items remain. Each decision below records what was chosen, why, and what was
rejected.

---

## R1 — How to select between gap-filled and observed-only series

**Decision**: Introduce a narrow `SeriesFiller` protocol (`fill(observations, from_date, to_date)`),
a `FillMode` string enum (`all` / `none`), and a second implementation `ObservedOnlyFiller` that clips
observations to the requested range without manufacturing dates. `PricingService.get_price_history`
accepts a `FillMode` and resolves the strategy; `GapFillService` is left completely untouched.

**Rationale**:

- `GapFillService.fill(observations, from_date, to_date) -> list[tuple[date, float]]` already matches
  the protocol signature exactly, so it conforms structurally with zero edits — satisfying
  Open/Closed (new behaviour by extension, principle I).
- A `typing.Protocol` keeps the abstraction narrow (Interface Segregation) and avoids forcing an
  inheritance relationship onto a stable, well-tested class.
- `GapFillService` is also used by `CurrencyService` for FX rates, which must *keep* gap-filling in
  both modes (FR-025). Not touching it guarantees that, and removes any chance of the FX path
  inheriting the new mode by accident.

**Alternatives rejected**:

- *A boolean `gap_fill: bool` parameter threaded into `GapFillService.fill`* — puts two behaviours in
  one class, violates Single Responsibility, and makes the FX path's "always fill" guarantee implicit
  rather than structural.
- *Filtering the gap-filled series back down to observed dates afterwards* — requires carrying a
  per-entry "was filled" flag through the series purely to strip it again, and risks a filled value
  surviving into the response if the flag is ever lost. FR-008 forbids exactly that outcome.
- *A separate endpoint (`/history/observed`)* — duplicates the currency, range-validation and
  normalisation plumbing, and splits the additive window fields across two contracts.

---

## R2 — Clipping observed-only output to the requested range

**Decision**: `ObservedOnlyFiller` sorts, de-duplicates by date, and filters to
`from_date <= d <= to_date`. It does not drop weekend-dated observations.

**Rationale**: `LocalPricingProvider.get_price_history` ignores the range entirely and returns every
row in the CSV (today the range clip is an incidental side effect of `GapFillService`'s `from`→`to`
loop). Without an explicit clip, `fill=none` would leak out-of-range fallback rows — the exact failure
in the "Fallback file rows outside the requested range are excluded" scenario. Keeping weekend
observations is deliberate: a real observation dated Saturday is still an observation (spec Edge Cases),
and only the business-day *grid* is a gap-fill construct.

**Alternatives rejected**: *Clipping inside `LocalPricingProvider`* — would change behaviour for the
existing `fill=all` path and risks altering today's fallback responses, which FR-003 requires to stay
identical.

---

## R3 — Where the observation window comes from

**Decision**: Add a narrow, optional capability protocol `ObservationWindowSource` with
`observation_window(ticker) -> ObservationWindow | None`, implemented by `CachedPricingProvider`
(from the cache file's first/last row) and `FallbackPricingProvider`/`LocalPricingProvider` (from the
CSV's first/last row), and delegated through the decorator chain. `PricingService` queries it
**after** fetching history, and falls back to deriving the extremes from the raw series it just
received when the provider does not offer the capability.

**Rationale**:

- `CachedPricingProvider` writes the merged series to disk *before* returning, so reading the cache
  extremes after the fetch automatically reports the widened window required by FR-015 with no extra
  bookkeeping.
- Making the capability a separate protocol rather than a new `PricingProvider` abstract method
  honours Interface Segregation: `YFinanceProvider` genuinely cannot answer "what is this
  instrument's full known history", and should not be forced to pretend.
- The raw-series fallback keeps the existing test doubles (`MagicMock(spec=PricingProvider)`) working
  unchanged, which protects the "existing suite passes unchanged" success criterion (SC-003).

**Alternatives rejected**:

- *Adding `observation_window` to the `PricingProvider` ABC* — forces a meaningless implementation on
  `YFinanceProvider` and breaks every existing `MagicMock(spec=PricingProvider)` fixture.
- *Returning the window from `get_price_history` as a richer result object* — a breaking change to the
  provider contract used by four providers and the FX path, for a field only one endpoint needs.
- *Probing the data source for the instrument's full lifetime* — turns every request into an
  unbounded fetch. The spec scopes the fields to "as far as the service knows" precisely to avoid this.

---

## R4 — How the no-earlier-data boundary is stored

**Decision**: A per-ticker sidecar JSON file in the existing cache directory,
`{sanitised-ticker}.meta.json`, holding `{"no_data_before": "YYYY-MM-DD"}`. Written atomically
(temp file + `os.replace`) exactly as the CSV is. `CacheRepository.delete` removes the sidecar
alongside the CSV, and `delete_all` globs `*.meta.json` in addition to `*.csv`.

**Rationale**:

- Satisfies FR-023 (survives restart, dies with the stored history) with no new dependency and no
  schema migration: a missing sidecar simply means "no boundary known".
- Reuses `CacheRepository._filename`'s existing character sanitisation, so tickers like `0P0000X3IE.L`
  and `^FTSE` are handled identically to their CSVs.
- Keeping it out of the CSV preserves the cache file's `date,close` contract, which the
  cache-management endpoints and existing tests read directly.
- `delete_all` currently globs `*.csv`; `*.meta.json` does not match that glob, so the sidecar must be
  added explicitly — noted as a concrete code change rather than an assumption.

**Alternatives rejected**:

- *One shared index file for all tickers* — every write becomes a read-modify-write of a global file,
  and `DELETE /cache/{ticker}` would need to rewrite it. Worse atomicity for no benefit.
- *A sentinel row or comment inside the CSV* — pollutes the price data contract and would be parsed
  as a price by any naive reader.
- *In-memory only* — fails FR-023; the saving would evaporate on every restart, and the service is
  restarted frequently in local development.

---

## R5 — Boundary record, skip and invalidate logic

**Decision**: All three behaviours live in `CachedPricingProvider.get_price_history`, which already
owns segment planning:

| Situation | Action | Log event |
|---|---|---|
| `before` segment would be fetched, boundary exists and `boundary <= cached_min` | skip the fetch | `cache_no_earlier_data_skip` |
| `before` fetch returns no rows | record `no_data_before = cached_min` | `cache_no_earlier_data_recorded` |
| `before` fetch returns rows starting at `new_earliest` | record `no_data_before = new_earliest` (replacing any existing boundary) | `cache_no_earlier_data_invalidated` |
| Cold cache populate returns rows starting after `from_date` | record `no_data_before = first fetched date` | `cache_no_earlier_data_recorded` |
| Cache CSV holds a row earlier than an existing boundary | delete the boundary | `cache_no_earlier_data_invalidated` |

**Rationale**:

- Recording on the **cold populate** path matters more than the warm path: the first long-lookback
  request is the one that pays the full cost, and without this the saving would not arrive until the
  third request. The inference is sound — the source was asked for `[from_date, to_date]` and returned
  nothing before `first fetched date`.
- Moving the boundary forward on a successful earlier fetch (rather than just deleting it) is both
  what the spec's invalidation scenario asserts and strictly more useful: the source was asked for the
  whole earlier segment and returned nothing before `new_earliest`.
- Only the `before` segment is guarded. The `after` segment is deliberately never suppressed
  (FR-020) because new observations legitimately arrive at the recent end every day.
- `_fetch_segment` already swallows `DataNotFoundError` into an empty list and re-raises
  `ProviderUnavailableError`, so "no data" and "source down" are already distinguishable at the exact
  point the boundary decision is made — a provider outage must never be recorded as "no data exists".

**Alternatives rejected**:

- *Putting the logic in `CacheRepository`* — the repository is a dumb persistence boundary; segment
  planning and provider-outcome interpretation belong in the provider decorator (Single Responsibility).
- *Guarding both ends with one mechanism* — would stop the service ever picking up new prices.

---

## R6 — Currency conversion under `fill=none`

**Decision**: No change to the conversion algorithm. `CurrencyService.translate_history` already
fetches FX for the requested range, gap-fills it via `GapFillService`, and aligns it to
`[p.date for p in records]`. With an observed-only `records` list, each observed date is therefore
converted at that date's gap-filled rate — precisely FR-025 — and no new dates can appear, because the
output list is built by iterating `records` (FR-026). The only required change is that
`build_translated_history` must copy the two new window fields into the `PriceHistoryResponse` it
constructs, instead of dropping them.

**Rationale**: The existing `FxAligner` forward-fills (then back-fills) to the nearest available rate,
so a missing raw rate on an observation date cannot drop the observation — it resolves to the carried
rate. This is already the behaviour the spec asks to preserve, verified by reading `fx_aligner.py`.

**Alternatives rejected**: *Passing the fill mode into `CurrencyService`* — it would have no effect on
the algorithm and would wrongly imply FX rates should also stop being filled.

---

## R7 — Rejecting an invalid `fill` value without calling the data source

**Decision**: Type the query parameter as the `FillMode` enum. FastAPI/Pydantic validate it during
request parsing and return a 422 naming `fill` in `loc`, before the endpoint body — and therefore
before any provider call — executes. No hand-written validator is needed.

**Rationale**: Matches how `_TICKER_PATTERN` and the date params are already validated in
`app/api/securities.py`, and FR-004's "MUST NOT call the data source" is satisfied structurally rather
than by discipline. `enum.StrEnum` is available (project requires Python 3.11+; the local venv runs
3.14) and serialises cleanly into the OpenAPI schema as an enumerated string.

**Alternatives rejected**: *A `str | None` parameter with a manual check raising `InvalidTickerError`* —
reuses an unrelated exception type and produces a less precise error body than the standard
`HTTPValidationError` existing consumers already handle.

---

## R8 — Empty result handling (contract alignment)

**Decision**: `PricingService.get_price_history` raises `DataNotFoundError` when the post-fill series
is empty, in both modes.

**Rationale**: FR-009 requires 404 in both modes, and feature 006's FR-008 already stated this
contract. Today there is a gap between contract and code: when a cache file exists but holds nothing
inside the requested range, `CachedPricingProvider` returns `[]` without raising, `GapFillService`
returns `[]`, and the endpoint answers 200 with an empty `prices` list. Closing that gap is required
for `fill=none` (where an out-of-range request is common) and brings `fill=all` into line with its own
documented contract.

**Risk check**: a grep of `tests/` found no assertion of a 200-with-empty-`prices` response, so this is
not expected to break the existing suite. It is nonetheless a behaviour change on an edge case for
`fill=all`, so it is called out explicitly in `plan.md` rather than buried here.

**Alternatives rejected**: *200 with an empty list under `fill=none` only* — would make the two modes
disagree on the same underlying "nothing to return" condition and contradict FR-009.

---

## Technology choices summary

No new runtime dependencies. The feature is built from what the project already pins: `fastapi`,
`pydantic` v2, `structlog`, `pytest` + `pytest-bdd`, plus the standard library (`enum.StrEnum`,
`json`, `os.replace`, `typing.Protocol`). Dependency hygiene under constitution principle II is
therefore satisfied by adding nothing.
