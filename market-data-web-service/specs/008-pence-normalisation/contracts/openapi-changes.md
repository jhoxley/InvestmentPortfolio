# API Contract Changes: Pence Unit Normalisation

**Feature**: 008-pence-normalisation  
**Date**: 2026-05-26  
**Scope**: Behaviour documentation only — no schema changes, no new endpoints, no breaking changes.

---

## Summary

This feature introduces no new endpoints and no changes to request or response schemas. The change is purely in the *values* returned by existing fields. The following documentation updates must be applied to `openapi.yaml`.

---

## Endpoint: `GET /securities/{ticker}/price`

### Description addition

Append to the existing endpoint description:

> **Sub-unit currency normalisation**: Prices denominated in a sub-unit currency (e.g. GBp — British pence, USd — US cents) are automatically converted to the corresponding major-unit currency (GBP, USD) before being returned. The `currency` field will always reflect the major-unit ISO 4217 code, and the `price` value will always be in major-unit terms. Consumers do not need to perform any additional scaling.

### Field description updates (in `PriceResponse` schema)

| Field      | New description addition                                                                 |
|------------|------------------------------------------------------------------------------------------|
| `currency` | Always a major-unit ISO 4217 code. Sub-unit codes (e.g. `GBp`) are normalised to their major-unit equivalent (e.g. `GBP`). |
| `price`    | Always expressed in major-unit terms. Sub-unit prices are divided by the appropriate ratio (100 for pence/cents) before being returned. |

---

## Endpoint: `GET /securities/{ticker}/history`

### Description addition

Append to the existing endpoint description:

> **Sub-unit currency normalisation**: Same normalisation as the `/price` endpoint applies. All `close` values in the returned series are in major-unit terms, and the `currency` field reflects the major-unit code. If a `currency` query parameter is provided for FX conversion, normalisation is applied first so the FX rate is applied to major-unit values.

### Field description updates (in `PriceHistoryResponse` / `PricePoint` schema)

| Field              | New description addition                                                               |
|--------------------|----------------------------------------------------------------------------------------|
| `currency` (response) | Always a major-unit ISO 4217 code after normalisation.                             |
| `close` (PricePoint)  | Always in major-unit terms. Pence/cent values are divided by 100 before inclusion. |

---

## Version bump

`openapi.yaml` version: `0.1.1` → `0.1.2` (minor behaviour documentation, no breaking changes).

---

## No changes required to

- Request schemas (query parameters, path parameters)
- Response schemas (field names, types, nullability)
- Error responses (4xx, 5xx)
- `/identifiers/` endpoints
- `/fx/` endpoints
- `/cache/` endpoints
