# Phase 0 Research: YFinance Price Data Cache

**Branch**: `003-yfinance-cache` | **Date**: 2026-05-08

## Decision Log

---

### Cache File Format

**Decision**: CSV files via Python standard library (`csv` module + `datetime`)

**Rationale**:
- Zero new production dependencies — `csv` and `datetime` are built-in
- Human-readable and debuggable (operators can inspect cache files directly)
- Sufficient for a single-user personal portfolio tool; no performance bottleneck expected
- Keeps the web service lean — analytics-weight libraries (pandas, pyarrow) belong in the analysis tool, not the API

**Alternatives considered**:
- Apache Parquet (pandas + pyarrow): efficient and used in the parent portfolio tool, but adds heavy production dependencies to a small API; rejected
- JSON: no additional dependencies, but produces larger files and lacks the columnar structure of tabular price data; rejected
- SQLite: robust and queryable, but over-engineered for a single-record-per-ticker lookup; rejected

**File schema**:
```
date,close
2025-01-02,189.30
2025-01-03,188.50
```
- `date`: ISO 8601 `YYYY-MM-DD` string
- `close`: float64 closing price

**File naming**: `{ticker}.csv` within the configured cache directory. Tickers with characters invalid in filenames (e.g. `^`, `/`) are escaped by replacing with `_`; the ticker value itself is preserved in the data.

---

### Configuration Format

**Decision**: YAML file (`config.yaml`) at the project root, parsed with PyYAML

**Rationale**:
- PyYAML is already present in the venv (pyyaml 6.0.3)
- YAML is human-readable and supports structured hierarchy (`cache.directory`) naturally
- A named file is unambiguous as a "configuration file" per the spec's language (FR-001)
- pyyaml will be added to `pyproject.toml` as an explicit pinned dependency

**Alternatives considered**:
- `.env` + python-dotenv: environment variable pattern, already in venv, but flat-key format is less expressive for structured config and feels like deployment config rather than application config; rejected
- `config.json`: no extra dependency, but YAML is more author-friendly; rejected
- `pyproject.toml` extra section: couples app config to build config; rejected

**Config schema**:
```yaml
cache:
  directory: ./cache
```

**Settings class**: Pydantic `BaseModel` in `app/config.py`, loaded once at startup via the FastAPI `lifespan` context and exposed through a `get_settings()` FastAPI dependency.

---

### Architecture Pattern for Cache Layer

**Decision**: Decorator pattern — `CachedPricingProvider` wraps the existing `PricingProvider` interface

**Rationale**:
- Open/Closed Principle: extends `get_price_history` behaviour without modifying `YFinanceProvider`
- Liskov Substitution: `CachedPricingProvider` implements `PricingProvider` and is fully substitutable
- Dependency Inversion: `CachedPricingProvider(inner: PricingProvider, repo: CacheRepository)` — both injected, never instantiated internally
- `get_current_price` is passed through unchanged (spec does not require caching of current prices)
- `CacheRepository` is a separate, single-responsibility class for all filesystem I/O

**Alternatives considered**:
- Separate `CacheService` sitting beside `PricingService`: adds an extra orchestration layer with no additional benefit for this feature's scope; rejected
- Modifying `YFinanceProvider` directly: violates Open/Closed; rejected
- Middleware / FastAPI dependency: cache logic is not HTTP-layer concern; rejected

---

### Cache Coverage Algorithm

**Decision**: Compare requested date range against actual min/max dates present in the cache CSV

**Rationale**:
- Implements FR-013 — stored bounds reflect real trading-day data, not calendar dates of the original request
- Prevents false partial-hits at weekends/holidays: if the cache's max date is a Friday and the request ends on the following Sunday, no YFinance call is needed
- Simple to implement: `cached_min = min(row dates)`, `cached_max = max(row dates)`; two comparisons determine which segments (before-cache, after-cache) are missing

**Missing-segment identification**:
```
if from_date < cached_min → missing segment: [from_date, cached_min - 1 day]
if to_date   > cached_max → missing segment: [cached_max + 1 day, to_date]
```
Up to two segments per request; each fetched independently from YFinance.

**Post-fetch merge**:
1. Append new rows to existing cache data (in-memory dict keyed by date)
2. Deduplicate by date (last-write-wins per FR assumption)
3. Sort ascending by date
4. Write merged result to CSV (atomic: write temp file, rename)

---

### YFinance Failure Handling

**Decision**: Raise `ProviderUnavailableError` for the entire request; do not persist partial data

**Rationale**: FR-012 — callers must receive either complete data or an explicit error; no silent partial responses. The cache file for the ticker is left unchanged when a YFinance fetch fails.

**Implementation**: `CachedPricingProvider.get_price_history` propagates any `ProviderUnavailableError` or `DataNotFoundError` raised by the inner provider; the cache write step is only reached if all segments are fetched successfully.

---

### New API Endpoints

**Decision**: Add a `/cache` router at `app/api/cache.py`

- `DELETE /cache/{ticker}` — removes `{ticker}.csv` from the cache directory; returns 200 if deleted, 404 if not found
- `DELETE /cache` — removes all `*.csv` files from the cache directory; returns 200 with count

**Rationale**:
- Separate router follows the existing pattern (`app/api/securities.py`)
- Distinct prefix `/cache` keeps cache management separate from securities data endpoints
- Standard HTTP DELETE semantics; idempotent on the "all" endpoint (empty cache → 0 deleted, no error)

---

### New Production Dependencies

| Package | Version Pin | Reason |
|---------|-------------|--------|
| `pyyaml` | `>=6.0` | Parse `config.yaml`; already in venv as transitive dep, now explicit |

No other new production dependencies. `pandas` is intentionally excluded from the web service's production deps.

### Test Dependencies (no change)

pytest-bdd, pytest, httpx already cover all new BDD scenarios.
