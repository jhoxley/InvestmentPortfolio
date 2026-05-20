# Research: Local Price File Fallback

**Feature**: 007-local-price-fallback  
**Phase**: 0 — Pre-design research  
**Date**: 2026-05-20

---

## Decision 1: Component Pattern for Fallback Interception

**Decision**: Implement fallback using the Decorator/Wrapper pattern — `FallbackPricingProvider` wraps the existing `CachedPricingProvider(YFinanceProvider())` chain and intercepts `DataNotFoundError`.

**Rationale**: The Open/Closed principle (Constitution I) requires new behaviour to be added by extension, not by modifying existing stable code. The existing `YFinanceProvider`, `CachedPricingProvider`, and `PricingService` are unmodified. `FallbackPricingProvider` satisfies `PricingProvider` (Liskov Substitution) and delegates to the existing chain, intercepting only the failure case.

**Alternatives considered**:
- Modifying `PricingService.get_price_history()` to catch `DataNotFoundError` and call a fallback — rejected because it violates SRP (pricing service would gain config-lookup responsibility) and OCP (modifying existing stable code).
- Adding a fallback flag to `YFinanceProvider` — rejected for the same OCP reason.

---

## Decision 2: Identifier Resolution Fallback Pattern

**Decision**: `FallbackIdentifierProvider` wraps `YFinanceIdentifierProvider` and intercepts `IdentifierNotFoundError`. When the fallback config has an entry matching the identifier, it returns the identifier itself as a pseudo-ticker with a synthetic response.

**Rationale**: Same decorator pattern as Decision 1, consistent across both provider hierarchies. `IdentifierProvider` ABC is already defined; `FallbackIdentifierProvider` is a valid implementor.

**Alternatives considered**:
- Modifying `IdentifierService.resolve()` — rejected (SRP/OCP violation).
- Adding fallback lookup to the existing `YFinanceIdentifierProvider` — rejected (single-responsibility violation; YFinance provider should not know about local config).

**Synthetic response format**: When returning a pseudo-ticker, the response fields `security_name` and `exchange` are set to `""` (empty string) since no YFinance data exists. This satisfies `TickerResolutionResponse` contract (both are `str`, not optional).

---

## Decision 3: Fallback Configuration Storage and Loading

**Decision**: JSON file on the local filesystem whose path is configured via `Settings.fallback.config_path` (a new `FallbackSettings` nested model). The file is read on each request — no in-memory caching.

**Rationale**: SC-005 requires operators to add a new fallback ticker by editing the configuration file without restarting the service. Reading on each request is the simplest mechanism that satisfies this requirement. The config file is small (tens to hundreds of entries at most) and JSON parsing is fast; no performance concern at the expected request rate.

**Format**: Dict keyed by identifier (case-insensitive lookup normalised to uppercase), each value is a `FallbackEntry` object:

```json
{
  "PRIV01": {
    "csv_path": "/data/prices/priv01.csv",
    "currency": "GBP",
    "date_column": "Date",
    "price_column": "Close",
    "use_local_only": false
  },
  "GB00B0PRVT01": {
    "csv_path": "/data/prices/gb00b0prvt01.csv",
    "currency": "GBP",
    "date_column": "Date",
    "price_column": "Price",
    "use_local_only": true
  }
}
```

**Alternatives considered**:
- YAML config — rejected; JSON is already used throughout the project; `json` is a stdlib module with no added dependency.
- TTL-based in-memory cache — rejected; unnecessary complexity for the expected config file size and request rate.
- Environment variable per entry — rejected; does not scale past a handful of entries and is not operator-friendly.

---

## Decision 4: CSV Reading and Date Parsing

**Decision**: Use `pandas.read_csv()` to load the CSV file and extract the configured date and price columns by name. For date parsing, use `python-dateutil`'s `dateutil.parser.parse()` applied to each cell. `python-dateutil` is already a transitive dependency of `yfinance` and therefore already installed.

**Rationale**: `pandas` is already a first-class dependency of the project. `pd.read_csv()` handles quoting, encoding, and extra columns cleanly; no bespoke CSV parser needed (Constitution II). `dateutil.parser.parse()` handles all common date formats (ISO 8601, UK/US date styles, partial dates) without requiring the operator to specify a format string, satisfying FR-006 (auto-detect from first row). Pandas' `parse_dates` argument is not used — instead the date column is read as string and parsed with dateutil, which gives clearer error messages and consistent format application.

**Alternatives considered**:
- `csv.DictReader` (stdlib) — rejected; doesn't handle encoding, quoting, or column extraction as cleanly as pandas; bespoke logic would be needed.
- `datetime.strptime` with explicit format detection — rejected; inferring a `strptime` format string from a parsed `datetime` object requires a list of candidate formats and a matching loop; dateutil is simpler and more reliable.

---

## Decision 5: Cache Bypass Mechanism

**Decision**: `FallbackPricingProvider` calls `LocalPricingProvider` directly (a new internal provider instance). `LocalPricingProvider` is never passed through `CachedPricingProvider`. The existing cache layer only sees traffic that goes to the YFinance path.

**Rationale**: FR-003 requires fallback data never to be written to or served from the price cache. The simplest mechanism is structural: the local provider is never wrapped in `CachedPricingProvider`. No additional "skip cache" flag or conditional is needed. The `CachedPricingProvider` is unchanged.

---

## Decision 6: Error Mapping for Fallback File Problems

**Decision**:
- Missing or unreadable CSV file → raise `ProviderUnavailableError` (maps to HTTP 503).
- CSV file exists but has zero data rows (headers only) → raise `DataNotFoundError` (maps to HTTP 404).

**Rationale**: Matches the error taxonomy already established: `ProviderUnavailableError` = infrastructure/configuration problem (operator must fix it), `DataNotFoundError` = the ticker has no data in the available source. Both exceptions are already handled by the existing error middleware and map to the correct HTTP status codes without any new exception types or handler modifications.

---

## Decision 7: use_local_only Check Point

**Decision**: `FallbackPricingProvider` checks `use_local_only` at the start of each call, before calling the inner (YFinance/cache) provider. If `True`, it constructs `LocalPricingProvider` and returns its result immediately.

**Rationale**: For assets known in advance to be unavailable on YFinance, skipping the remote call saves latency and avoids unnecessary `DataNotFoundError` handling. This is also more observable (a log entry can note "local_only bypass" vs "YFinance fallback triggered").

---

## Decision 8: FallbackSettings Config Path Default

**Decision**: `FallbackSettings.config_path` defaults to `None`. When `None`, `FallbackConfigRepository` treats the fallback config as empty (no entries configured); all requests flow to YFinance as before. This makes the feature fully backwards-compatible — services without a fallback config file continue to work without modification.

**Alternatives considered**:
- Default to `./fallback_config.json` — rejected; would cause an error on startup or first request if the file does not exist, breaking existing deployments that don't use this feature.

---

## Dependency Review

| Dependency | Status | Notes |
|------------|--------|-------|
| `pandas` | Already installed | Used for `pd.read_csv()` |
| `python-dateutil` | Already installed (transitive) | Used for `dateutil.parser.parse()` |
| `pydantic` | Already installed | `FallbackSettings` model |
| `json` (stdlib) | Built-in | Config file loading |
| `pathlib` (stdlib) | Built-in | CSV path resolution |

No new dependencies required.
