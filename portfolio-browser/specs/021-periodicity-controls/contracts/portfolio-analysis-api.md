# Contract: portfolio-analysis-service — the `periodicity` parameter this UI consumes

**Feature**: `021-periodicity-controls` | **Date**: 2026-09-22
**Upstream source of truth**: `portfolio-analysis-service/specs/008-periodicity-timeseries/contracts/openapi.yaml`

This UI consumes two existing endpoints and adds one query parameter to each. Nothing else about
the calls changes.

---

## Endpoints used

| Page | Endpoint | Existing params this UI already sends |
|---|---|---|
| Overview | `GET /v1/accounts/{account_name}/timeseries` | `attribute` (repeated), `start`, `end` |
| Positions | `GET /v1/accounts/{account_name}/position` | `position` (repeated), `attribute` (repeated), `start`, `end` |

---

## The added parameter

| Name | In | Required | Values | Behaviour when omitted |
|---|---|---|---|---|
| `periodicity` | query | no | `day`, `week`, `month`, `quarter`, `annual` | The service treats the request as `day` — byte-identical to the pre-008 response |

**Matched case-sensitively.** `Annual`, `yearly`, `daily` and `Q` are all rejected. This UI can
only ever send one of the five values, since they come from a validated closed config list — so a
422 from this parameter indicates a bug in the UI, not user input.

### UI label → API value mapping

| Button label (UI) | Value sent |
|---|---|
| day | `day` |
| week | `week` |
| month | `month` |
| quarter | `quarter` |
| **year** | **`annual`** |

The final row is the only divergence between the two vocabularies, and it lives in
`config/content.yaml` rather than in code.

---

## Response shape

Aggregated responses use the **same** entry shape as daily ones — this is what lets the existing
figure builders plot them unchanged:

```json
{
  "account_name": "HL-SIPP",
  "attributes": ["capital", "market_value"],
  "from_date": "2016-04-20",
  "to_date": "2025-12-31",
  "periodicity": "annual",
  "entries": [
    { "date": "2016-04-20", "capital": 8904.82, "market_value": 9120.44 },
    { "date": "2017-01-02", "capital": 21000.00, "market_value": 22880.12 }
  ],
  "_links": { "self": "...", "attributes": "...", "accounts": "..." }
}
```

Guarantees this UI relies on:

| Guarantee | Consequence for the UI |
|---|---|
| `periodicity` is echoed on **every** response, including when it defaulted to `day` | Its absence means the service predates 008 → log a warning (research.md §6) |
| `from_date` / `to_date` always describe the resolved **daily** range, unaffected by the interval | The date pickers need no adjustment when the interval changes |
| Each entry is dated at its window's **start**, clamped to `from_date` for the first window | No entry date ever falls outside the picked range, so the x-axis needs no widening |
| Each value is the **last observation** within the window, all attributes from one source date | Hover tooltips remain internally consistent |
| A window with no observation is **omitted**, not returned as null | No null-handling is needed in the figure builders |
| Entries are ordered by date ascending | Existing plotting order holds |
| On the position endpoint, window dates are **identical across positions** | Stacked-area mode still aligns bands (FR-014) |

### Position endpoint caveat this UI must not misrepresent

Under any interval other than `day`, `position_return` and `weighted_position_return` carry the
**last single-day return** within each window — *not* a compounded period return. The UI must not
relabel, rescale or otherwise imply a period return (Principle I forbids re-deriving it here
anyway).

---

## Errors

No new error handling. The existing `PortfolioAnalysisServiceError` → error-state path already
covers every non-2xx, timeout and connection failure, including the 422
`unsupported-periodicity` problem document that a bad value would produce.

| Status | Body | UI behaviour |
|---|---|---|
| 200 | as above | plot it |
| 404 / 422 / 5xx / timeout | RFC 7807 problem document | existing error state, unchanged |

---

## ⚠️ Deployment prerequisite (verified 2026-09-22)

The analysis service instance running on `127.0.0.1:8000` at the time of planning **predates 008**
and silently ignores this parameter:

- `?periodicity=month` over 2016→2025 returned **daily** entries
- the response body contained **no** `periodicity` field
- `?periodicity=fortnight` returned **200**, not the specified 422

The 008 code is implemented and its tests pass, but the process must be **restarted** before this
UI feature can be developed or verified end to end. The echoed-field warning described above
exists so that this situation is diagnosable rather than silent.
