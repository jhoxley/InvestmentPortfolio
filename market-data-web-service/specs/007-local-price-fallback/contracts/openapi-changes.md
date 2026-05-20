# OpenAPI Contract Changes: Local Price File Fallback

**Feature**: 007-local-price-fallback  
**Base contract**: `openapi.yaml` (root of repository)  
**Change type**: Non-breaking additions and description updates  
**Version bump**: PATCH (0.1.0 → 0.1.1) — no schema changes; documentation/description updates only

---

## Summary of Changes

This feature does not add new endpoints or change any request/response schemas. All changes are:
1. Updated `503` response descriptions on the securities endpoints to include fallback file errors.
2. Updated the `GET /identifiers/{identifier}` endpoint description to document pseudo-ticker behaviour.
3. A new `FallbackConfig` schema added under `components/schemas` for documentation purposes only (not used in any endpoint response/request body).

---

## Changed Endpoints

### `GET /securities/{ticker}/price`

**503 response description** (updated):
```
Upstream data provider unavailable, or a configured fallback CSV file could not be read (missing file or permission error).
```

### `GET /securities/{ticker}/history`

**503 response description** (updated):
```
Upstream data provider unavailable, or a configured fallback CSV file could not be read (missing file or permission error).
```

### `GET /identifiers/{identifier}`

**Endpoint description** (add to existing):
```
When the primary data source cannot resolve the identifier to a ticker, the service consults the
local fallback configuration. If a matching entry is found, the identifier itself is returned as
the ticker (a "pseudo-ticker"), enabling subsequent pricing requests to route to the local file.
```

**200 response description** (updated):
```
Identifier resolved successfully. The ticker field may be a pseudo-ticker (equal to the identifier)
when the resolution came from the local fallback configuration rather than the primary data source.
```

---

## New Schema Component

### `FallbackConfigEntry` (informational — not used in endpoint I/O)

```yaml
FallbackConfigEntry:
  type: object
  required:
    - csv_path
    - currency
    - date_column
    - price_column
  properties:
    csv_path:
      type: string
      description: Filesystem path to the CSV file containing price history.
      example: /data/prices/priv01.csv
    currency:
      type: string
      pattern: ^[A-Z]{3}$
      description: ISO 4217 currency code of the prices in the CSV file.
      example: GBP
    date_column:
      type: string
      description: Name of the column in the CSV file that contains date values.
      example: Date
    price_column:
      type: string
      description: Name of the column in the CSV file that contains price values.
      example: Close
    use_local_only:
      type: boolean
      default: false
      description: >
        When true, the primary data source is bypassed entirely; prices are served from
        the local file without attempting a YFinance lookup. Use for assets known to be
        unavailable on the primary source.
```

### `FallbackConfig` (informational — documents the JSON config file format)

```yaml
FallbackConfig:
  type: object
  description: >
    Top-level structure of the fallback configuration JSON file.
    Keys are security identifiers (ticker symbols, ISINs, CUSIPs, or SEDOLs),
    normalised to uppercase. Each value is a FallbackConfigEntry.
  additionalProperties:
    $ref: '#/components/schemas/FallbackConfigEntry'
  example:
    PRIV01:
      csv_path: /data/prices/priv01.csv
      currency: GBP
      date_column: Date
      price_column: Close
      use_local_only: false
    GB00B0PRVT01:
      csv_path: /data/prices/gb00b0prvt01.csv
      currency: GBP
      date_column: Date
      price_column: Price
      use_local_only: true
```

---

## No-Change Endpoints

The following endpoints are unaffected by this feature:
- `GET /fx/{pair}/history` — FX pair endpoint is explicitly out of scope.
- `DELETE /cache/{ticker}` — Cache management unaffected.
- `DELETE /cache` — Cache management unaffected.

---

## Implementation Notes

- The `openapi.yaml` in the repository root must be updated with the description changes above before the endpoint implementation tasks begin (Constitution VI: OpenAPI-First).
- The `FallbackConfigEntry` and `FallbackConfig` schemas should be added to `components/schemas` even though no endpoint returns them, to document the config file format for operators.
- The version field in `openapi.yaml` should be bumped from `0.1.0` to `0.1.1`.
