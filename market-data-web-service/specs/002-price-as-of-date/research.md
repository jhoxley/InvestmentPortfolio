# Research: Add As-Of Date to Current Price Response

**Feature**: 002-price-as-of-date
**Date**: 2026-05-06
**Status**: Complete — all unknowns resolved

---

## Decision 1: Date Source from yfinance

**Decision**: Use `Ticker.history(period="5d")` — the date of the last row in the returned DataFrame.

**Rationale**: `yfinance.Ticker.fast_info` was inspected empirically against yfinance 1.3.0. Its available attributes are:
`currency`, `day_high`, `day_low`, `exchange`, `fifty_day_average`, `last_price`, `last_volume`, `market_cap`, `open`, `previous_close`, `quote_type`, `regular_market_previous_close`, `shares`, `ten_day_average_volume`, `three_month_average_volume`, `timezone`, `toJSON`, `two_hundred_day_average`, `values`, `year_change`, `year_high`, `year_low`.

**No date attribute exists.** There is no `last_trade_date`, `regularMarketTime`, or equivalent on `fast_info` in this version.

`Ticker.history(period="5d")` returns a DataFrame with a DatetimeTZ index. The last row's index value (`.date()`) is the most recent trading day with a closing price — which is exactly what the history endpoint uses, guaranteeing reconciliation.

**Alternatives considered**:
- `Ticker.fast_info.last_price` + manual date inference (today or prior business day): fragile, does not guarantee reconciliation with the history endpoint. Rejected.
- `Ticker.info["regularMarketTime"]`: available as a Unix timestamp but requires separate HTTP call (`info` is heavier than `history`). Also not guaranteed to match the history endpoint's date. Rejected.
- `Ticker.get_fast_info()`: same as `fast_info`, no date available. Rejected.

---

## Decision 2: Price Source Change

**Decision**: Switch `get_current_price()` to derive the `price` from `history(period="5d")` last row's `Close`, replacing the existing `fast_info.last_price`.

**Rationale**: FR-004 requires that `price` and `as_of_date` refer to the same trading session. If `price` comes from `fast_info` (potentially intraday) and `as_of_date` comes from `history` (always a closing-price date), they may refer to different times during market hours. Using history for both eliminates this ambiguity and guarantees consistency.

For a portfolio analysis tool, daily closing prices are the correct unit of measurement. Intraday prices from `fast_info.last_price` are less useful in this context.

**Alternatives considered**:
- Keep `fast_info.last_price` for price; derive date from history: violates FR-004 during market hours. Rejected.
- Use `fast_info.last_price` for price; use `fast_info.last_price` date via some attribute: no date attribute exists (see Decision 1). Rejected.

**Impact**: Existing US1 BDD tests for `current_price.feature` continue to pass — the price is still positive, the currency and other fields are still present. The only observable difference is that the price is now consistently the daily close, never an intraday value.

---

## Decision 3: market_state Source

**Decision**: Derive `market_status` from `t.info.get("marketState")` — falls back to `"closed"` if unavailable.

**Rationale**: The existing implementation calls `getattr(info, "market_state", None)` on `fast_info`, which always returns `None` in yfinance 1.3.0 (the attribute does not exist). This means `market_status` was always `"closed"` in the existing service. `t.info["marketState"]` returns e.g. `"REGULAR"` (open), `"CLOSED"`, or `"PRE"`/`"POST"` (extended hours).

This is a bug fix, not a new feature — but it is a natural improvement made while touching `get_current_price()`.

**Alternatives considered**:
- Continue returning `"closed"` always: technically incorrect, contradicts the field's documented meaning. Rejected.
- Parse `fast_info.timezone` + current time: fragile across exchanges. Rejected.

---

## Decision 4: Backward Compatibility

**Decision**: `as_of_date` is a new required field on `PriceResponse`. All existing fields remain unchanged.

**Rationale**: Existing BDD scenarios test for specific fields by name; they do not assert the absence of other fields. Adding a new field does not break any existing test or consumer. The OpenAPI contract update (adding a new required field) is a minor non-breaking change from a consumer perspective — consumers can ignore fields they do not use.

**Assumptions**: No consumer is deserialising the response into a strict schema that rejects unknown fields. Per the spec, the service is for personal/local use.
