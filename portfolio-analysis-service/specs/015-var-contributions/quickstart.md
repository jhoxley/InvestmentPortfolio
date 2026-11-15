# Quickstart: VaR Contributions (Marginal Risk) Endpoint

## Prerequisites

- Service set up per the README, with an account whose position ladder has been ingested.
- At least one completed VaR calculation run for that account (feature 012:
  `POST /v1/accounts/{account}/risk/var/runs`), run *after* this feature's `VarRunService` change
  that persists the scenario-returns snapshot. A run completed before this feature shipped has an
  estimate but no snapshot — step 4 demonstrates how that case is handled identically to "never
  computed".

## 1. Pick a date that already has a completed estimate

```powershell
curl.exe -s "http://127.0.0.1:8000/v1/accounts/HL-SIPP/risk/var?start=2026-09-22&end=2026-09-22" `
  | python -m json.tool
```

Note the `total_value_gbp`, `lookback_code` and one confidence level's `es_gbp` from the response —
these are the values the contributions breakdown must reconcile against in step 2.

## 2. Request the contributions breakdown, grouped by position

```powershell
curl.exe -s "http://127.0.0.1:8000/v1/accounts/HL-SIPP/risk/var/contributions?date=2026-09-22&lookback=2y&confidence=99&group_by=position" `
  | python -m json.tool
```

Expected: `200` with one `groups` entry per held position (including a `"Cash"` entry with all four
risk measures `0.0`). Sum `component_es_gbp` across every entry and confirm it matches step 1's
`es_gbp` for the same date/lookback/confidence within 0.5% (SC-001). The largest `component_es_gbp`
should belong to the account's largest/most volatile holding (sense-check against
`docs/proposals/value-at-risk.md` Appendix A's weight column).

## 3. Switch to theme grouping

```powershell
curl.exe -s "http://127.0.0.1:8000/v1/accounts/HL-SIPP/risk/var/contributions?date=2026-09-22&lookback=2y&confidence=99&group_by=theme" `
  | python -m json.tool
```

Expected: `200` with one `groups` entry per theme present in the account that day (plus `"Cash"` as
its own theme), `component_es_gbp` again summing to the same total ES as step 2 (the partition is
different, the total is identical). Any position whose `IdentifierMappingEntry` has no `theme` set
appears folded into an `"Unclassified"` entry.

## 4. Confirm the "not computed" contract

```powershell
curl.exe -s "http://127.0.0.1:8000/v1/accounts/HL-ISA/risk/var/contributions?date=2099-01-02&lookback=2y" `
  | python -m json.tool
```

(Pick a date outside anything computed, or an account with no run at all.)

Expected: `200`, `"date": null`, `"groups": []`, and `_links` containing `status` and `runs` — never
a `404` or `422` purely because nothing has been computed (FR-009).

## 5. Confirm the "insufficient quality" contract

```powershell
curl.exe -s "http://127.0.0.1:8000/v1/accounts/HL-SIPP/risk/var/contributions?date=2016-05-03&lookback=5y&confidence=99" `
  | python -m json.tool
```

(Pick an early date whose 5y look-back is known from `docs/proposals/value-at-risk.md` §4.5 to be
`insufficient` quality this far back in the account's history — confirm first via
`GET .../risk/var?start=2016-05-03&end=2016-05-03&lookback=5y`.)

Expected: `200`, `"quality": "insufficient"`, `"groups": []`, `total_value_gbp` still populated
(FR-010) — no fabricated figures.

## 6. Confirm malformed requests are rejected clearly

```powershell
curl.exe -s -o - -w "`nHTTP %{http_code}`n" `
  "http://127.0.0.1:8000/v1/accounts/HL-SIPP/risk/var/contributions?date=2026-09-22&group_by=sector"
```

Expected: `422` with `"type": "https://portfolio-analysis/errors/invalid-var-query"` and
`"fields": ["group_by"]` style detail (research.md §3) — the same problem type already produced by
an invalid `lookback` or `confidence` on the series endpoint, not a bespoke new type.

## 7. Confirm no market-data calls are made

With the market-data-web-service stopped (or its URL pointed somewhere unreachable), repeat step 2
against an account/date/lookback that already has a persisted snapshot. Expected: still `200` with
the full breakdown — this endpoint never calls `ObservedPriceClient` (FR-007, SC-002).
