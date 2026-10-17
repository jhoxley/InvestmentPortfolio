# Quickstart: VaR Series, Backtest and Methods Endpoints

## Prerequisites

- Service set up per the README, with an account whose position ladder has been ingested.
- At least one completed VaR calculation run for that account (feature 012:
  `POST /v1/accounts/{account}/risk/var/runs`). Without one, the series/backtest endpoints
  still respond successfully (empty series / zero observations) — step 4 demonstrates this.

## 1. Discover the configured method

```powershell
curl.exe -s "http://127.0.0.1:8000/v1/risk/var/methods" | python -m json.tool
```

Expected: `200` listing `lookbacks` (with one marked `"is_headline": true`),
`confidence_levels_bp`, and a static `measures` list. No account required.

## 2. Read the headline series

```powershell
curl.exe -s "http://127.0.0.1:8000/v1/accounts/HL-SIPP/risk/var?start=2026-01-01&end=2026-03-31" `
  | python -m json.tool
```

Expected: `200` with `lookback_code` equal to the configured headline (default `"2y"`), one
`series` entry per business date in range that has a stored estimate, each with `levels`
for every configured confidence level. Spot-check one date's `var_gbp`/`es_gbp` against
`data/HL-SIPP/var/estimates.csv` directly.

## 3. Narrow the look-back and confidence level

```powershell
curl.exe -s "http://127.0.0.1:8000/v1/accounts/HL-SIPP/risk/var?lookback=1y&confidence=99" `
  | python -m json.tool
```

Expected: every `series[].levels` array has exactly one entry, `confidence_bp: 9900`, and the
figures match the `1y` look-back's stored row, not `2y`/`5y`.

## 4. Confirm the empty-series contract

```powershell
curl.exe -s "http://127.0.0.1:8000/v1/accounts/HL-ISA/risk/var?start=2099-01-01&end=2099-01-02" `
  | python -m json.tool
```

(Pick a range outside anything computed, or a freshly-ingested account with no run yet.)

Expected: `200`, `"series": []`, and `_links` containing `status` and `runs` — never a `404` or
`422` purely because nothing has been computed.

## 5. Run the backtest

```powershell
curl.exe -s "http://127.0.0.1:8000/v1/accounts/HL-SIPP/risk/var/backtest?confidence=99" `
  | python -m json.tool
```

Expected: `200` with one `levels` entry (`confidence_bp: 9900`) reporting
`observation_count`, `exception_count`, `kupiec_lr`/`kupiec_p_value`,
`christoffersen_independence_lr`/`_p_value`, `conditional_coverage_lr`/`_p_value`, `zone`
(one of `green`/`yellow`/`red`), `exception_dates`, `mean_var_gbp`, and `var_stability`.
Cross-check `exception_count` by hand: it is the number of dates where
`hypothetical_pnl_gbp < -var_99_gbp` among dates with quality `ok`/`degraded` and a
realised outcome.

## 6. Switch PnL basis and minimum quality

```powershell
curl.exe -s "http://127.0.0.1:8000/v1/accounts/HL-SIPP/risk/var/backtest?confidence=99&pnl_basis=ladder&min_quality=ok" `
  | python -m json.tool
```

Expected: `observation_count` drops to (at most) the number of `ok`-quality dates, and
`exception_count` reflects `ladder_pnl_gbp` instead of `hypothetical_pnl_gbp`.

## 7. Request the rolling exception series

```powershell
curl.exe -s "http://127.0.0.1:8000/v1/accounts/HL-SIPP/risk/var/backtest?confidence=99&rolling=true" `
  | python -m json.tool
```

Expected: `levels[0].rolling_exceptions` is a non-null list, one point per date from the
250th included observation onward, each `exception_count` between 0 and 250.

## 8. Confirm invalid-request handling

```powershell
curl.exe -s -i "http://127.0.0.1:8000/v1/accounts/HL-SIPP/risk/var?lookback=3y"
curl.exe -s -i "http://127.0.0.1:8000/v1/accounts/HL-SIPP/risk/var?confidence=90"
curl.exe -s -i "http://127.0.0.1:8000/v1/accounts/does-not-exist/risk/var"
```

Expected: the first two return `422` with `type` ending `invalid-var-query` and a
`correlation_id`, naming the supported values in `detail`; the third returns `404`
(`account-not-found`), consistent with the performance and VaR run endpoints.
