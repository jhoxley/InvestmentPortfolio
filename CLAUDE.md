# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Python financial analysis tool that processes Hargreaves Lansdown portfolio data (transactions + income from Excel) and generates reports and visualisations. Data is enriched with market prices via yfinance, with local parquet caching.

## Commands

**Run the application:**
```bash
.venv/Scripts/python PortfolioAnalysis.py <ReportType> data_file="..." static_file="..." transactions_sheet="Transactions" income_sheet="Income" output_file="..."
```

Report types: `DailyDetails`, `DailySummary`, `MonthlySummary`, `QuarterlySummary`, `AnnualSummary`, `Projected`, `Current`, `Performance`, `All`

Optional params: `fwd_periods=1095`, `periodicity="QE"` (for projection/periodic reports)

**Run tests:**
```bash
python -m unittest discover -s test -p "test*.py"
```

**Run a single test:**
```bash
python -m unittest test.test_AnalysisFuncs.TestCreateDailySummary.test_create_daily_summary_single_position
```

No build step or linter configured. Dependencies: `pip install -r requirements.txt`

## Architecture

### Data flow

```
Excel (Transactions + Income)  +  JSON (static metadata)
        ↓
PortfolioAnalysis.py  — loops over each position
        ↓
MarketData.py         — fetches prices from yfinance (cached as .parquet)
        ↓
DataFormatting.py     — merges transactions + income + dates + prices into per-position DataFrame
        ↓
AnalysisFuncs.py      — calculates metrics (returns, PnL, weights) only as needed by the report
        ↓
Reports/              — each report class writes Excel + PNG output
```

### Key design decisions

**Report strategy pattern:** `BaseReport` is an abstract base; each report type is a concrete subclass. `MultiReport` is a composite that runs multiple reports against the same data. `PeriodicSummaryBase` is a template-method base for time-aggregated reports (Monthly/Quarterly/Annual share aggregation logic; subclasses override `get_periodicity()`).

**Lazy measure calculation:** `BaseReport.required_measures()` declares what columns a report needs. The orchestrator calculates only those columns (e.g. `calculate_daily_returns()`, `calculate_position_weights()`) before invoking the report. Don't add metric calculations upfront.

**Market data caching:** `Data/MarketData.py` caches each ticker as `cache_<ticker>.parquet` in the repo root. Cache is checked for date coverage before fetching; missing ranges are prepended/appended. The `.gitignore` excludes these files.

**Per-position processing:** Each position is processed independently in a loop, then all DataFrames are concatenated via `DataFormatting.create_portfolio()`. Positions are identified by `Position Name` string matching between the transactions sheet and the static JSON config.

### Input data contracts

**Static JSON** (one object per position):
```json
{ "name": "...", "isin": "GB...", "ticker": "AAPL.L", "ignore": false, "theme": "Tech Stocks", "multiplier": 1.0, "price_file": null }
```

**Transactions sheet columns:** `Position Name`, `Settle date`, `Reference`, `Adj Qty`, `Value (£)`

**Income sheet columns:** `Position Name`, `Settle date`, `Quantity`, `Value (£)`

### Constants worth knowing

- 260 trading days/year for annualisation
- Business-day frequency (`freq='B'`) for date series
- 2 business-day lag assumed for yfinance data freshness
- Zero close prices are filtered out (treated as bad data)
- Cash positions are given a synthetic `Close = 1.0`

### Test structure

Tests live in `test/`, test data (CSVs) in `test_data/` organised by function name. Tests compare computed output against expected CSV files loaded at test time. `test_yfinance.py` makes live network calls and is not a unit test.

### Known issues (from README)

- Sales/divestments don't correctly factor into PnL and Capital calculations
- Parquet cache may not correctly handle partial date coverage in all edge cases
- `FutureWarning` in `DataFormatting.py:26` regarding `.fillna()` downcasting behaviour
