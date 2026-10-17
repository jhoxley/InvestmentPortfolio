# Script contracts

## `refresh-var.ps1` (repository root, new)

```
.\refresh-var.ps1 [-BaseUrl <url>] [-Accounts <string[]>] [-Mode missing|full]
                  [-TimeoutMinutes <int>] [-PollSeconds <int>]
```

| Parameter | Default | Meaning |
|---|---|---|
| `-BaseUrl` | `http://127.0.0.1:8000` | portfolio-analysis-service base URL |
| `-Accounts` | every account from `GET /v1/accounts` with a `position_ladder` | Accounts to refresh |
| `-Mode` | `missing` | Run mode |
| `-TimeoutMinutes` | `15` | Per-account wait limit |
| `-PollSeconds` | `2` | Polling interval |

Behaviour per account, in sequence:
1. `POST /v1/accounts/{a}/risk/var/runs` with `{"mode": "<Mode>"}`.
2. On 409, adopt the active run from `_links.active_run` and wait for it.
3. Poll `GET` on the run until `succeeded` or `failed`, or until the timeout passes.
4. Log the account, status, `dates_computed`, warning count (and up to 5 warnings) and the
   failure detail.

**Exit codes**: `0` if every account succeeded; `1` if any account failed, timed out, or could not
be queued (other than adopting an active run).

## `run_end_to_end.ps1` (modified)

* New **Phase 7 "Compute Value at Risk"** after Phase 6 (capital ingestion). For each account in
  `$SubAccountLedgers` that ingested successfully, it runs the same queue-and-poll routine as
  `refresh-var.ps1` (shared helper), with mode `missing` and a 15-minute timeout.
* A failure or timeout logs at Error level and sets `$OverallSuccess = $false`. Processing continues.
* The existing "Start Investment Portfolio Browser" phase is renumbered to Phase 8 and always runs.
