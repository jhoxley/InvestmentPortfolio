# Phase 1 Data Model: Observed-Only Price History (`fill=none`)

**Feature**: `specs/009-observed-prices-fill-none` | **Date**: 2026-10-03

Three new types and two extended ones. Nothing is removed or renamed, and no existing field changes
type, shape or meaning.

---

## New: `FillMode`

**Location**: `app/models/fill.py`
**Kind**: `enum.StrEnum`
**Represents**: Which series-shaping strategy a history request wants.

| Member | Wire value | Meaning |
|---|---|---|
| `ALL` | `"all"` | Today's behaviour: a value for every Mon–Fri in the requested range, gaps filled by carry. |
| `NONE` | `"none"` | Real observations only; no date is manufactured. |

**Validation rules**:

- Any value outside the two members is rejected during request parsing with a 422 naming `fill`
  (FR-004). No data-source call occurs.
- Absent parameter resolves to `ALL` (FR-002).
- Values are lowercase and case-sensitive, matching the enum's wire values.

---

## New: `ObservationWindow`

**Location**: `app/providers/observation_window.py`
**Kind**: frozen dataclass
**Represents**: The earliest and latest dates for which the service knows of a real observation for one
instrument — the `ObservationWindow` entity from the spec.

| Field | Type | Notes |
|---|---|---|
| `first_observed_date` | `date` | Earliest known real observation. |
| `last_observed_date` | `date` | Latest known real observation. |

**Validation rules**:

- `first_observed_date <= last_observed_date`. A single known observation yields equal values.
- Derived from real observations only, never from filled values (FR-014).
- Not clipped to any requested range (FR-013).
- Widens monotonically as more history is discovered, for as long as the underlying stored history
  survives (FR-015). It is not a durable promise: deleting the cached history resets what the service
  knows, which is why the field is specified as "as far as the service knows".
- `None` (no window) is a legitimate answer when the service holds nothing for the instrument.

**Relationships**: Produced by any `ObservationWindowSource`; consumed by `PricingService` and surfaced
on `PriceHistoryResponse`.

---

## New: `ObservationWindowSource` (capability protocol)

**Location**: `app/providers/observation_window.py`
**Kind**: `typing.Protocol`, `@runtime_checkable`

```python
def observation_window(self, ticker: str) -> ObservationWindow | None: ...
```

**Implemented by**:

| Implementer | Window derived from |
|---|---|
| `CachedPricingProvider` | First and last row of `{ticker}.csv` in the cache directory. |
| `LocalPricingProvider` | First and last row of the configured fallback CSV. |
| `FallbackPricingProvider` | The local file's window whenever the local file served the request — both for a `use_local_only` entry and for one whose file was used because the primary source returned nothing. Delegates to its inner provider only when the primary source supplied the prices. |

> **Why the fallback rule is phrased by data source, not by configuration flag**: keying it off
> `use_local_only` alone returns `None` for the fallback-triggered case, where the CSV supplied the prices
> but no cache file exists to read a window from. FR-017 requires the window to follow whichever source
> actually served the request.

**Cache purity invariant** (what makes FR-014 and FR-008 hold): the cache CSV contains only real
observations. `CachedPricingProvider` writes what the inner provider returned, and gap-fill runs
*downstream* of the cache in `PricingService` — so a filled value is never persisted and can never be
read back as an observation. This is why a window derived from cache extremes is a window over real
observations, and why FR-008's "even when the underlying store already holds previously filled values"
clause describes a state this design cannot reach. Any future change that caches post-fill data would
break both requirements.

**Deliberately not implemented by** `YFinanceProvider`: a stateless source cannot answer what the
service knows overall. Callers must treat the capability as optional and fall back to deriving the
extremes from the series just returned (Interface Segregation — see research R3).

---

## New: `SeriesFiller` (strategy protocol) and `ObservedOnlyFiller`

**Location**: `app/services/series_fill.py`

```python
class SeriesFiller(Protocol):
    def fill(
        self, observations: list[tuple[date, float]], from_date: date, to_date: date
    ) -> list[tuple[date, float]]: ...
```

**Implementations**:

| Class | Mode | Behaviour |
|---|---|---|
| `GapFillService` (existing, unmodified) | `ALL` | Mon–Fri grid with forward-fill, back-fill and end-of-range fill. Already satisfies the protocol structurally. |
| `ObservedOnlyFiller` (new) | `NONE` | De-duplicates by date, sorts ascending, keeps only `from_date <= d <= to_date`. Manufactures no dates. Retains weekend-dated observations. |

**`ObservedOnlyFiller` validation rules**:

- Output dates are a subset of input dates (the invariant behind FR-005 and FR-008).
- Output is sorted ascending with unique dates; on a duplicate date the last value wins, matching
  `CacheRepository.write`'s existing de-duplication.
- Empty input yields empty output; the empty case is turned into a 404 by `PricingService`, not here.

`FillStrategyResolver.resolve(mode) -> SeriesFiller` maps mode to implementation, so `PricingService`
holds no `if`/`else` on mode semantics.

---

## New: `NoEarlierDataBoundary` (persisted record)

**Location**: persisted as `./cache/{sanitised-ticker}.meta.json`; accessed through `CacheRepository`.
**Represents**: The spec's `NoEarlierDataBoundary` entity — an assertion that the data source has no
observations before a given date for this instrument.

**On-disk shape**:

```json
{ "no_data_before": "2024-01-02" }
```

| Field | Type | Notes |
|---|---|---|
| `no_data_before` | ISO-8601 date string | The data source returned nothing earlier than this date for a segment that was actually requested. |

**Accessors** (`CacheRepository`): `read_no_data_before(ticker) -> date | None`,
`write_no_data_before(ticker, d) -> None`, `clear_no_data_before(ticker) -> None`.

**Validation and lifecycle rules**:

- A missing or unreadable sidecar means "no boundary known" — never an error. An unparsable sidecar is
  logged at WARNING and treated as absent, matching `CacheRepository.read`'s existing tolerance.
- Written atomically (temp file + `os.replace`), as the CSV is.
- Keyed by the same sanitised filename as the CSV, so `^FTSE` and `0P0000X3IE.L` behave identically to
  their price files.
- **Recorded** when a requested earlier segment comes back empty (FR-018), and when a cold-cache populate
  returns rows starting after the requested start date (FR-027).
- **Consulted** only for the segment before the earliest cached observation. The segment *after* the
  latest cached observation is never suppressed (FR-020).
- **Invalidated** — moved forward to the newly discovered earliest observation — when a fetch returns
  rows earlier than the boundary, and cleared outright if the cache CSV is found to hold a row earlier
  than the boundary.
- **Deleted** with the CSV by `CacheRepository.delete`, and by `delete_all` (which must glob
  `*.meta.json` as well as its current `*.csv`).
- Never written from a `ProviderUnavailableError` (FR-028): an outage is not evidence that data does not
  exist, and an existing boundary is left untouched when a fetch fails.

**Relationships**: One optional record per cached instrument; its lifetime is bounded by that
instrument's cache file.

---

## Extended: `PriceHistoryResponse`

**Location**: `app/models/pricing.py`

| Field | Type | Status |
|---|---|---|
| `ticker` | `str` | unchanged |
| `currency` | `str` | unchanged |
| `prices` | `list[PricePoint]` | unchanged shape; contents depend on `fill` |
| `first_observed_date` | `date \| None` | **NEW** |
| `last_observed_date` | `date \| None` | **NEW** |

**Validation rules**:

- Both fields are populated in both fill modes (FR-012) and describe the instrument, not the requested
  range (FR-013).
- Nullable so the model stays valid when the service genuinely knows no window; in practice a successful
  response always has at least one observation, because an empty series is a 404.
- Purely additive: existing field names, order and `PricePoint` shape are untouched, so existing
  consumers are unaffected (FR-016).

---

## Extended: `ObservedPriceSeries` (conceptual)

The spec's `ObservedPriceSeries` entity has no dedicated class. It is the `list[tuple[date, float]]`
returned by `ObservedOnlyFiller.fill`, which becomes `PriceHistoryResponse.prices` after minor-unit
normalisation and any currency conversion. Its defining invariant — every date corresponds to a real
observation from the primary source, cache or fallback file — is enforced by `ObservedOnlyFiller`
producing a subset of its input dates, and is the property US1's final scenario asserts directly.

---

## Entity relationships

```
FillMode ──selects──► SeriesFiller ──┬── GapFillService      (mode ALL)
                                     └── ObservedOnlyFiller  (mode NONE)
                                                │
                                           produces
                                                ▼
                                      ObservedPriceSeries ──► PriceHistoryResponse.prices

ObservationWindowSource ──produces──► ObservationWindow ──► PriceHistoryResponse
  ├── CachedPricingProvider    (cache CSV extremes)
  ├── LocalPricingProvider     (fallback CSV extremes)
  └── FallbackPricingProvider  (delegates)

CachedPricingProvider ──consults/maintains──► NoEarlierDataBoundary (one per cached ticker)
                                                      │
                                              persisted by CacheRepository
                                              lifetime bounded by {ticker}.csv
```
