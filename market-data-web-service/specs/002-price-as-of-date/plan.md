# Implementation Plan: Add As-Of Date to Current Price Response

**Branch**: `002-price-as-of-date` | **Date**: 2026-05-06 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/002-price-as-of-date/spec.md`

## Summary

Add a required `as_of_date` field (YYYY-MM-DD) to the `GET /securities/{ticker}/price` response that identifies the trading date of the returned price. To guarantee reconciliation with the history endpoint, the provider is updated to derive both the price and its date from `Ticker.history(period="5d")` rather than `fast_info`. This makes date and price provably from the same session and eliminates the gap between the two endpoints. The change is additive — all existing fields are preserved.

## Technical Context

**Language/Version**: Python 3.14.4 (existing venv)
**Primary Dependencies**: FastAPI 0.136.1, yfinance 1.3.0, pydantic 2.13.3, structlog, pytest-bdd 8.1.0
**Storage**: N/A — live fetch, no persistence
**Testing**: pytest-bdd (Gherkin BDD), pytest, httpx TestClient
**Target Platform**: Local machine — Windows; `localhost:8000`
**Project Type**: web-service (existing)
**Performance Goals**: Current price response < 3s (unchanged from feature 001)
**Constraints**: `history(period="5d")` replaces `fast_info.last_price` — slightly more data fetched but guarantees date/price consistency
**Scale/Scope**: Single user, personal portfolio tool

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Check | Notes |
|-----------|-------|-------|
| I. SOLID Design | ✅ | Change is confined to provider (data) and service (assembly); router is untouched |
| II. Standard Dependencies | ✅ | No new dependencies; yfinance `.history()` already used in the history endpoint |
| III. BDD Test-First | ✅ | New `.feature` file authored and confirmed failing before implementation tasks begin |
| IV. Code Quality Standards | ✅ | mypy strict mode; same pyproject.toml config applies to all changes |
| V. Observability & Logging | ✅ | Existing request/response middleware covers all endpoints; no new logging required |
| VI. OpenAPI-First | ✅ | `openapi.yaml` updated with `as_of_date` field before endpoint implementation |

All six principles pass. No violations to document.

## Project Structure

### Documentation (this feature)

```text
specs/002-price-as-of-date/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── contracts/
│   └── openapi-diff.md  # Phase 1 output — schema change summary
└── tasks.md             # Phase 2 output (/speckit-tasks command)
```

### Source Code (files modified by this feature)

```text
market-data-web-service/
├── app/
│   ├── models/
│   │   └── pricing.py             # Add as_of_date: date field to PriceResponse
│   ├── providers/
│   │   └── yfinance_provider.py   # get_current_price(): switch from fast_info to history(period="5d")
│   └── services/
│       └── pricing_service.py     # get_current_price(): populate as_of_date in PriceResponse
├── tests/
│   ├── features/
│   │   └── current_price_as_of_date.feature  # 3 new BDD scenarios
│   └── steps/
│       └── current_price_as_of_date_steps.py # Step definitions for new scenarios
└── openapi.yaml                   # Updated with as_of_date field in PriceResponse schema
```

No new files or directories are added to the application code. All changes are modifications to existing modules or additions to the existing test structure.

## Complexity Tracking

> No violations — all constitution checks pass.

---

## Phase 0: Research Summary

See [research.md](research.md) for full decision log.

| Topic | Decision |
|-------|----------|
| Date source from yfinance | `Ticker.history(period="5d")` — last row's index date. `fast_info` has no date attribute in yfinance 1.3.0 (confirmed empirically). |
| Price source change | Switch from `fast_info.last_price` to `history(period="5d")` last row's `Close`. Guarantees price and date are from the same session (FR-004). |
| market_state source | `t.info.get("marketState")` — `fast_info` does not expose `market_state` as an attribute in yfinance 1.3.0; `t.info["marketState"]` returns e.g. `"REGULAR"`. |
| Backward compatibility | `as_of_date` is a new required field; all existing fields unchanged. Additive only. |
| New dependencies | None. `history()` is already used in `get_price_history()`; this reuses the same call pattern. |

---

## Phase 1: Design Artifacts

- [data-model.md](data-model.md) — updated PriceResponse schema with as_of_date field
- [contracts/openapi-diff.md](contracts/openapi-diff.md) — schema change to openapi.yaml

---

## Implementation Notes

### Provider Change (get_current_price)

Current approach uses `fast_info.last_price` which provides no date. New approach:

```python
def get_current_price(self, ticker: str) -> dict[str, object]:
    try:
        t = yf.Ticker(ticker)
        df = t.history(period="5d")
    except _NETWORK_ERRORS as exc:
        raise ProviderUnavailableError() from exc
    except Exception as exc:
        raise DataNotFoundError(ticker) from exc

    if df is None or df.empty:
        raise DataNotFoundError(ticker)

    # Get the most recent trading day with a valid close
    df = df[df["Close"] > 0]
    if df.empty:
        raise DataNotFoundError(ticker)

    last_row = df.iloc[-1]
    price = float(last_row["Close"])
    as_of_date = df.index[-1].date()

    try:
        info = t.fast_info
        currency = getattr(info, "currency", None)
        market_state = t.info.get("marketState")
    except Exception:
        currency = None
        market_state = None

    return {
        "price": price,
        "as_of_date": as_of_date,
        "currency": str(currency) if currency else "USD",
        "market_state": market_state,
    }
```

### Model Change (PriceResponse)

```python
from datetime import date, datetime

class PriceResponse(BaseModel):
    ticker: str
    price: float = Field(gt=0.0)
    currency: str
    timestamp: datetime
    market_status: Literal["open", "closed"]
    as_of_date: date   # NEW — trading date of the price observation
```

### BDD Reconciliation Test Strategy

The reconciliation scenario requires two API calls in one test. The step definitions use the shared `client` fixture and store intermediate results in a pytest fixture:

```python
@when("a client sends a GET request to /securities/MSFT/price", target_fixture="price_response")
def get_msft_price(client): ...

@when("a client also sends a GET request to /securities/MSFT/history with no date parameters",
      target_fixture="history_response")
def get_msft_history(client): ...

@then('the "as_of_date" in the price response matches the "date" of the last entry in the history "prices" list')
def reconcile_dates(price_response, history_response): ...
```
