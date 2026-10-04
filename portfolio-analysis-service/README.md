# Portfolio Analysis Service

A locally hosted FastAPI web service that ingests sub-account ledger files produced by the `AccountPreparationPipeline` scripts, expands them into full daily position ladders, and exposes the results via a REST API.

---

## 1. Service Summary

The service accepts an XLSX file describing the historical trading and income activity for one portfolio account. Each file contains sparse rows — one per activity event per sub-account — keyed by date. The service expands this sparse input into a **daily position ladder**: one row per sub-account per business day (Mon–Fri), from the earliest activity date through T-2 (today minus two business days), forward-filling each position's values across dates with no activity.

### Current Capabilities

| Feature | Endpoint | Status |
|---|---|---|
| Ingest a new sub-account ledger | `POST /v1/accounts/{account}/ladder` | Available |
| Retrieve ladder summary (metadata) | `GET /v1/accounts/{account}/ladder` | Available |
| Download the full ladder as XLSX | `GET /v1/accounts/{account}/ladder/download` | Available |
| Daily return histogram and distribution statistics (risk) | `GET /v1/accounts/{account}/risk/return-histogram` | Available |
| Queue a historical-simulation VaR calculation run (risk) | `POST /v1/accounts/{account}/risk/var/runs` | Available |
| Read a VaR run's status, or list an account's runs | `GET /v1/accounts/{account}/risk/var/runs[/{run_id}]` | Available |
| VaR coverage, freshness and per-instrument treatment (risk) | `GET /v1/accounts/{account}/risk/var/status` | Available |
| Read an account's previously computed VaR/ES series and outcomes (risk) | `GET /v1/accounts/{account}/risk/var` | Available |
| Backtest an account's VaR estimates against realised outcomes (risk) | `GET /v1/accounts/{account}/risk/var/backtest` | Available |
| Describe the supported VaR method, look-backs and measures (risk) | `GET /v1/risk/var/methods` | Available |
| Liveness probe | `GET /health` | Available |
| Readiness probe | `GET /ready` | Available |

### Key Behaviours

- **Forward-fill:** Each sub-account's values (`book_cost`, `quantity`, `total_income`) are carried forward across business days with no activity record.
- **Periodicity:** `GET /v1/accounts/{account}/timeseries` and `GET /v1/accounts/{account}/position` accept an optional `periodicity` of `day` (default), `week`, `month`, `quarter` or `annual`. Windows are aligned to the real calendar — Monday, the 1st of the month, 1 Jan/Apr/Jul/Oct, and 1 Jan respectively — not to the requested dates. Each entry is dated at its window's start business day (clamped to the resolved start for the first window) and carries the **last** observation of each attribute in that window, all from one source date. Omitting the parameter reproduces the per-business-day response exactly; `from_date`/`to_date` always describe the resolved daily range. Note that `position_return` and `weighted_position_return` therefore report the last *single-day* return in the window, not a compounded period return.
- **Risk — daily return histogram:** `GET /v1/accounts/{account}/risk/return-histogram?start=&end=` buckets the account's portfolio-level daily returns (the same per-business-day series the performance endpoints use: the sum of `weighted_position_return` across sub-accounts) into whole basis points (1 bp = 0.01%, rounded half away from zero). `histogram` is a list of `[bucket_bps, count]` pairs, sorted ascending, with empty buckets omitted. `statistics` reports `count`, `mean`, `median`, `mode`, `minimum`, `maximum`, the sample `std_dev` with `std_dev_bands` (for 1, 2 and 3 sigma: the multiple plus the lower/upper edges around the mean), `skewness` and excess `kurtosis`; values that are undefined for the available observations are `null`. `start`/`end` default and adjust exactly as for the performance endpoint.
- **Equity closure rule:** When a non-Cash sub-account's `quantity` reaches zero it is excluded from all subsequent dates. The date on which it reaches zero is its final row.
- **Cash always persists:** The `Cash` sub-account is never subject to the closure rule; it appears on every business day regardless of balance.
- **Idempotency:** Submitting the same file twice is a no-op (SHA-256 checksum match). The response indicates `status: unchanged` with HTTP 200.
- **Merge guard:** Submitting a *different* file for an account that already has a stored ladder returns HTTP 409. Merge/replace is not yet supported.
- **Local file store:** Ladders are written to `data/{account_name}/ladder.xlsx` and `meta.json`. The store is human-readable and suitable for manual inspection.
- **Risk — VaR calculation runs:** `POST /v1/accounts/{account}/risk/var/runs` (`mode: "full"` or `"missing"`, optional `start`/`end`) queues a historical-simulation Value-at-Risk calculation and returns 202 immediately with a run resource; the calculation itself runs in the background, one run at a time across all accounts. `GET .../risk/var/runs/{run_id}` reads a run's status (`queued`/`running`/`succeeded`/`failed`); `GET .../risk/var/runs?limit=` lists an account's runs, newest first. A second request for an account that already has an active run gets HTTP 409, linking to that run. `mode: "missing"` (the default) recomputes only dates with no estimate, a changed fingerprint (holdings or configuration), or a now-resolvable pending outcome — a no-op `missing` run after nothing has changed computes 0 dates and makes no market-data calls. Results are stored per account under `data/{account}/var/` (`estimates.csv`, `outcomes.csv`, `instruments.csv`, `meta.json`, `runs/{run_id}.json`). For every business date, VaR and Expected Shortfall are computed at 95%/97.5%/99% for 1Y/2Y/5Y look-backs from the historical simple returns of that date's holdings (observed prices only, via market-data-web-service's `fill=none`, never gap-filled); missing or sparse price history falls back to a configured proxy instrument, then to a value-weighted rescale of the account's other holdings. A run that cannot reach market-data-web-service, or finds it does not support observed-only history, fails closed (`market_data_unavailable` / `observed_history_unsupported`) rather than silently using filled prices. Any run still `queued`/`running` when the service restarts is marked `failed` with reason `interrupted`. `GET /v1/accounts/{account}/risk/var/status` reports the computed date range against the ladder's own range, missing/stale/pending counts, the last run, and each instrument's observed-history treatment (`actual`/`proxied`/`rescaled`) per look-back, without reading the ladder file itself. See `docs/proposals/value-at-risk.md` for the full methodology.
- **Risk — VaR series, backtest and methods (read-only):** `GET /v1/accounts/{account}/risk/var?start=&end=&lookback=&confidence=` reads feature 012's stored estimates/outcomes for the resolved date range (as for the performance endpoints), one look-back (`1y`/`2y`/`5y`, repeatable `confidence` as percentages, default the configured headline and every configured level respectively). Each entry reports scenario count, coverage percentages, quality, per-confidence VaR/ES (GBP and %), and the realised hypothetical/ladder PnL and exception flags for its outcome date; `insufficient`-quality dates and pending outcomes still appear with the affected fields `null`. An account with nothing computed gets a successful empty series with `status`/`runs` links, never an error. Never triggers a calculation. `GET /v1/accounts/{account}/risk/var/backtest?pnl_basis=&min_quality=&rolling=` reports, per confidence level, observation/exception counts, expected exceptions, exception rate, Kupiec proportion-of-failures and Christoffersen independence/conditional-coverage likelihood ratios and p-values (stdlib `math.erfc`/`exp`/`lgamma` only), a Basel-style traffic-light zone (reproduces 0–4/5–9/10+ at 250 days/99%), exception dates, mean VaR, VaR stability, and an optional 250-day rolling exception count. `insufficient`-quality and pending-outcome dates are always excluded from the observation set regardless of `min_quality` (`ok`/`degraded`, default `degraded`); an excluded date breaks the independence transition chain for its neighbours rather than being skipped over. `GET /v1/risk/var/methods` describes the configured method, look-backs (with the headline marked), confidence levels and measures, for building UI controls; needs no account. An unsupported `lookback`/`confidence`/`pnl_basis`/`min_quality` value is rejected with `invalid-var-query` (422), naming the supported values. See `docs/proposals/value-at-risk.md` §4 for the backtesting methodology.

---

## 2. Running Locally

### Prerequisites

- Python 3.11 or later
- `pip`

### Setup

```bash
cd portfolio-analysis-service

# Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

# Install dependencies
pip install -r requirements.txt
```

### Start the Server

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

The server starts at `http://127.0.0.1:8000`. The `--reload` flag enables auto-restart on file changes during development.

### Configuration

Runtime configuration is read from `config.yaml` in the working directory. The only current setting is the data directory:

```yaml
# config.yaml
data:
  directory: ./data
```

To redirect the data store to a different path, edit this file before starting the server. The directory is created automatically on startup if it does not exist.

The VaR calculation (`var:`) is entirely optional to configure — every field has a sensible default matching `docs/proposals/value-at-risk.md`:

```yaml
var:
  methodology_version: "1.0.0"
  lookbacks: {"1y": 260, "2y": 520, "5y": 1300}
  confidence_levels_bp: [9500, 9750, 9900]        # 95%, 97.5%, 99%
  min_observed_share_per_scenario: 0.5            # scenario days below this coverage are excluded
  sparse_density_threshold: 0.8                   # below this, an instrument is treated as sparse (proxy "always")
  outlier_abs_return: 0.25                        # |return| above this is reported as a warning
  quality:
    ok_max_rescaled_pct: 5
    ok_max_proxied_pct: 25
    insufficient_min_scenario_ratio: 0.8
    insufficient_max_rescaled_pct: 20
  excluded_returns:                               # configured bad prices to treat as missing
    - identifier: "GB0031348658"
      date: "2026-02-10"
  headline_lookback: "2y"                         # default look-back for the series/backtest endpoints;
                                                   # must be a key of lookbacks (validated at startup)
```

Instruments needing a proxy (short or sparse price history) are configured per instrument in the identifier mapping file (`identifier_mapping.path`), not in `config.yaml`:

```json
{ "name": "Scottish Widows Pension", "isin": "SWPENSION", "ticker": "",
  "var_proxy": "GB00B08HD927", "var_proxy_mode": "always", "var_proxy_scale": 1.0 }
```

`var_proxy` is the identifier whose returns stand in for this instrument's; `var_proxy_mode` is `"fill_gaps"` (default — use the proxy only where this instrument has no return) or `"always"`; `var_proxy_scale` (default `1.0`) is a static multiplier applied to the proxy's returns. All three fields are optional and backward-compatible with existing mapping entries.

---

## 3. Build, Type Check, Lint, and Test

All tooling is configured in `pyproject.toml`. Commands assume the virtual environment is active.

### Install Dev Dependencies

```bash
pip install -r requirements-dev.txt
```

### Linting and Formatting (ruff)

```bash
# Check for issues
ruff check app/ tests/

# Auto-fix safe issues
ruff check app/ tests/ --fix

# Format code
ruff format app/ tests/
```

ruff enforces: import order (`I`), pyupgrade (`UP`), bugbear (`B`), simplify (`SIM`), annotations (`ANN`), Google-style docstrings (`D`), and standard error/warning rules (`E`, `F`, `W`).

### Type Checking (mypy)

```bash
mypy --strict app/
```

### Running Tests (pytest)

```bash
# All tests
pytest

# Unit tests only
pytest tests/unit/ -v

# BDD feature tests only
pytest tests/steps/ -v

# Filter by user story tag
pytest tests/steps/ -m us1 -v    # ingestion
pytest tests/steps/ -m us2 -v    # retrieval
pytest tests/steps/ -m us3 -v    # idempotency
pytest tests/steps/ -m us4 -v    # merge guard
pytest tests/steps/ -m validation -v

# Performance smoke tests
pytest tests/unit/test_performance.py -v
```

All tests use an isolated temporary data directory (via `pytest`'s `tmp_path` fixture); no real `data/` directory is written during the test run.

---

## 4. Key Design Principles and How to Extend

### Architecture

```
POST /v1/accounts/{name}/ladder
        │
        ▼
  LedgerValidator          ← validates schema, date range (T-2 boundary)
        │
        ▼
  LadderExpander           ← expands sparse rows → dense business-day series
        │
        ▼
  IngestionService         ← orchestrates checksum, validate, expand, persist
        │
        ▼
  LadderRepository         ← writes ladder.xlsx + meta.json atomically
```

### Design Principles

| Principle | Implementation |
|---|---|
| **Single responsibility** | Each class does one thing: validate, expand, persist, or orchestrate |
| **Dependency injection** | FastAPI `Depends()` wires `LadderRepository → IngestionService → endpoint` |
| **Idempotency via checksum** | SHA-256 of the raw file bytes; checked before any processing |
| **Atomic writes** | `tempfile.mkstemp(suffix=".xlsx")` + `os.replace()` prevents partial files |
| **RFC 7807 errors** | All error responses use `application/problem+json` with `type`, `title`, `status`, `detail`, `instance` |
| **HATEOAS links** | Every success response includes `_links.self` and `_links.download` |
| **Structured logging** | `structlog` with JSON output; correlation ID bound per request via `contextvars` |
| **T-2 boundary** | Expansion ends at `today - 2 business days` using `pandas.bdate_range` |

### How to Extend

**Adding a new endpoint:**
1. Add a new route function in `app/api/ladder.py` (or a new router file for a different domain).
2. Register the router in `app/main.py` via `app.include_router(...)`.
3. Add Gherkin scenarios in `tests/features/` and step implementations in `tests/steps/`.

**Adding a new validation rule:**
1. Add a private method to `LedgerValidator` in `app/validators/ledger.py`.
2. Call it from `LedgerValidator.validate()`.
3. Raise `SchemaValidationError` or `EmptyDateRangeError` as appropriate.
4. Add a unit test to `tests/unit/test_ledger_validator.py`.

**Adding a new exception type:**
1. Define the exception class in `app/exceptions.py`.
2. Register an `@app.exception_handler` in `app/main.py` returning a `_problem(...)` response.
3. Raise the exception from the relevant service or endpoint.

**Supporting ledger merges (currently 409):**
The merge path is stubbed in `IngestionService.ingest()`. When ready to implement, replace the `raise MergeNotSupportedError(...)` branch with merge logic (e.g. union of date ranges, conflict resolution strategy), then update or remove the `@us4` BDD scenario.

**Changing the storage format:**
`LadderRepository` is the single point of storage access. Swap out the `write()` / `read_xlsx()` / `read_meta()` implementation to target a database, cloud blob storage, or Parquet without touching any other code.

---

## 5. Programmatic Client Usage

The service exposes a standard REST JSON API. Below are Python examples using `httpx` (or the standard `requests` library).

### Ingest a Ledger

```python
import httpx

BASE = "http://127.0.0.1:8000"

with open("my_portfolio_ledger.xlsx", "rb") as f:
    response = httpx.post(
        f"{BASE}/v1/accounts/my-portfolio/ladder",
        files={"file": ("ledger.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )

response.raise_for_status()
body = response.json()

print(body["status"])           # "created" or "unchanged"
print(body["row_count"])        # total rows in the expanded ladder
print(body["from_date"])        # earliest date in the ladder
print(body["to_date"])          # latest date (T-2)
print(body["sub_accounts"])     # ["Cash", "Equity A", ...]
print(body["_links"]["download"])  # URL to download the XLSX
```

### Retrieve Ladder Summary

```python
response = httpx.get(f"{BASE}/v1/accounts/my-portfolio/ladder")
response.raise_for_status()
summary = response.json()

print(summary["row_count"])
print(summary["from_date"])
print(summary["to_date"])
```

### Download the Full Ladder XLSX

```python
import pandas as pd
import io

response = httpx.get(f"{BASE}/v1/accounts/my-portfolio/ladder/download")
response.raise_for_status()

df = pd.read_excel(io.BytesIO(response.content), engine="openpyxl")
print(df.head())
# Columns: date | sub_account | book_cost | quantity | total_income
```

### Error Handling

All errors return `application/problem+json`. The `status` field matches the HTTP status code.

```python
response = httpx.post(f"{BASE}/v1/accounts/bad name!/ladder", files=...)
if response.status_code == 422:
    error = response.json()
    print(error["type"])    # "https://portfolio-analysis/errors/invalid-account-name"
    print(error["detail"])  # human-readable explanation
```

| Status | Error type slug | Cause |
|---|---|---|
| 422 | `invalid-account-name` | Account name contains illegal characters or exceeds 64 chars |
| 422 | `schema-validation-failed` | Missing column, non-numeric value, unparseable date, empty file, or non-XLSX file |
| 422 | `empty-date-range` | Earliest activity date is within T-2 (too recent to produce any ladder rows) |
| 404 | `account-not-found` | No ladder stored for this account |
| 409 | `merge-not-supported` | A different file was submitted for an account that already has a ladder |
| 422 | `invalid-var-run-request` | Malformed run body, unknown `mode`, start after end, or `limit` outside 1-100 |
| 409 | `var-run-in-progress` | The account already has a queued or running VaR run (`_links.active_run` names it) |
| 404 | `var-run-not-found` | No VaR run with that id exists for this account |
| 502 | `market-data-service-unavailable` | market-data-web-service request failed (network error, non-2xx, timeout) |
| 422 | `invalid-var-query` | Unsupported `lookback`, `confidence`, `pnl_basis` or `min_quality` value on the series/backtest endpoints |

The four VaR-specific error types above also include a `correlation_id` field, matching the id logged against the triggering request and (for a run failure) the run's own `failure.correlation_id`.

---

## 6. Manual Testing

### Swagger UI

With the server running, open a browser and navigate to:

```
http://127.0.0.1:8000/docs
```

This renders the full interactive OpenAPI UI. You can:

- Expand any endpoint and click **Try it out**
- For `POST /v1/accounts/{account_name}/ladder`, click **Choose File** to upload a local XLSX
- Execute the request and inspect the response body, headers, and status code directly in the browser

The raw OpenAPI JSON schema is available at `http://127.0.0.1:8000/openapi.json`.

---

### curl (bash / Git Bash)

**Ingest a ledger (first time — expects 201):**
```bash
curl -s -w "\nHTTP %{http_code}\n" \
  -X POST http://127.0.0.1:8000/v1/accounts/my-portfolio/ladder \
  -F "file=@my_portfolio_ledger.xlsx;type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" \
  | python -m json.tool
```

**Ingest the same file again (idempotent — expects 200, status: unchanged):**
```bash
curl -s -w "\nHTTP %{http_code}\n" \
  -X POST http://127.0.0.1:8000/v1/accounts/my-portfolio/ladder \
  -F "file=@my_portfolio_ledger.xlsx;type=application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
```

**Retrieve the ladder summary:**
```bash
curl -s http://127.0.0.1:8000/v1/accounts/my-portfolio/ladder | python -m json.tool
```

**Download the full XLSX ladder:**
```bash
curl -s -o my-portfolio-ladder.xlsx \
  http://127.0.0.1:8000/v1/accounts/my-portfolio/ladder/download

echo "Downloaded: $(wc -c < my-portfolio-ladder.xlsx) bytes"
```

**Liveness and readiness checks:**
```bash
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/ready
```

---

### PowerShell

**Ingest a ledger:**
```powershell
$file = "my_portfolio_ledger.xlsx"
$account = "my-portfolio"

$form = [System.Net.Http.MultipartFormDataContent]::new()
$fileStream = [System.IO.File]::OpenRead($file)
$fileContent = [System.Net.Http.StreamContent]::new($fileStream)
$fileContent.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::new(
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
$form.Add($fileContent, "file", [System.IO.Path]::GetFileName($file))

$client = [System.Net.Http.HttpClient]::new()
$response = $client.PostAsync("http://127.0.0.1:8000/v1/accounts/$account/ladder", $form).Result
$body = $response.Content.ReadAsStringAsync().Result

Write-Host "Status: $($response.StatusCode)"
$body | ConvertFrom-Json | ConvertTo-Json -Depth 5
$client.Dispose()
```

**Retrieve the ladder summary:**
```powershell
$account = "my-portfolio"
$response = Invoke-RestMethod -Uri "http://127.0.0.1:8000/v1/accounts/$account/ladder" -Method Get
$response | ConvertTo-Json -Depth 5
```

**Download the full XLSX:**
```powershell
$account = "my-portfolio"
$outFile = "$account-ladder.xlsx"

Invoke-WebRequest `
    -Uri "http://127.0.0.1:8000/v1/accounts/$account/ladder/download" `
    -OutFile $outFile

Write-Host "Saved $outFile ($($(Get-Item $outFile).Length) bytes)"
```

**Liveness and readiness:**
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/health"
Invoke-RestMethod -Uri "http://127.0.0.1:8000/ready"
```

---

## File Structure

```
portfolio-analysis-service/
├── app/
│   ├── api/
│   │   ├── health.py          # GET /health, GET /ready
│   │   ├── ladder.py          # POST/GET /v1/accounts/{name}/ladder[/download]
│   │   └── risk_var.py        # POST/GET .../risk/var/runs[/{id}], .../status, .../var, .../var/backtest, .../var/methods
│   ├── models/
│   │   ├── ladder.py          # Pydantic response models (IngestionSummary, LadderSummary, ProblemDetail)
│   │   ├── var.py             # VarRun, VarRunRequest, VarStatus, RunWarning, RunFailure, ...
│   │   └── var_series.py      # VarSeriesResponse, VarBacktestResponse, VarMethodsResponse, ... (feature 013)
│   ├── repositories/
│   │   ├── ladder_repository.py  # Filesystem read/write (ladder.xlsx + meta.json)
│   │   └── var_repository.py     # Filesystem read/write (var/estimates.csv, outcomes.csv, ...)
│   ├── services/
│   │   ├── ingestion_service.py  # Orchestration: checksum → validate → expand → persist
│   │   ├── ladder_expander.py    # Business-day expansion and forward-fill logic
│   │   └── var/                  # Historical-simulation VaR calculation (feature 012) + read API (013)
│   │       ├── engine.py               # Pure: rank_k, var_es, scenario_pnl, estimate, hypothetical_pnl
│   │       ├── exposures.py            # Ladder rows → per-date Exposure + proxy configs
│   │       ├── return_panel.py         # Observed prices → business-day return grid; outliers/exclusions
│   │       ├── fingerprint.py          # Config/holdings fingerprinting for incremental runs
│   │       ├── run_scheduler.py        # Single-worker background execution of runs
│   │       ├── var_run_service.py      # Orchestrates one run end to end
│   │       ├── var_status_service.py   # Coverage/freshness status (never reads the ladder)
│   │       ├── var_window.py           # Ladder-free date-window resolution (013)
│   │       ├── backtest.py             # Pure: Kupiec/Christoffersen/CC/traffic-light/stability (013)
│   │       ├── var_series_service.py   # Orchestrates GET .../risk/var (013)
│   │       ├── var_backtest_service.py # Orchestrates GET .../risk/var/backtest (013)
│   │       └── var_methods_service.py  # Pure builder for GET /v1/risk/var/methods (013)
│   ├── validators/
│   │   └── ledger.py          # Schema validation for incoming XLSX files
│   ├── config.py              # Settings loaded from config.yaml
│   ├── exceptions.py          # Domain exception types
│   ├── logging_config.py      # structlog setup (JSON output, rotating file handler)
│   └── main.py                # FastAPI app, middleware, exception handlers
├── tests/
│   ├── features/              # Gherkin .feature files
│   ├── steps/                 # pytest-bdd step implementations
│   └── unit/                  # Pure unit tests (no HTTP)
├── specs/
│   └── 001-position-ladder-ingestion/  # Spec Kit design artefacts
├── config.yaml                # Runtime configuration
├── pyproject.toml             # Tool configuration (ruff, mypy, pytest)
├── requirements.txt           # Pinned runtime dependencies
└── requirements-dev.txt       # Pinned dev/test dependencies
```
