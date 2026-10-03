# Quickstart: Historical-Simulation VaR Calculation Runs

## Prerequisites

- Service set up per the README, with an account whose position ladder has been ingested (feature
  001/002/006). The same prerequisite as the performance endpoints.
- market-data-web-service running **with feature 009** (`fill=none` support). Without it, runs fail
  with reason `observed_history_unsupported`, which is expected behaviour.
- Optional: proxies in the identifier mapping file, e.g.

```json
{ "name": "Scottish Widows Pension", "isin": "SWPENSION", "ticker": "", "theme": "Other Pension",
  "var_proxy": "GB00B08HD927", "var_proxy_mode": "always", "var_proxy_scale": 1.0 }
{ "name": "Lindsell Train Global Equity Class D - Accumulation (GBP)", "isin": "", "ticker": "0P0001WUUI.L",
  "theme": "Global", "var_proxy": "IE00BJSPMJ28" }
```

## 1. Queue a full run

```powershell
curl.exe -s -i -X POST "http://127.0.0.1:8000/v1/accounts/HL-SIPP/risk/var/runs" `
  -H "Content-Type: application/json" -d '{\"mode\": \"full\"}'
```

Expected: `HTTP/1.1 202 Accepted` with a `Location` header, and a body with `"status": "queued"` and
`_links.self`.

## 2. Poll the run

```powershell
curl.exe -s "http://127.0.0.1:8000/v1/accounts/HL-SIPP/risk/var/runs/<run_id>" | python -m json.tool
```

The status moves `queued` → `running` → `succeeded`. The first run per account may take minutes,
because market-data fetches pre-holding history from yfinance. `dates_computed` should equal the
number of ladder business days (about 2,700 for HL-SIPP). `warnings` lists outliers and unresolved
proxies.

A second POST while the run is active returns **409** with `_links.active_run`.

## 3. Inspect the store

```
data/HL-SIPP/var/estimates.csv   # 3 rows per date (1y/2y/5y): VaR/ES at 95/97.5/99, coverage, quality
data/HL-SIPP/var/outcomes.csv    # 1 row per date: hypothetical & ladder PnL; the newest row is "pending"
data/HL-SIPP/var/instruments.csv # treatment per instrument and look-back
data/HL-SIPP/var/runs/<run_id>.json
```

Sanity checks:
- Estimates for the latest date at 2y should be mostly `ok`, with proxied share ≈ 4.5% (Scottish
  Widows + WisdomTree, if configured).
- VaR at 99% ≥ 97.5% ≥ 95%, and ES ≥ VaR at each level.
- `ladder_pnl_gbp` ≈ the performance endpoint's daily return for the outcome date × the previous
  day's total value.

## 4. Status

```powershell
curl.exe -s "http://127.0.0.1:8000/v1/accounts/HL-SIPP/risk/var/status" | python -m json.tool
```

Expect `missing_dates: 0`, a `computed_range` equal to the `ladder_range`, `pending_outcomes: 1`, and
the `instruments` list (e.g. Lindsell Train D Acc: `1y: actual`, `2y: proxied`, `5y: proxied`).

## 5. Incremental refresh

```powershell
.\refresh-var.ps1 -Accounts HL-SIPP        # from the repository root
```

With nothing changed, the run reports `dates_computed` equal to the count of pending outcomes that
became realised (normally 0), and the script exits 0. To check staleness, change a proxy's
`var_proxy_scale`, rerun, and confirm every date is recomputed.

## 6. Interrupted run recovery

Queue a full run, stop uvicorn while it's `running`, then restart. Reading the run shows
`"status": "failed"` with `failure.reason = "interrupted"`.

## 7. End-to-end pipeline

Run `run_end_to_end.ps1`. Phase 7 "Compute Value at Risk" logs each account's run outcome, and
Phase 8 starts the browser even if a VaR run failed.

## 8. Quality gates

```powershell
ruff check app/ tests/ ; ruff format --check app/ tests/ ; mypy --strict app/ ; pytest
```
