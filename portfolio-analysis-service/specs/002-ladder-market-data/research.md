# Phase 0 Research: Ladder Market Data Enrichment

No `NEEDS CLARIFICATION` markers remain in the Technical Context (all resolved via
`/speckit-clarify` before planning began, plus direct inspection of the existing codebase). This
document records the resulting decisions and the evidence behind them.

## 1. HTTP client for calling `market-data-web-service`

**Decision**: Use `httpx.Client` synchronously from within `PricingEnrichmentService`, called
from the existing synchronous `IngestionService.ingest()` method (itself invoked from an async
FastAPI route handler without `await`, exactly as `pandas`/`openpyxl` I/O already is in feature
001).

**Rationale**: `httpx` is already a dependency of this project (currently dev-only, used to
drive FastAPI's `TestClient`). Promoting it to a runtime dependency avoids introducing a new
third-party library. Keeping the call synchronous is consistent with the rest of
`IngestionService`, which already performs blocking pandas/file I/O inside a sync method called
from an async endpoint — introducing `httpx.AsyncClient` here would be architecturally
inconsistent for no real benefit at this service's scale (single user, local instance).

**Alternatives considered**: `requests` (rejected — new dependency, no async story, no benefit
over httpx); `httpx.AsyncClient` (rejected — would require threading async through
`IngestionService`/`LadderExpander`, which are synchronous today, for no measurable gain at this
scale).

## 2. Testing the market-data-service HTTP boundary

**Decision**: Fake `market-data-web-service` responses in tests using `httpx.MockTransport`
(built into `httpx`), injected into `HttpMarketDataClient` via a custom `transport=` argument.

**Rationale**: Avoids adding `respx` or standing up a real second FastAPI instance in the test
suite. `httpx.MockTransport` lets tests assert exactly how many requests were made (needed for
SC-003's "one request per sub-account" guarantee) and control response bodies precisely
(including simulating gaps for the fail-fast scenarios).

**Alternatives considered**: `respx` (rejected — new dependency for something `httpx` already
provides); running a real `market-data-web-service` instance in tests (rejected — slow, couples
this service's test suite to another repository's runtime, and only `run_end_to_end.ps1` needs
that level of integration).

## 3. Why "missing price" will be rare in practice (informs FR-008 implementation)

**Finding**: `market-data-web-service`'s `PricingService` already runs every price history
through `GapFillService.fill()` (see `market-data-web-service/app/services/gap_fill.py`), which
back-fills any date before the first observation with that first observation's price, and
forward-fills every subsequent Mon–Fri gap. Consequently, a `/securities/{ticker}/history`
response for a valid, actively-tracked ticker will already contain **every** business day in the
requested range — including UK/exchange holidays that this service's own ladder does not exclude
(per feature 001's assumption that only weekends are excluded, no holiday calendar is applied).

**Decision**: `PricingEnrichmentService` still performs its own coverage check per FR-008
(comparing the ladder's business-day range for a sub-account against the dates actually present
in the response) — this is a correctness guarantee, not a redundant one. In practice, given the
upstream gap-fill, a coverage failure will primarily surface for genuinely unresolvable cases:
an identifier with zero historical observations at all (invalid ticker, nothing ever traded), or
a native-currency-to-GBP FX translation that the market-data-service cannot satisfy
(`CurrencyUnavailableError` upstream). Ordinary market holidays will NOT trigger failures because
the upstream gap-fill already covers them before this service ever sees the response.

**Rationale for documenting this**: It resolves what would otherwise look like a design flaw
(every ladder spanning a bank holiday would seem doomed to fail) and clarifies that the fail-fast
behaviour specified in FR-008 is a safety net for real data problems, not a routine occurrence.

## 4. Ticker vs. ISIN precedence

**Decision** (from `/speckit-clarify`): When a mapping entry has both `ticker` and `isin`
populated, `ticker` is used to call `market-data-web-service`; `isin` is only used when `ticker`
is absent.

**Rationale**: `market-data-web-service`'s `/securities/{ticker}/history` endpoint is
ticker-oriented and backed by `yfinance`, which is far more reliable when given an actual ticker
symbol than an ISIN. Preferring ticker also guarantees exactly one request per sub-account (no
implicit `/identifiers/{isin}` resolution hop first).

## 5. Currency handling

**Decision**: Every price-history request explicitly sets `currency=GBP` as a query parameter.
No FX conversion is performed within `portfolio-analysis-service` itself — it relies entirely on
`market-data-web-service`'s existing `CurrencyService` to translate the security's native
currency into GBP server-side (confirmed present in `app/api/securities.py`'s
`get_price_history` endpoint).

**Rationale**: Duplicating FX conversion logic in this service would violate Single
Responsibility and risk divergent FX rates between the two services. `market-data-web-service`
already owns this concern.

## 6. Response status enum: rename `"unchanged"` → `"refreshed"`

**Decision**: `IngestionSummary.status` changes from `Literal["created", "unchanged"]` to
`Literal["created", "refreshed"]` — a rename, not an additive third value.

**Rationale**: Per FR-013 (from `/speckit-clarify`), a checksum-unchanged re-submission now
always re-runs price enrichment via fresh market-data calls; it is never a true no-op anymore.
The concept `"unchanged"` therefore no longer describes any real code path — keeping it alongside
a new `"refreshed"` value would leave a dead enum member and ambiguity about which value a
checksum match produces. This is a breaking response-schema change, judged acceptable because the
API is pre-1.0 and locally hosted with no external consumers yet (consistent with feature 001
having no versioning/compatibility guarantees beyond the `/v1/` prefix).

**Alternatives considered**: Adding `"refreshed"` as a third value alongside `"created"` and
`"unchanged"` (rejected — `"unchanged"` would become unreachable dead code, which fails
Constitution III's "no unreachable code" static-analysis gate in spirit even though `ruff`/`mypy`
cannot detect an unreachable *enum value*).

## 7. Refresh path: re-enrich without re-expanding

**Decision**: On a checksum match, `IngestionService` reads back the existing stored ladder via
a new `LadderRepository.read_ladder_df()` method, re-runs `PricingEnrichmentService` against
those existing base rows (`date`, `sub_account`, `book_cost`, `quantity`, `total_income`), and
overwrites `ladder.xlsx` with the refreshed `price`/`market_value`/`portfolio_weight` values. The
uploaded file's bytes are not re-parsed and `LadderExpander` is not re-invoked.

**Rationale**: FR-013 explicitly requires the underlying rows and date range to remain
unexpanded on refresh; re-parsing the uploaded file would risk silently producing a different
row set if `today` has advanced since the original ingestion (the T-2 boundary in
`LadderExpander` is relative to "today"), which would contradict "without re-expanding."

## 8. Floating-point tolerance for weight-sums-to-1.0

**Decision**: Use a tolerance of `0.0001` (already recorded as an assumption in spec.md),
implemented via `math.isclose(total, 1.0, abs_tol=0.0001)` in production code and
`pytest.approx(1.0, abs=0.0001)` in tests.

**Rationale**: Matches SC-002 exactly; avoids brittle exact-equality floating-point assertions.
