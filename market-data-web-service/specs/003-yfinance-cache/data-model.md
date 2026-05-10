# Data Model: YFinance Price Data Cache

**Branch**: `003-yfinance-cache` | **Date**: 2026-05-08

## Entities

---

### CacheEntry

Represents the stored historical price data for a single ticker on the local filesystem.

| Attribute | Type | Description |
|-----------|------|-------------|
| `ticker` | `str` | Yahoo Finance ticker symbol; also the stem of the cache filename |
| `cached_min_date` | `date` | Actual earliest trading date present in the stored data (derived — not stored separately) |
| `cached_max_date` | `date` | Actual latest trading date present in the stored data (derived — not stored separately) |
| `prices` | `list[PriceRecord]` | Chronologically ascending list of trading-day price observations |

**Identity rule**: One `CacheEntry` per ticker symbol. The file `{cache_dir}/{ticker}.csv` is the canonical record.

**Derived metadata**: `cached_min_date` and `cached_max_date` are computed at read-time from the actual dates in `prices`; they are not stored as separate fields. This implements FR-013 — the stored range always reflects real trading-day data.

**Lifecycle**:
- **Created**: first time a ticker is requested and no cache file exists (cache miss path)
- **Updated**: when a partial cache hit results in new segments being fetched and merged
- **Deleted**: via `DELETE /cache/{ticker}` or `DELETE /cache`
- **Read**: on every historical price request before any YFinance call

---

### PriceRecord

A single daily closing price observation stored within a CacheEntry.

| Attribute | Type | Description | Constraints |
|-----------|------|-------------|-------------|
| `date` | `date` | Trading date (YYYY-MM-DD) | Not null; unique within a CacheEntry |
| `close` | `float` | Closing price for this trading date | > 0.0 |

**Identity rule**: `date` is the unique key within a single CacheEntry; duplicate dates are deduplicated (last-write-wins) during merge.

---

### CacheDirectory

The filesystem location where all `CacheEntry` files are stored.

| Attribute | Type | Description |
|-----------|------|-------------|
| `path` | `Path` | Absolute or relative path on the local filesystem |

**Configuration**: The `path` is read from `config.yaml → cache.directory` at startup (FR-001, FR-011).  
**Lifecycle**: Created automatically at startup if it does not exist (FR-011). All cache files within it use the pattern `{ticker}.csv`.

---

### Settings

The application configuration loaded from `config.yaml` at startup.

| Attribute | Type | Default | Description |
|-----------|------|---------|-------------|
| `cache.directory` | `str` | `./cache` | Path to the cache storage directory |

---

### CacheDeleteResponse

Response returned by `DELETE /cache/{ticker}`.

| Attribute | Type | Description |
|-----------|------|-------------|
| `ticker` | `str` | The ticker whose cache was targeted |
| `deleted` | `bool` | `true` if a cache entry was found and removed; `false` if no entry existed |

---

### CacheClearResponse

Response returned by `DELETE /cache`.

| Attribute | Type | Description |
|-----------|------|-------------|
| `deleted_count` | `int` | Number of cache entries (files) removed; 0 if cache was empty |

---

## Cache Coverage Algorithm

Given a request for ticker `T` over `[from_date, to_date]`:

```
1. Read CacheEntry for T
   → If no file exists: CACHE MISS → fetch full range from YFinance
   → If file unreadable: treat as CACHE MISS (FR-010)

2. Derive cached_min = min(PriceRecord.date), cached_max = max(PriceRecord.date)

3. Identify missing segments:
   before_segment = [from_date, cached_min - 1 day]  if from_date < cached_min
   after_segment  = [cached_max + 1 day, to_date]    if to_date   > cached_max

4. If no missing segments: FULL HIT → return records filtered to [from_date, to_date]

5. If missing segments exist: PARTIAL HIT
   a. Fetch each segment from YFinance
   b. On any YFinance error → raise ProviderUnavailableError (FR-012); do NOT write to cache
   c. Merge all records (cached + new) by date; deduplicate; sort ascending
   d. Write merged data back to CacheEntry file
   e. Return records filtered to [from_date, to_date]
```

## File Format

**CSV schema** (one file per ticker, `{ticker}.csv`):
```csv
date,close
2025-01-02,189.30
2025-01-03,188.50
2025-01-06,191.00
```

- Rows sorted ascending by `date`
- No header variations; schema is fixed
- Ticker symbols with filesystem-unsafe characters (`^`, `/`, `:`, `*`, `?`, `"`, `<`, `>`, `|`) are sanitised by replacing each with `_` for the filename only; the ticker value in memory is unmodified
