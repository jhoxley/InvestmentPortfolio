# Data Model: Capital Ledger Mode

**Feature**: 011-capital-ledger-mode
**Date**: 2026-07-01

## Input Schema

The mode reads an XLSX file produced by `create_ledger`. The columns consumed are a subset of
`LEDGER_COLUMNS` from `src/modes/create_ledger/constants.py`:

| Column | Type | Description |
|--------|------|-------------|
| `Transaction ID` | str (`NNNNN-NNN`) | Canonical sort key; used to order rows before accumulation |
| `date` | str / date | Calendar date of the ledger row |
| `action` | str | One of: `deposit`, `income`, `buy`, `sell`, `trading`, `dividend`, etc. |
| `Transaction Value` | float | Sign-adjusted monetary value of each ledger row |

Only rows where `action` ∈ {`deposit`, `income`, `buy`, `sell`} are retained.

## Output Schema

One row per unique calendar date in the filtered input, chronological (date ascending) order.

| Column | Type | Description |
|--------|------|-------------|
| `date` | str | Calendar date (ISO 8601, matches input ledger date format) |
| `capital` | float | Cumulative sum of `Transaction Value` for all `deposit` rows ≤ this date |
| `income` | float | Cumulative sum of `Transaction Value` for all `income` rows ≤ this date |
| `book_value` | float | Cumulative net sum of `Transaction Value` for all `buy` + `sell` rows ≤ this date |

All numeric columns are `0.00` at the start (no negative carry from before first date).
Forward-fill means a date with no new `deposit` rows still shows the most recent `capital` total.

## Key Constants (to be declared in `constants.py`)

| Constant | Value | Purpose |
|----------|-------|---------|
| `CAPITAL_ACTION_DEPOSIT` | `"deposit"` | Action filter for capital column |
| `CAPITAL_ACTION_INCOME` | `"income"` | Action filter for income column |
| `CAPITAL_ACTION_BUY` | `"buy"` | Action filter for book_value column |
| `CAPITAL_ACTION_SELL` | `"sell"` | Action filter for book_value column |
| `CAPITAL_LEDGER_ACTIONS` | `frozenset({"deposit", "income", "buy", "sell"})` | Input row filter |
| `CAPITAL_COL_DATE` | `"date"` | Output date column name |
| `CAPITAL_COL_CAPITAL` | `"capital"` | Output capital column name |
| `CAPITAL_COL_INCOME` | `"income"` | Output income column name |
| `CAPITAL_COL_BOOK_VALUE` | `"book_value"` | Output book_value column name |
| `CAPITAL_LEDGER_OUTPUT_COLUMNS` | `["date", "capital", "income", "book_value"]` | Output column order |
| `LOG_CCL_CORRELATION_ID` | `"correlation_id"` | Structured log key |
| `COMPLETION_MSG` | `"Capital ledger written"` | Completion log message |

## Relationship to Existing Entities

- **Input**: `LEDGER_COLUMNS` (from `src/modes/create_ledger/constants.py`) — the mode reads
  `Transaction ID`, `date`, `action`, and `Transaction Value` from this schema.
- **Consumed constant**: `TRANSACTION_ID_SORT_COLS` (from `create_ledger/constants.py`) — the
  canonical sort order `[date, account, sub_account, reference]` is encoded in the existing
  Transaction IDs; sorting by `Transaction ID` ASC achieves the same ordering without re-deriving
  the key.
- **No new persistent entities**: The output XLSX is a flat report; there is no state carried
  between runs (unlike `create_ledger` which preserves Transaction IDs across re-runs).
