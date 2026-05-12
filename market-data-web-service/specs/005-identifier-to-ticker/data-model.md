# Data Model: Identifier-to-Ticker Lookup

**Feature**: 005-identifier-to-ticker  
**Date**: 2026-05-12

---

## Entities

### IdentifierType (string enum)

The canonical set of supported identifier types.

| Value  | Description |
|--------|-------------|
| `ISIN` | International Securities Identification Number (ISO 6166) |
| `CUSIP` | Committee on Uniform Securities Identification Procedures (US/Canada) |
| `SEDOL` | Stock Exchange Daily Official List (UK/international) |

---

### IdentifierLookupRequest (input)

Submitted by the caller to the lookup endpoint.

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `identifier` | `str` | yes | Non-empty; format validated against detected or hinted type |
| `type` | `IdentifierType \| null` | no | If provided, skips auto-detection and validates against the specified type |

**Auto-detection rules** (applied when `type` is absent):

| Priority | Type  | Condition |
|----------|-------|-----------|
| 1        | ISIN  | `len == 12` and first 2 chars match `[A-Z]{2}` |
| 2        | CUSIP | `len == 9` |
| 3        | SEDOL | `len in {6, 7}` |
| —        | Error | No match → `IdentifierFormatError` (422) |

Input is normalised to uppercase before detection and validation.

---

### IdentifierFormatValidation (validation rules)

Applied after type is known (detected or hinted).

| Type  | Pattern              | Length | Notes |
|-------|----------------------|--------|-------|
| ISIN  | `^[A-Z]{2}[A-Z0-9]{10}$` | 12 | Structural only — no Luhn computation |
| CUSIP | `^[A-Z0-9]{9}$`     | 9  | |
| SEDOL | `^[A-Z0-9]{6,7}$`  | 6–7 | |

Validation failure → `IdentifierFormatError` (422).

---

### TickerResolutionResponse (output)

Returned on successful resolution.

| Field | Type | Description |
|-------|------|-------------|
| `identifier` | `str` | The original identifier value (normalised to uppercase) |
| `identifier_type` | `str` | Detected or caller-confirmed type (`ISIN`, `CUSIP`, or `SEDOL`) |
| `ticker` | `str` | Resolved ticker symbol, as returned by the data source |
| `security_name` | `str` | Security name, as returned by the data source |
| `exchange` | `str` | Exchange identifier, passed through from the data source without normalisation |

---

## Relationships

```
IdentifierLookupRequest
  └── identifier_type_hint: IdentifierType? (optional)

IdentifierFormatValidation
  └── governed_by: IdentifierType (one-to-one)

TickerResolutionResponse
  ├── identifier_type: IdentifierType
  └── ticker → used by existing PriceResponse / PriceHistoryResponse endpoints
```

---

## Error States

| State | Exception | HTTP |
|-------|-----------|------|
| Identifier does not match any known format | `IdentifierFormatError` | 422 |
| Identifier matches format but type hint conflicts | `IdentifierFormatError` | 422 |
| Identifier is validly formatted but data source returns no match | `IdentifierNotFoundError` | 404 |
| Data source is unreachable | `ProviderUnavailableError` | 503 |
