# Data Model: Pence Unit Normalisation

**Feature**: 008-pence-normalisation  
**Date**: 2026-05-26

---

## New Entity: SubUnitCurrencyMapping

Represents the relationship between a sub-unit currency code (as returned by a data source) and its major-unit equivalent, along with the scaling divisor needed to convert values.

| Field          | Type    | Description                                                  |
|----------------|---------|--------------------------------------------------------------|
| `sub_unit_code` | `str`  | The sub-unit currency string as returned by the data source (e.g. `"GBp"`, `"USd"`) |
| `major_code`   | `str`   | The ISO 4217 major-unit code (e.g. `"GBP"`, `"USD"`)        |
| `divisor`      | `float` | The factor by which to divide a price to convert to the major unit (e.g. `100.0`) |

**Initial entries**:

| sub_unit_code | major_code | divisor |
|---------------|------------|---------|
| `GBp`         | `GBP`      | `100.0` |
| `USd`         | `USD`      | `100.0` |

**Validation rules**:
- `sub_unit_code` is matched case-insensitively against the input currency string.
- `major_code` MUST be a valid 3-letter uppercase ISO 4217 code.
- `divisor` MUST be a positive number greater than zero.
- An unrecognised `sub_unit_code` produces no normalisation (pass-through).

---

## Modified Entity: PriceResponse (existing)

No structural changes. After this feature:
- `currency` field always contains a major-unit ISO 4217 code (e.g. `"GBP"`, never `"GBp"`).
- `price` field always contains the major-unit amount (e.g. `311.40`, never `31140`).

---

## Modified Entity: PricePoint / PriceHistoryResponse (existing)

No structural changes. After this feature:
- `PriceHistoryResponse.currency` always contains a major-unit code.
- `PricePoint.close` always contains the major-unit price.

---

## Service Dependency Graph (updated)

```
PricingService
├── PricingProvider (injected — existing)
├── GapFillService (injected — existing)
└── SubUnitNormaliser (injected — NEW)
```

`SubUnitNormaliser` holds the `SubUnitCurrencyMapping` table and exposes:
- `normalise(currency, price) → (major_currency, normalised_price)`
- `normalise_series(currency, series) → (major_currency, normalised_series)`
- `is_minor_unit(currency) → bool`
