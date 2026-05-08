# Market Data Web Service

A locally hosted REST API for retrieving security pricing data, backed by [Yahoo Finance](https://finance.yahoo.com/) via the `yfinance` package. Built with FastAPI and designed for programmatic consumption by portfolio analysis tools.

---

## Overview

### Purpose

This service exposes a clean HTTP interface for fetching current and historical prices for individual securities identified by Yahoo Finance ticker symbols (e.g. `AAPL`, `MSFT`, `VOD.L`, `BARC.L`). It acts as a thin, standards-compliant wrapper around Yahoo Finance — normalising responses into structured JSON, enforcing data quality rules, and providing predictable error contracts.

It was built as a companion to the Investment Portfolio analysis tool in this repository, replacing direct `yfinance` calls in analysis scripts with a proper service boundary.

### Capabilities

| Capability | Detail |
|---|---|
| Current price | Returns the most recent available price for any valid ticker, with currency, timestamp, and market status |
| Historical prices | Returns a daily closing price series over a caller-specified date range (defaults to trailing 30 days) |
| Data quality | Zero and negative prices from Yahoo Finance are rejected — callers always receive positive prices or an error |
| Error contracts | Structured JSON error responses for all failure modes: 404 (unknown ticker), 422 (bad input), 503 (Yahoo Finance unreachable) |
| Interactive docs | Swagger UI at `/docs`, ReDoc at `/redoc`, raw OpenAPI schema at `/openapi.json` |
| Structured logging | Every request and response is logged as JSON to `logs/market-data-api.log` and stdout |

### Ticker Format

Tickers follow Yahoo Finance conventions:

| Market | Example tickers |
|---|---|
| US equities | `AAPL`, `MSFT`, `TSLA`, `SPY` |
| London Stock Exchange | `VOD.L`, `BARC.L`, `SHEL.L` |
| ETFs / indices | `^GSPC`, `^FTSE`, `GLD` |
| Other exchanges | `SAP.DE`, `7203.T` |

### Implemented Specification

The service implements all user stories from two feature specifications:

**Feature 001 — Security Pricing API** (`specs/001-security-pricing-api/spec.md`):
- **US1 — Current Price** (P1 MVP): `GET /securities/{ticker}/price`
- **US2 — Historical Price Series** (P2): `GET /securities/{ticker}/history`
- **US3 — Error Handling** (P3): Structured 404/422/503 responses for all failure cases

**Feature 002 — As-Of Date on Current Price** (`specs/002-price-as-of-date/spec.md`):
- **US1 — Know What Date a Price Is For** (P1): `as_of_date` field added to the current price response, reconciled with the most recent entry in the history endpoint

All 12 acceptance scenarios are implemented as executable BDD tests (`pytest tests/ -v`).

---

## Section 1 — Interactive Use

### Prerequisites

- Python 3.11 or later
- Internet access (required for Yahoo Finance data)

### Installation

```powershell
cd market-data-web-service
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Starting the Server

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

The server starts at `http://localhost:8000`. The `--reload` flag restarts automatically on code changes — omit it in production.

### Swagger UI

Open **http://localhost:8000/docs** in a browser to explore the full API interactively. Every endpoint is documented with request parameters, example responses, and a live "Try it out" button.

The raw OpenAPI schema is available at **http://localhost:8000/openapi.json**.

### Making Requests from the Terminal

**Current price (PowerShell):**
```powershell
Invoke-RestMethod "http://localhost:8000/securities/AAPL/price" | ConvertTo-Json
```

**Current price (curl):**
```bash
curl http://localhost:8000/securities/AAPL/price
```

Example response:
```json
{
  "ticker": "AAPL",
  "price": 189.30,
  "currency": "USD",
  "timestamp": "2026-05-06T09:15:00Z",
  "market_status": "closed",
  "as_of_date": "2026-05-06"
}
```

**Historical prices with a date range:**
```powershell
Invoke-RestMethod "http://localhost:8000/securities/VOD.L/history?from=2024-01-01&to=2024-06-30"
```

**Historical prices — default trailing 30 days:**
```powershell
Invoke-RestMethod "http://localhost:8000/securities/MSFT/history"
```

Example response:
```json
{
  "ticker": "MSFT",
  "currency": "USD",
  "prices": [
    { "date": "2024-01-02", "close": 374.02 },
    { "date": "2024-01-03", "close": 370.87 }
  ]
}
```

### Error Responses

All errors return a JSON body with a `detail` field:

| Scenario | HTTP Status | Example `detail` |
|---|---|---|
| Unknown or delisted ticker | 404 | `"No valid price data found for ticker 'INVALIDXYZ99'"` |
| Ticker with invalid characters | 422 | FastAPI validation message |
| `from` date after `to` date | 422 | `"'from' date (2024-06-01) must not be after 'to' date (2024-01-01)"` |
| Yahoo Finance unreachable | 503 | `"Upstream data provider is currently unavailable. Please try again later."` |

### Running the Tests

```powershell
pytest tests/ -v
```

All 12 BDD scenarios (3 per user story) should pass. Live network calls are made for US1 and US2 scenarios.

### Checking Logs

Structured JSON logs are written to `logs/market-data-api.log`:

```powershell
Get-Content logs\market-data-api.log -Wait
```

Each log entry includes `method`, `path`, `status`, `duration_ms`, and `timestamp`.

---

## Section 2 — Programmatic Use

### Python — Direct HTTP with `httpx`

```python
import httpx

BASE_URL = "http://localhost:8000"

# Current price
response = httpx.get(f"{BASE_URL}/securities/AAPL/price")
response.raise_for_status()
data = response.json()
print(data["price"], data["currency"], data["market_status"], data["as_of_date"])

# Historical prices
response = httpx.get(
    f"{BASE_URL}/securities/MSFT/history",
    params={"from": "2024-01-01", "to": "2024-06-30"},
)
response.raise_for_status()
history = response.json()
print(f"{len(history['prices'])} trading days returned")
```

### Python — Handling Errors

```python
import httpx

def get_price(ticker: str, base_url: str = "http://localhost:8000") -> dict:
    try:
        response = httpx.get(f"{base_url}/securities/{ticker}/price", timeout=10.0)
        if response.status_code == 404:
            raise ValueError(f"Ticker not found: {ticker}")
        if response.status_code == 503:
            raise RuntimeError("Market data service is currently unavailable")
        response.raise_for_status()
        return response.json()
    except httpx.TimeoutException:
        raise RuntimeError("Request timed out — is the service running?")
```

### Loading Historical Prices into a Pandas DataFrame

```python
import httpx
import pandas as pd

def get_price_history(
    ticker: str,
    from_date: str | None = None,
    to_date: str | None = None,
    base_url: str = "http://localhost:8000",
) -> pd.DataFrame:
    params = {}
    if from_date:
        params["from"] = from_date
    if to_date:
        params["to"] = to_date

    response = httpx.get(f"{base_url}/securities/{ticker}/history", params=params, timeout=15.0)
    response.raise_for_status()
    payload = response.json()

    df = pd.DataFrame(payload["prices"])
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    df.attrs["ticker"] = payload["ticker"]
    df.attrs["currency"] = payload["currency"]
    return df


# Usage
df = get_price_history("AAPL", from_date="2024-01-01", to_date="2024-12-31")
print(df.head())
#             close
# date
# 2024-01-02  185.20
# 2024-01-03  184.25
# ...

# Resample to monthly
monthly = df["close"].resample("ME").last()

# Calculate daily returns
df["return"] = df["close"].pct_change()
print(df["return"].describe())
```

### Loading Multiple Tickers into a Single DataFrame

```python
import httpx
import pandas as pd

def get_portfolio_prices(
    tickers: list[str],
    from_date: str,
    to_date: str,
    base_url: str = "http://localhost:8000",
) -> pd.DataFrame:
    frames = []
    with httpx.Client(base_url=base_url, timeout=15.0) as client:
        for ticker in tickers:
            response = client.get(
                f"/securities/{ticker}/history",
                params={"from": from_date, "to": to_date},
            )
            if response.status_code == 404:
                print(f"Warning: {ticker} not found, skipping")
                continue
            response.raise_for_status()
            payload = response.json()
            df = pd.DataFrame(payload["prices"])
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date").rename(columns={"close": ticker})
            frames.append(df)

    if not frames:
        return pd.DataFrame()

    return pd.concat(frames, axis=1).sort_index()


# Usage
prices = get_portfolio_prices(
    tickers=["AAPL", "MSFT", "VOD.L"],
    from_date="2024-01-01",
    to_date="2024-12-31",
)
print(prices.tail())
#              AAPL    MSFT   VOD.L
# date
# 2024-12-27  255.1   438.0   69.5
# ...

# Normalised performance (rebased to 100)
rebased = (prices / prices.iloc[0]) * 100
```

---

## Section 3 — Deployment as a Long-Running Service

The service is a standard ASGI application and can be deployed on any machine that has Python and internet access. The options below cover the most common local and server scenarios.

### Prerequisites on the Target Machine

- Python 3.11 or later
- Internet access (outbound HTTPS to `query1.finance.yahoo.com` and related Yahoo Finance endpoints)
- No database, message broker, or external storage is required

### Option A — Windows Service (NSSM)

[NSSM](https://nssm.cc/) wraps any executable as a native Windows service. This is the simplest option for a Windows host.

1. **Install NSSM** — download from https://nssm.cc/download and place `nssm.exe` on the PATH.

2. **Install the service:**
   ```powershell
   nssm install MarketDataAPI "C:\path\to\market-data-web-service\.venv\Scripts\uvicorn.exe"
   nssm set MarketDataAPI AppParameters "app.main:app --host 0.0.0.0 --port 8000"
   nssm set MarketDataAPI AppDirectory "C:\path\to\market-data-web-service"
   nssm set MarketDataAPI AppStdout "C:\path\to\market-data-web-service\logs\service.log"
   nssm set MarketDataAPI AppStderr "C:\path\to\market-data-web-service\logs\service-error.log"
   nssm set MarketDataAPI Start SERVICE_AUTO_START
   nssm start MarketDataAPI
   ```

3. **Manage the service:**
   ```powershell
   nssm status MarketDataAPI
   nssm restart MarketDataAPI
   nssm stop MarketDataAPI
   ```

### Option B — Linux systemd Service

On a Linux server (Ubuntu, Debian, RHEL, etc.):

1. **Deploy the application** to `/opt/market-data-api`:
   ```bash
   git clone <repo> /opt/market-data-api
   cd /opt/market-data-api/market-data-web-service
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```

2. **Create a systemd unit file** at `/etc/systemd/system/market-data-api.service`:
   ```ini
   [Unit]
   Description=Market Data Web Service
   After=network-online.target
   Wants=network-online.target

   [Service]
   Type=simple
   User=www-data
   WorkingDirectory=/opt/market-data-api/market-data-web-service
   ExecStart=/opt/market-data-api/market-data-web-service/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2
   Restart=on-failure
   RestartSec=5s
   StandardOutput=journal
   StandardError=journal

   [Install]
   WantedBy=multi-user.target
   ```

3. **Enable and start:**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable market-data-api
   sudo systemctl start market-data-api
   sudo systemctl status market-data-api
   ```

4. **View logs:**
   ```bash
   journalctl -u market-data-api -f
   ```

### Option C — Docker Container

A minimal `Dockerfile` for containerised deployment:

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

Build and run:
```bash
docker build -t market-data-api .
docker run -d --name market-data-api -p 8000:8000 --restart unless-stopped market-data-api
```

### Reverse Proxy (Optional)

If the service needs to be accessible over HTTPS or on a standard port, place it behind a reverse proxy. Example nginx config:

```nginx
server {
    listen 443 ssl;
    server_name market-data.internal;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 30s;
    }
}
```

### Infrastructure Dependencies Summary

| Dependency | Required | Notes |
|---|---|---|
| Python 3.11+ | Yes | Runs in a venv — no system-wide install needed beyond the interpreter |
| Outbound HTTPS | Yes | Yahoo Finance API endpoints (`query1.finance.yahoo.com`, `finance.yahoo.com`) |
| Disk (logs) | Yes | `logs/` directory; log rotation caps files at 10 MB × 3 backups |
| Database | No | All data fetched live from Yahoo Finance on each request; nothing persisted |
| Message broker | No | — |
| Authentication | No | No auth in v1; restrict access via firewall or reverse proxy if needed |
| Port 8000 | Default | Configurable via `--port` flag |

### Scaling Notes

This service is designed for single-user, local portfolio tooling. It makes live HTTP calls to Yahoo Finance on every request — there is no caching layer in v1. Under concurrent load the bottleneck is Yahoo Finance's response time (~1–3 seconds per request). If needed, a future version could add an in-memory TTL cache (e.g. with `cachetools`) between the service and yfinance.

For the intended use case, a single `uvicorn` worker is sufficient. Multiple workers (`--workers 4`) are safe to add as there is no shared in-process state.
