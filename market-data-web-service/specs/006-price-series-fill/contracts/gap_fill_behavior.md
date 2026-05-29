# Contract: Gap-Fill Behavioral Guarantee

**Feature**: Price Series Gap Fill  
**Applies to**: `GET /securities/{ticker}/history`, `GET /fx/{pair}/history`  
**Date**: 2026-05-17

---

## Summary

Both history endpoints are guaranteed to return an entry for **every Mon–Fri business day** in the requested date range, inclusive. The response schemas are unchanged; only the completeness guarantee is new.

---

## Behavioral Contract

### Business Day Completeness (FR-001, FR-009)

For any request with a valid `from`/`to` date range:

```
∀ d ∈ [from_date, to_date] where d.weekday() ∈ {Mon, Tue, Wed, Thu, Fri}:
  response contains exactly one entry with date = d
```

**Corollary**: Weekend dates (Saturday, Sunday) are never present in the response.

---

### Forward-Fill Rule (FR-002, FR-004)

If business day `d` has no market observation:
- And there exists a prior observed day `d'` < `d`:
- Then `price(d) = price(d')` — the most recent prior observation is carried forward.

This covers mid-range gaps (market holidays, data outages) and end-of-range gaps (today's data not yet available from the source).

---

### Back-Fill Rule (FR-003)

If the first available market observation is on day `d_first` > `from_date`:
- Then for all business days `d` in `[from_date, d_first)`:
- `price(d) = price(d_first)` — the first observation is copied backward.

---

### No Observation → Not Found (FR-008)

If the data source has **no observations at all** for the requested range:
- The endpoint returns HTTP 404 with `code = "TICKER_NOT_FOUND"` or `code = "DATA_NOT_FOUND"`.
- No gap-filled empty series is returned.

---

### Gap-Fill Ordering (FR-005, FR-010)

For security price history with currency conversion:

```
1. Fetch raw security prices  (may contain gaps)
2. Gap-fill security prices   (BusinessDaySeries, Mon-Fri complete)
3. Fetch raw FX rates         (may contain gaps)
4. Gap-fill FX rates          (BusinessDaySeries, Mon-Fri complete)
5. Apply FX rates to prices   (each filled price × filled rate for same date)
6. Return PriceHistoryResponse
```

**Consequence (SC-005)**: A gap-filled security price entry (carrying a repeated price) is multiplied by the gap-filled FX rate for its date — not the FX rate from the original observation date. The converted price may therefore differ day-to-day on holiday dates due to currency moves, but no spike or zero will appear because both series are complete.

---

## Unchanged Behaviour

- `GET /securities/{ticker}/price` (current price) — behaviour unchanged.
- Gap-fill is not switchable per request — it is always applied.
- The response models (`PriceHistoryResponse`, `FxHistoryResponse`, `PricePoint`, `FxRateEntry`) are structurally unchanged; no new fields are added.
- Gap-filled entries are indistinguishable from observed entries in the response — there is no `is_filled` or `fill_type` field.

---

## OpenAPI Updates Required

| Path | Field | Current | Updated |
|------|-------|---------|---------|
| `/securities/{ticker}/history` | `description` | (existing) | Append: "All Mon–Fri business days in the requested range are guaranteed to have an entry — gaps from holidays or data outages are filled by forward/backward carry of the nearest observation." |
| `/fx/{pair}/history` | `description` | (existing) | Append: "All Mon–Fri business days in the requested range are guaranteed to have an entry — gaps from holidays or data outages are filled by forward/backward carry of the nearest rate." |
