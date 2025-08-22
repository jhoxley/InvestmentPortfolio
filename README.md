# Investment Portfolio

This readme covers the overview of this repository. The **most important** part to appreciate is this is a personal, private play-project for learning technologies and comes with no guarantee of correctness or support!

## TODO

**Bugs**
- [ ] Return calculations look suspicious. Add unit tests to validate.
- [ ] C:\Users\jhoxl\Python\InvestmentPortfolio\DataFormatting.py:26: FutureWarning: Downcasting object dtype arrays on .fillna, .ffill, .bfill is deprecated and will change in a future version.
- [x] fix yfinance handling of ccy, i.e. cash lines need a close px of 1.0
- [x] PnL and handling of income incorrect; avoid double-count through cash line

**Improvements**
- Python code to extract position name from raw HL data
- Capture deposit/withdrawal separate from book cost
- Factor out position<>identifier map
- Factor out yfinance into own module
- Add caching layer to yfinance to retain historical data just in case of rate limiting or other issues

## Input data

This set of scripts is built around a simple extract of a Hargreaves Lansdown portoflio (www.hl.co.uk) as held by the author. This can be merged into a single XLSX input file with two tabs capturing the key events.

Two known issues with code at time of writing:
1. XLSX has an ugly built-in formula to extract a standardised position name from the raw data. This should be unified into the application code.
2. The position name in the XLSX has a hard-coded dictionary of identifiers in `PortfolioAnalysis.py` which is bad

### Transactions

Stuff here

### Income

More stuff here

## Execution

Following sections provide information on using and interpretting 

### Running tests

TBC

### Setup of environment

### Running application

- Create a Python env
- Activate
- Execute `./.venv/Scripts/python .\PortfolioAnalysis.py`

### Interpreting the results

Two output files
- `ProcessedDailySummary.xlsx`
- `ProcessedDailyInvestmentData`