# Data Model: Local Price File Fallback

**Feature**: 007-local-price-fallback  
**Phase**: 1 — Design  
**Date**: 2026-05-20

---

## Entities

### FallbackEntry

A single entry in the fallback configuration, mapping one identifier to one local CSV file.

| Field | Type | Required | Constraints | Notes |
|-------|------|----------|-------------|-------|
| `identifier` | `str` | Yes | Non-empty; key in the JSON dict | Stored/compared case-insensitively (normalised to uppercase) |
| `csv_path` | `Path` | Yes | Valid filesystem path | May be absolute or relative to the config file's directory |
| `currency` | `str` | Yes | 3-letter ISO 4217 code | Currency of the prices in the CSV file |
| `date_column` | `str` | Yes | Non-empty | Column name (header) in the CSV containing the date values |
| `price_column` | `str` | Yes | Non-empty | Column name (header) in the CSV containing the price values |
| `use_local_only` | `bool` | No | Default: `False` | When `True`, skip YFinance entirely and serve from local file immediately |

**Source**: JSON config file (operator-managed). One `FallbackEntry` per key in the JSON dict.

---

### FallbackConfigFile

The top-level structure of the JSON configuration file.

```
{
  "<IDENTIFIER_UPPERCASE>": FallbackEntry,
  ...
}
```

- Keys are identifier strings (ticker symbols, ISINs, CUSIPs, SEDOLs).
- Keys are compared case-insensitively (normalised to uppercase at load time and at lookup time).
- The file is re-read on every request; no service restart is needed to add or modify entries.
- A missing or unconfigured `fallback.config_path` in `Settings` results in an empty config (no fallback entries); the service behaves as before.

---

### LocalPriceRecord (ephemeral)

A single price observation read from a CSV row. Not persisted; created transiently during CSV parsing and discarded after conversion.

| Field | Type | Notes |
|-------|------|-------|
| `date` | `datetime.date` | Parsed from the configured date column using `dateutil.parser.parse()` |
| `price` | `float` | Parsed from the configured price column; must be > 0 |

The list of `LocalPriceRecord` values is equivalent to `list[tuple[date, float]]`, the standard `PricingProvider.get_price_history()` return type.

---

## Configuration Schema

### Settings (updated)

```
Settings
├── cache: CacheSettings          (existing)
│   └── directory: Path
└── fallback: FallbackSettings    (NEW)
    └── config_path: Path | None  (default: None)
```

When `config_path` is `None`, `FallbackConfigRepository` returns an empty config (no fallback entries).

---

## Relationships

```
Settings.fallback.config_path
         │
         ▼
FallbackConfigRepository ──reads──▶ JSON file (FallbackConfigFile)
         │
         │ lookup(identifier) → FallbackEntry | None
         ▼
FallbackPricingProvider
    ├── inner: CachedPricingProvider(YFinanceProvider)  (try first, unless use_local_only)
    └── on DataNotFoundError / use_local_only ──▶ LocalPricingProvider(entry)
                                                       │
                                                       ▼
                                                 reads CSV file
                                                 (entry.csv_path)
                                                       │
                                                       ▼
                                               list[LocalPriceRecord]
                                                       │
                                                       ▼
                                         list[tuple[date, float]]
                                         (→ GapFillService → PricingService)

FallbackIdentifierProvider
    ├── inner: YFinanceIdentifierProvider
    └── on IdentifierNotFoundError ──▶ FallbackConfigRepository.lookup(identifier)
                                              │
                               found ─────────┴───── not found
                                 │                       │
                         return identifier          re-raise IdentifierNotFoundError
                         as pseudo-ticker
```

---

## State Transitions

### FallbackConfigRepository lookup

```
lookup(identifier)
  │
  ├─ config_path is None ──▶ return None
  │
  ├─ file not found ──▶ raise ProviderUnavailableError  [logged at ERROR]
  │
  ├─ file found, identifier not in config ──▶ return None
  │
  └─ identifier found ──▶ return FallbackEntry
```

### LocalPricingProvider.get_price_history

```
get_price_history(ticker, from_date, to_date)
  │
  ├─ file not found / unreadable ──▶ raise ProviderUnavailableError  [→ 503]
  │
  ├─ file has no data rows ──▶ raise DataNotFoundError  [→ 404]
  │
  └─ file has rows ──▶ parse all rows ──▶ return sorted list[tuple[date, float]]
       (gap-fill and date-range filtering applied by PricingService / GapFillService upstream)
```

### FallbackPricingProvider.get_price_history

```
get_price_history(ticker, from_date, to_date)
  │
  ├─ lookup(ticker) → None ──▶ call inner, propagate result or exception unchanged
  │
  ├─ lookup(ticker) → entry, use_local_only=True ──▶ LocalPricingProvider(entry).get_price_history()
  │
  └─ lookup(ticker) → entry, use_local_only=False
       │
       ├─ inner.get_price_history() succeeds ──▶ return result (YFinance data used)
       │
       └─ inner raises DataNotFoundError ──▶ LocalPricingProvider(entry).get_price_history()
            (ProviderUnavailableError from inner propagates unchanged — no fallback)
```

---

## Validation Rules

- `currency` must match `^[A-Z]{3}$` (validated at config load time; invalid entries log a warning and are skipped).
- `csv_path` existence is NOT validated at config load time; the error is raised lazily when the file is first requested (SC-006).
- `date_column` and `price_column` must be present in the CSV header row; if not found, raise `ProviderUnavailableError` with a descriptive message.
- Price values of 0 or negative are silently skipped (consistent with `YFinanceProvider` behaviour).
