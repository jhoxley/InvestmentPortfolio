# Data Model: Historical-Simulation VaR Calculation Runs

All money is in GBP. Confidence levels are held as integer basis points (9500, 9750, 9900) and
shown as decimals (0.95, 0.975, 0.99) at the API boundary. Business days are Mon–Fri.

## Domain objects (in memory)

### PositionExposure
| Field | Type | Notes |
|---|---|---|
| sub_account | str | Ladder sub-account name |
| identifier | str | `ticker or isin` from the identifier mapping (same rule as pricing) |
| market_value | float | > 0 (zero-value positions are excluded) |

### Exposure (one account, one date)
| Field | Type | Notes |
|---|---|---|
| as_of | date | |
| positions | tuple[PositionExposure, ...] | Non-Cash, market value > 0 |
| cash_value | float | Cash sub-account market value (≥ 0) |
| risky_value | float | Σ position market values |
| total_value | float | risky_value + cash_value |
| fingerprint | str | sha256 hex (research §8) |

### ProxyConfig (per identifier)
| Field | Type | Default | Validation |
|---|---|---|---|
| proxy | str \| None | None | Identifier priced by market-data |
| mode | `fill_gaps` \| `always` | `fill_gaps` | Unknown values → mapping load error |
| scale | float | 1.0 | Must be > 0 |

### ReturnPanel
| Field | Type | Notes |
|---|---|---|
| grid | ndarray[date] (T) | Business days covering every needed window plus the outcome days |
| identifiers | tuple[str, ...] (m) | Held identifiers plus proxies |
| returns | ndarray[float] (T × m) | NaN = missing (before first observation, or excluded) |
| observed | ndarray[bool] (T × m) | True only where a real price was observed that day (and not excluded) |
| first_observed | dict[str, date \| None] | From market-data `first_observed_date` |

### Treatment (enum)
`actual`, `proxied`, `rescaled`, used per position per window and in the status.

### Quality (enum)
`ok`, `degraded`, `insufficient`.

## Persisted records (`data/{account}/var/`)

### estimates.csv: one row per (date, lookback_days)
| Column | Type | Notes |
|---|---|---|
| date | date | As-of date |
| method | str | `historical-simulation` |
| lookback_code | str | `1y` / `2y` / `5y` |
| lookback_days | int | 260 / 520 / 1300 |
| scenario_count | int | n after exclusions |
| excluded_scenarios | int | L − n |
| actual_mv_pct, proxied_mv_pct, rescaled_mv_pct | float | Share of risky value; sum to 100 (or 100/0/0 when risky value is 0) |
| quality | str | `ok` / `degraded` / `insufficient` |
| quality_reason | str | Empty unless degraded or insufficient |
| var_9500_gbp, var_9750_gbp, var_9900_gbp | float \| empty | Empty when insufficient |
| es_9500_gbp, es_9750_gbp, es_9900_gbp | float \| empty | Empty when insufficient |
| row_fingerprint | str | Same as the date's outcome fingerprint |
| methodology_version | str | |
| run_id | str | Run that computed the row |
| computed_at | datetime (UTC, ISO) | |

Key: (date, lookback_days). Unique. Upsert replaces all rows of a recomputed date.

### outcomes.csv: one row per date
| Column | Type | Notes |
|---|---|---|
| date | date | As-of date |
| outcome_date | date | Next business day |
| outcome_status | str | `realised` / `pending` |
| total_value_gbp | float | Including Cash |
| risky_value_gbp | float | |
| hypothetical_pnl_gbp | float \| empty | Empty when pending |
| ladder_pnl_gbp | float \| empty | Empty when pending |
| row_fingerprint | str | Holdings + config fingerprint |
| run_id, computed_at | | |

### instruments.csv: last successful run's view
| Column | Type | Notes |
|---|---|---|
| identifier | str | |
| sub_accounts | str | Names joined with `;` |
| first_observed_date, last_observed_date | date \| empty | From market-data |
| proxy, proxy_mode, proxy_scale | | Configured values |
| treatment_1y, treatment_2y, treatment_5y | str | Treatment at the **latest computed date** for that window (column names follow the configured look-back codes) |
| outlier_count | int | Returns above the outlier threshold seen in the run's panel |

### meta.json
```json
{
  "account_name": "HL-SIPP",
  "methodology_version": "1.0.0",
  "config_fingerprint": "<sha256>",
  "last_successful_run_id": "<uuid>",
  "updated_at": "2026-10-03T21:00:00Z"
}
```

### runs/{run_id}.json: VarRun
| Field | Type | Notes |
|---|---|---|
| run_id | str (uuid4) | |
| account_name | str | |
| mode | `missing` \| `full` | |
| requested_start, requested_end | date \| null | As supplied |
| resolved_start, resolved_end | date \| null | Clipped to the ladder range when the run starts |
| status | `queued` \| `running` \| `succeeded` \| `failed` | |
| requested_at, started_at, finished_at | datetime \| null | UTC |
| correlation_id | str | Correlation ID of the POST request that created the run |
| dates_selected | int | Dates chosen for computation |
| dates_computed | int | Dates written |
| dates_skipped | int | Ladder dates in the run's range that were not selected |
| dates_missing, dates_stale, outcomes_pending_filled | int | Breakdown of the selection |
| warnings | list[RunWarning] | |
| failure | RunFailure \| null | `{type, title, detail, reason, run_id, correlation_id}`; reason ∈ market_data_unavailable, observed_history_unsupported, interrupted, internal_error |

**RunWarning**: `{kind: "outlier" | "proxy_unresolved" | "instrument_not_found" | "excluded_price",
identifier, date | null, value | null, message}`.

### State transitions (VarRun.status)
```
(created) ──► queued ──► running ──► succeeded
                │           └──────► failed (market data / unsupported / internal)
                └──(service restart)─► failed (interrupted)
running ──(service restart)──► failed (interrupted)
```
Only `queued` and `running` count as **active** for the 409 rule.

## Validation rules

| Rule | Source | Error |
|---|---|---|
| mode ∈ {missing, full}; default `missing` | FR-017 | 422 `invalid-var-run-request` |
| start ≤ end when both are given; ISO dates | FR-025 | 422 `invalid-var-run-request` |
| account name pattern | FR-025 | 422 `invalid-account-name` (existing) |
| account has any ingested resource | FR-025 | 404 `account-not-found` (existing) |
| account has a position ladder | FR-025 | 422 `missing-required-source` (existing) |
| no active run for the account | FR-019 | 409 `var-run-in-progress` |
| run id exists for that account | FR-020 | 404 `var-run-not-found` |

All three new problem types add `correlation_id` to the standard problem-details fields (FR-033).
| `var_proxy_scale` > 0; mode in the enum | FR-008 | Mapping load error: logged; a run started with it fails `internal_error` naming the entry |

A requested range is clipped to the ladder's range. A range with no ladder dates is a valid run that
computes 0 dates.

## Relationships

```
Account 1──* VarRun
Account 1──* Outcome (per date) 1──* Estimate (per look-back)
Estimate *──1 Exposure (same date, same fingerprint)
Instrument (identifier) 0..1──1 ProxyConfig ──► proxy Instrument
```
