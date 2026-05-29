# Implementation Plan: Local Price File Fallback

**Branch**: `007-local-price-fallback` | **Date**: 2026-05-20 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `specs/007-local-price-fallback/spec.md`

## Summary

When the primary market data source (YFinance) returns no data for a ticker, the service now checks a local JSON configuration file for a matching fallback entry and serves price data from a configured CSV file instead. The fallback is triggered by `DataNotFoundError` (empty results or unknown ticker) — never by infrastructure errors. Cache bypass is structural: the local provider is never wrapped in `CachedPricingProvider`. All existing gap-fill and FX conversion pipelines apply identically to fallback data. The identifier resolution endpoint also consults the fallback config when YFinance cannot resolve an ISIN/CUSIP/SEDOL, returning the identifier as a pseudo-ticker.

## Technical Context

**Language/Version**: Python 3.12  
**Primary Dependencies**: FastAPI, pydantic, pandas, python-dateutil (transitive via yfinance), structlog  
**Storage**: Local filesystem — JSON config file (operator-managed), CSV price files (operator-managed)  
**Testing**: pytest, pytest-bdd, BDD feature files (Gherkin)  
**Target Platform**: Linux/Windows server (same as existing service)  
**Project Type**: Web service  
**Performance Goals**: Identical to existing service; local file reads add negligible latency  
**Constraints**: No new dependencies; backwards-compatible when `fallback.config_path` is not set  
**Scale/Scope**: Tens to hundreds of fallback entries per config; CSV files with hundreds to thousands of rows

## Constitution Check

| Principle | Check | Notes |
|-----------|-------|-------|
| I. SOLID Design | ✅ New wrapper classes (`FallbackPricingProvider`, `FallbackIdentifierProvider`, `LocalPricingProvider`, `FallbackConfigRepository`); no existing stable classes modified; all dependencies injected | |
| II. Standard Dependencies | ✅ `pandas` (existing dep) for CSV; `dateutil` (transitive dep) for date parsing; `json` stdlib for config; no new package installs | |
| III. BDD Test-First | ✅ `.feature` files authored and confirmed failing before implementation tasks begin | |
| IV. Code Quality Standards | ✅ Existing `ruff` + `mypy --strict` config applies; all new modules fully type-annotated | |
| V. Observability & Logging | ✅ `structlog` log entries for: fallback triggered, use_local_only bypass, CSV read start/success/failure, pseudo-ticker resolution | |
| VI. OpenAPI-First | ✅ `openapi.yaml` description updates applied before endpoint wiring (no schema changes required) | |

## Project Structure

### Documentation (this feature)

```text
specs/007-local-price-fallback/
├── plan.md              ← this file
├── research.md          ← Phase 0 decisions
├── data-model.md        ← entity definitions and relationships
├── quickstart.md        ← integration scenario guide and fixture list
├── contracts/
│   ├── openapi-changes.md          ← diff of openapi.yaml changes
│   └── fallback-config.schema.json ← JSON Schema for config file
└── tasks.md             ← Phase 2 output (/speckit-tasks command)
```

### Source Code (additions and modifications)

```text
app/
├── models/
│   └── fallback.py              NEW — FallbackEntry dataclass (Pydantic model)
├── repositories/
│   └── fallback_config.py       NEW — FallbackConfigRepository (loads JSON config)
├── providers/
│   ├── local_provider.py        NEW — LocalPricingProvider (reads CSV, implements PricingProvider)
│   ├── fallback_provider.py     NEW — FallbackPricingProvider (wraps inner, intercepts DataNotFoundError)
│   └── identifier_provider.py   MODIFY — add FallbackIdentifierProvider class (wraps YFinanceIdentifierProvider)
├── config.py                    MODIFY — add FallbackSettings, update Settings
└── api/
    ├── securities.py             MODIFY — use FallbackPricingProvider in get_pricing_service()
    └── identifiers.py            MODIFY — use FallbackIdentifierProvider in get_identifier_service()

openapi.yaml                     MODIFY — description updates + FallbackConfigEntry schema

tests/
├── features/
│   ├── local_price_fallback_history.feature    NEW — US1 scenarios
│   ├── local_price_fallback_current.feature    NEW — US2 scenarios
│   └── local_price_fallback_fx.feature         NEW — US3 scenarios
├── steps/
│   ├── local_price_fallback_history_steps.py   NEW
│   ├── local_price_fallback_current_steps.py   NEW
│   └── local_price_fallback_fx_steps.py        NEW
├── fixtures/
│   ├── priv01_prices.csv                        NEW — 2 observations: 2025-01-02, 2025-01-06
│   ├── priv_isin_prices.csv                     NEW — 1 observation: 2025-01-02
│   ├── priv01_empty.csv                         NEW — headers only
│   ├── fallback_config.json                     NEW — PRIV01 → priv01_prices.csv (GBP)
│   ├── fallback_config_isin.json                NEW — GB00B0PRVT01 → priv_isin_prices.csv (GBP, use_local_only)
│   ├── fallback_config_local_only.json          NEW — PRIV01 with use_local_only: true
│   └── fallback_config_missing_file.json        NEW — PRIV01 → /nonexistent/path/priv01.csv
└── conftest.py                                  MODIFY — add fallback-aware client fixtures
```

## Implementation Design

### New Classes

#### `app/models/fallback.py`

```python
class FallbackEntry(BaseModel):
    csv_path: Path
    currency: str  # validated: ^[A-Z]{3}$
    date_column: str
    price_column: str
    use_local_only: bool = False
```

#### `app/repositories/fallback_config.py`

```python
class FallbackConfigRepository:
    def __init__(self, config_path: Path | None) -> None: ...
    def lookup(self, identifier: str) -> FallbackEntry | None:
        # normalise identifier to uppercase; re-read JSON each call
        # return None if config_path is None or identifier not found
```

#### `app/providers/local_provider.py`

```python
class LocalPricingProvider(PricingProvider):
    def __init__(self, entry: FallbackEntry) -> None: ...

    def get_price_history(self, ticker: str, from_date: date, to_date: date
                          ) -> list[tuple[date, float]]:
        # pd.read_csv(entry.csv_path)
        # extract entry.date_column and entry.price_column
        # parse dates with dateutil.parser.parse(); filter price > 0
        # return sorted list (no range filtering — GapFillService handles that upstream)
        # raise ProviderUnavailableError if file unreadable
        # raise DataNotFoundError if no valid rows

    def get_current_price(self, ticker: str) -> dict[str, object]:
        # call get_price_history with wide range; take last entry
        # return {"price": ..., "as_of_date": ..., "currency": entry.currency, "market_state": None}
```

#### `app/providers/fallback_provider.py`

```python
class FallbackPricingProvider(PricingProvider):
    def __init__(self, inner: PricingProvider,
                 fallback_repo: FallbackConfigRepository) -> None: ...

    def get_price_history(self, ticker: str, from_date: date, to_date: date
                          ) -> list[tuple[date, float]]:
        entry = self._fallback_repo.lookup(ticker)
        if entry is None:
            return self._inner.get_price_history(ticker, from_date, to_date)
        if entry.use_local_only:
            return LocalPricingProvider(entry).get_price_history(ticker, from_date, to_date)
        try:
            return self._inner.get_price_history(ticker, from_date, to_date)
        except DataNotFoundError:
            return LocalPricingProvider(entry).get_price_history(ticker, from_date, to_date)

    def get_current_price(self, ticker: str) -> dict[str, object]:
        # identical pattern
```

#### `FallbackIdentifierProvider` (in `app/providers/identifier_provider.py`)

```python
class FallbackIdentifierProvider(IdentifierProvider):
    def __init__(self, inner: IdentifierProvider,
                 fallback_repo: FallbackConfigRepository) -> None: ...

    def lookup_ticker(self, identifier: str, identifier_type: str) -> dict[str, object]:
        try:
            return self._inner.lookup_ticker(identifier, identifier_type)
        except IdentifierNotFoundError:
            entry = self._fallback_repo.lookup(identifier)
            if entry is None:
                raise
            return {"ticker": identifier, "security_name": "", "exchange": ""}
```

### Modified Factories

#### `app/api/securities.py` — `get_pricing_service()`

```python
def get_pricing_service(settings: Settings = Depends(get_settings)) -> PricingService:
    repo = CacheRepository(settings.cache.directory)
    yf_provider = CachedPricingProvider(YFinanceProvider(), repo)
    fallback_repo = FallbackConfigRepository(settings.fallback.config_path)
    provider = FallbackPricingProvider(inner=yf_provider, fallback_repo=fallback_repo)
    return PricingService(provider=provider, gap_fill=GapFillService())
```

#### `app/api/identifiers.py` — `get_identifier_service()`

```python
def get_identifier_service(settings: Settings = Depends(get_settings)) -> IdentifierService:
    fallback_repo = FallbackConfigRepository(settings.fallback.config_path)
    provider = FallbackIdentifierProvider(
        inner=YFinanceIdentifierProvider(),
        fallback_repo=fallback_repo,
    )
    return IdentifierService(provider=provider)
```

### Modified Config

#### `app/config.py`

```python
class FallbackSettings(BaseModel):
    config_path: Path | None = None

class Settings(BaseModel):
    cache: CacheSettings = CacheSettings()
    fallback: FallbackSettings = FallbackSettings()
```

## Complexity Tracking

No constitution violations. All new behaviour is added by extension (new classes). Existing stable classes are unchanged except for the two factory functions in `api/securities.py` and `api/identifiers.py` which compose the new providers.

## Logging Plan (Constitution V)

| Event | Level | Fields |
|-------|-------|--------|
| Fallback triggered (DataNotFoundError from inner) | INFO | `event="fallback_triggered"`, `ticker`, `fallback_path` |
| use_local_only bypass | INFO | `event="local_only_bypass"`, `ticker`, `fallback_path` |
| CSV file read start | DEBUG | `event="local_csv_read_start"`, `ticker`, `path` |
| CSV file read success | DEBUG | `event="local_csv_read_ok"`, `ticker`, `path`, `row_count` |
| CSV file not found | ERROR | `event="local_csv_not_found"`, `ticker`, `path` |
| CSV file empty | WARNING | `event="local_csv_empty"`, `ticker`, `path` |
| Fallback config load | DEBUG | `event="fallback_config_loaded"`, `path`, `entry_count` |
| Identifier pseudo-ticker returned | INFO | `event="identifier_fallback_resolved"`, `identifier`, `ticker` |

## Test Fixtures

### `tests/fixtures/priv01_prices.csv`
```csv
Date,Close
2025-01-02,100.00
2025-01-06,110.00
```

### `tests/fixtures/priv01_empty.csv`
```csv
Date,Close
```

### `tests/fixtures/priv_isin_prices.csv`
```csv
Date,Close
2025-01-02,150.00
```

### `tests/fixtures/fallback_config.json`
```json
{
  "PRIV01": {
    "csv_path": "tests/fixtures/priv01_prices.csv",
    "currency": "GBP",
    "date_column": "Date",
    "price_column": "Close",
    "use_local_only": false
  }
}
```

(Additional fixture files listed in quickstart.md.)

## BDD Scenario Mapping

| Feature File | Spec Scenarios | Story |
|---|---|---|
| `local_price_fallback_history.feature` | History served from local file; gap-fill applied; no-fallback → 404; ISIN pseudo-ticker; use_local_only | US1 |
| `local_price_fallback_current.feature` | Current price from local file; no-fallback → 404 | US2 |
| `local_price_fallback_fx.feature` | FX conversion applied to local file prices | US3 |

Each Gherkin scenario in the spec maps 1:1 to a `.feature` file scenario.

## Dependency Graph

```
Phase 1 (Setup & OpenAPI)
  └─ T001: Update openapi.yaml descriptions
  └─ T002: Add FallbackSettings to Settings (config.py)
  └─ T003: Create FallbackEntry model (models/fallback.py)
  └─ T004: Create test fixture files (CSV + JSON)

Phase 2 (Foundational — repository + local provider)
  └─ T005: FallbackConfigRepository (repositories/fallback_config.py)
  └─ T006: LocalPricingProvider (providers/local_provider.py)

Phase 3 (US1 — Price History Fallback)
  └─ T007 [BDD]: Write history feature file + steps (RED)
  └─ T008: FallbackPricingProvider (providers/fallback_provider.py)
  └─ T009: Wire FallbackPricingProvider in securities.py
  └─ T010 [verify]: History BDD scenarios GREEN

Phase 4 (US2 — Current Price Fallback)
  └─ T011 [BDD]: Write current price feature file + steps (RED)
  └─ T012: get_current_price path in LocalPricingProvider + FallbackPricingProvider
  └─ T013 [verify]: Current price BDD scenarios GREEN

Phase 5 (US3 — FX Conversion)
  └─ T014 [BDD]: Write FX conversion feature file + steps (RED)
  └─ T015 [verify]: FX conversion BDD scenarios GREEN (no new impl; existing CurrencyService handles it)

Phase 6 (Identifier Fallback)
  └─ T016 [BDD]: Write ISIN pseudo-ticker feature file + steps (RED)
  └─ T017: FallbackIdentifierProvider (identifier_provider.py)
  └─ T018: Wire FallbackIdentifierProvider in identifiers.py
  └─ T019 [verify]: Identifier BDD scenarios GREEN

Phase 7 (Polish)
  └─ T020: Error edge cases — missing file (503), empty file (404)
  └─ T021: ruff + mypy --strict (zero violations)
  └─ T022: Full BDD suite green
```
