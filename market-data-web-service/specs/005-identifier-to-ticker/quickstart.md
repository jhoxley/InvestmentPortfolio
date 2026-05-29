# Quickstart: Identifier-to-Ticker Lookup

**Feature**: 005-identifier-to-ticker  
**Date**: 2026-05-12

End-to-end integration scenarios for BDD test authoring and manual verification.

---

## Scenario 1 — Resolve ISIN to Ticker (Happy Path)

**Input**: `GET /identifiers/US0378331005`  
**Expected**: HTTP 200, `ticker` field is non-empty, `identifier_type` is `"ISIN"`, `security_name` and `exchange` are present.

```python
# BDD step outline
# Given: yf.Search("US0378331005") returns quotes with symbol="AAPL"
# When: GET /identifiers/US0378331005
# Then: status 200, body.ticker == "AAPL", body.identifier_type == "ISIN"
```

---

## Scenario 2 — Resolve CUSIP to Ticker

**Input**: `GET /identifiers/037833100`  
**Expected**: HTTP 200, `identifier_type` is `"CUSIP"`, `ticker` is non-empty.

---

## Scenario 3 — Resolve SEDOL to Ticker

**Input**: `GET /identifiers/B020QX2`  
**Expected**: HTTP 200, `identifier_type` is `"SEDOL"`, `ticker` is non-empty.

---

## Scenario 4 — Resolved Ticker Works with Pricing Endpoint

**Flow**:
1. `GET /identifiers/US0378331005` → resolve ISIN to ticker (e.g., `"AAPL"`)
2. `GET /securities/AAPL/price` → returns HTTP 200 with a price

This confirms end-to-end integration (SC-001).

---

## Scenario 5 — Invalid Format Rejected (US2)

**Input**: `GET /identifiers/NOT-VALID-FORMAT`  
**Expected**: HTTP 422, `code == "IDENTIFIER_FORMAT_ERROR"`, `detail` is descriptive.

---

## Scenario 6 — Valid Format but Not Found (US2)

**Input**: `GET /identifiers/US0000000000`  
**Expected**: HTTP 404, `code == "IDENTIFIER_NOT_FOUND"`, `detail` is descriptive.

---

## Scenario 7 — Type Hint Provided and Matches (US1)

**Input**: `GET /identifiers/US0378331005?type=ISIN`  
**Expected**: HTTP 200, identical result to Scenario 1; `identifier_type == "ISIN"`.

---

## Scenario 8 — Type Hint Provided but Format Conflicts (Edge Case)

**Input**: `GET /identifiers/NOT-VALID-FORMAT?type=ISIN`  
**Expected**: HTTP 422, `code == "IDENTIFIER_FORMAT_ERROR"`.

---

## Scenario 9 — Provider Unavailable (Edge Case)

**Input**: `GET /identifiers/US0378331005` when yfinance raises a network exception.  
**Expected**: HTTP 503, `code == "PROVIDER_UNAVAILABLE"`.

---

## Mock Setup for BDD Tests

The `YFinanceIdentifierProvider` is injected via FastAPI dependency injection.  
Tests override `get_identifier_provider` in `conftest.py` with a `MagicMock(spec=IdentifierProvider)`.

```python
# Typical mock setup for a successful lookup:
mock_identifier_provider.lookup_ticker.return_value = {
    "ticker": "AAPL",
    "security_name": "Apple Inc.",
    "exchange": "NMS",
}
```

Network failure is simulated by configuring the mock to raise `ProviderUnavailableError`.
Empty-result case is simulated by raising `IdentifierNotFoundError`.
