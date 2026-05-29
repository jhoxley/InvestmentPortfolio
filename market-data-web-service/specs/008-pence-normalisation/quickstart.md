# Quickstart & Integration Scenarios: Pence Unit Normalisation

**Feature**: 008-pence-normalisation  
**Date**: 2026-05-26

---

## Overview

After this feature, the market data service automatically normalises sub-unit currencies (GBp, USd) to their major-unit equivalents (GBP, USD) on all pricing endpoints. No consumer changes are required.

---

## Scenario 1: Current price of a UK pence-quoted stock (US1)

**Setup**: A mock pricing provider returns `price=31140, currency="GBp"` for ticker `CNKY.L`.

**Request**:
```
GET /securities/CNKY.L/price
```

**Expected response**:
```json
{
  "ticker": "CNKY.L",
  "price": 311.40,
  "currency": "GBP",
  "market_status": "closed",
  "as_of_date": "2026-05-26"
}
```

**Key assertions**:
- `currency == "GBP"` (not `"GBp"`)
- `price == 311.40` (not `31140`)

---

## Scenario 2: Price history of a pence-quoted stock (US2)

**Setup**: A mock pricing provider returns prices in currency `"GBp"` for ticker `CNKY.L`:
- `2026-05-20 → 31000`
- `2026-05-21 → 31100`
- `2026-05-22 → 31140`

**Request**:
```
GET /securities/CNKY.L/history?from=2026-05-20&to=2026-05-22
```

**Expected response**:
```json
{
  "ticker": "CNKY.L",
  "currency": "GBP",
  "prices": [
    {"date": "2026-05-20", "close": 310.00},
    {"date": "2026-05-21", "close": 311.00},
    {"date": "2026-05-22", "close": 311.40}
  ]
}
```

**Key assertions**:
- `currency == "GBP"`
- Each `close` value equals the raw pence value ÷ 100

---

## Scenario 3: Standard currency is unchanged (US1/US2 regression)

**Setup**: A mock provider returns `price=150.00, currency="USD"` for ticker `AAPL`.

**Request**:
```
GET /securities/AAPL/price
```

**Expected response**:
```json
{
  "ticker": "AAPL",
  "price": 150.00,
  "currency": "USD"
}
```

**Key assertions**:
- `currency == "USD"` (unchanged)
- `price == 150.00` (not divided by anything)

---

## Scenario 4: Pence-quoted stock with FX conversion to USD (US3)

**Setup**:
- Mock provider returns prices in currency `"GBp"` for ticker `CNKY.L` (e.g. `31140`)
- FX provider returns a GBP/USD rate of `1.25` for the relevant date range

**Request**:
```
GET /securities/CNKY.L/history?from=2026-05-22&to=2026-05-22&currency=USD
```

**Processing order**:
1. `PricingService` fetches raw `31140 GBp`
2. Normalisation: `311.40 GBP`
3. FX conversion: `311.40 × 1.25 = 389.25 USD`

**Expected response**:
```json
{
  "ticker": "CNKY.L",
  "currency": "USD",
  "prices": [
    {"date": "2026-05-22", "close": 389.25, "fx_rate": 1.25}
  ]
}
```

**Key assertions**:
- `currency == "USD"`
- `close == 389.25` (normalised first, then FX-converted — not `31140 × 1.25 = 38925`)

---

## BDD Test Mapping

| Scenario | Feature file | User Story |
|----------|-------------|------------|
| Current price normalised (GBp → GBP) | `pence_normalisation_current.feature` | US1 |
| Current price passthrough (USD) | `pence_normalisation_current.feature` | US1 |
| Current price normalised (USd → USD) | `pence_normalisation_current.feature` | US1 |
| History normalised (GBp → GBP) | `pence_normalisation_history.feature` | US2 |
| History passthrough (EUR) | `pence_normalisation_history.feature` | US2 |
| FX with normalisation first | `pence_normalisation_fx.feature` | US3 |
| Current price + FX | `pence_normalisation_fx.feature` | US3 |
