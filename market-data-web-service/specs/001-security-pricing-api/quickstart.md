# Quickstart: Security Pricing API

**Feature**: 001-security-pricing-api
**Date**: 2026-05-04

---

## Prerequisites

- Python 3.11+
- Internet access (required for Yahoo Finance data)
- Windows PowerShell or bash

---

## 1. Install Dependencies

```powershell
cd C:\GitHub\JHoxley\InvestmentPortfolio\market-data-web-service
python -m venv .venv
.venv\Scripts\Activate.ps1          # PowerShell
pip install -r requirements.txt
```

---

## 2. Run the API Server

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

The server starts at `http://localhost:8000`.

---

## 3. Explore the API

Open in a browser:
- **Swagger UI**: http://localhost:8000/docs
- **OpenAPI schema**: http://localhost:8000/openapi.json
- **ReDoc**: http://localhost:8000/redoc

---

## 4. Example Requests

**Current price:**
```powershell
Invoke-RestMethod "http://localhost:8000/securities/AAPL/price"
```

**Historical prices (last 30 days — default):**
```powershell
Invoke-RestMethod "http://localhost:8000/securities/MSFT/history"
```

**Historical prices (custom range):**
```powershell
Invoke-RestMethod "http://localhost:8000/securities/VOD.L/history?from=2024-01-01&to=2024-06-30"
```

---

## 5. Run the BDD Test Suite

All Gherkin scenarios from the spec are executable via pytest:

```powershell
pytest tests/ -v
```

To run a specific feature file:

```powershell
pytest tests/ -v -k "current_price"
```

---

## 6. Run Linting and Type Checking

```powershell
ruff check app/ tests/
mypy app/
```

---

## 7. Check Logs

Structured JSON logs are written to `logs/market-data-api.log`. To tail the log:

```powershell
Get-Content logs\market-data-api.log -Wait
```

---

## Project Layout

```text
market-data-web-service/
├── app/
│   ├── main.py                    # FastAPI app entry point
│   ├── api/
│   │   └── securities.py          # /securities router
│   ├── services/
│   │   └── pricing_service.py     # Business logic layer
│   ├── providers/
│   │   └── yfinance_provider.py   # yfinance data access layer
│   ├── models/
│   │   └── pricing.py             # Pydantic request/response models
│   └── logging_config.py          # structlog JSON logging setup
├── tests/
│   ├── features/
│   │   ├── current_price.feature  # BDD: US1 scenarios
│   │   ├── historical_price.feature # BDD: US2 scenarios
│   │   └── error_handling.feature # BDD: US3 scenarios
│   ├── steps/
│   │   ├── current_price_steps.py
│   │   ├── historical_price_steps.py
│   │   └── error_handling_steps.py
│   └── conftest.py
├── openapi.yaml                   # OpenAPI contract (committed)
├── pyproject.toml                 # Ruff + mypy config
├── requirements.txt               # Pinned dependencies
└── logs/                          # JSON log files (git-ignored)
```
