# Implementation Plan: Ledger Transaction Columns

**Branch**: `005-ledger-transaction-columns` | **Date**: 2026-06-08 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/005-ledger-transaction-columns/spec.md`

## Summary

Extend `create_ledger` to output a nine-column ledger XLSX. Two existing columns are renamed
(`value` → `Account Value`, `quantity` → `Account Quantity`) and two new columns are added
(`Transaction Value`, `Transaction Quantity`). The new columns represent the per-row
sign-adjusted contribution of each event — the delta between consecutive running balances.
The invariant `Account Value[i] = Account Value[i−1] + Transaction Value[i]` holds exactly
for every output row. The engine change is minimal: retain `adj_value` and `adj_quantity` as
the transaction columns instead of dropping them, and rename the cumsum output columns.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: `pandas>=2.0,<3.0`, `openpyxl>=3.1,<4.0` (all existing)
**Storage**: XLSX on local filesystem
**Testing**: `pytest` (unit), `pytest-bdd` (Gherkin BDD), `pytest` integration (subprocess)
**Target Platform**: Command-line; Windows / macOS / Linux
**Project Type**: Enhancement to existing CLI mode
**Performance Goals**: No change to O(N) complexity; SC-005 (500 rows, 10 s) still applies
**Constraints**: Breaking output schema change — documented; no new runtime dependencies;
  JOURNAL_COLUMNS (input) unchanged; LEDGER_COLUMNS (output) is new 9-column constant
**Scale/Scope**: Single-developer tool; matches existing scope of `create_ledger`

## Constitution Check

- [x] Virtual environment initialised; no new runtime dependencies
- [x] No magic strings — all new column names in `LEDGER_COL_*` constants and `LEDGER_COLUMNS`
  list in `create_ledger/constants.py`
- [x] SOLID — `LedgerEngine` continues SRP (computation only); `CreateLedgerMode` continues
  SRP (CLI only); no new shared state
- [x] All code fully type-annotated; `mypy --strict` planned as quality gate
- [x] `ruff check` + `ruff format --check` planned as quality gates
- [x] BDD scenarios updated in `tests/features/create_ledger.feature`; unit tests updated in
  `tests/unit/create_ledger/test_engine.py`; integration tests in
  `tests/integration/test_create_ledger_e2e.py`
- [x] Structured logging: no new log statements needed; existing completion log in mode.py
  continues to report rows processed

**Post-design re-check**: All gates confirmed. No violations.

## Project Structure

### Documentation (this feature)

```text
specs/005-ledger-transaction-columns/
├── plan.md              # This file
├── research.md          # Phase 0 decisions
├── data-model.md        # Schema change, new constants
├── quickstart.md        # Setup + run + verify
├── contracts/
│   └── cli-contract.md  # CLI delta + breaking change notice
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code Changes

```text
src/modes/create_ledger/
├── constants.py    # ADD LEDGER_COL_*, LEDGER_COLUMNS
├── engine.py       # EXTEND: retain adj_value/adj_quantity as Transaction cols;
│                   #         rename cumsum output to Account Value/Quantity;
│                   #         drop input value/quantity; return LEDGER_COLUMNS
└── mode.py         # UPDATE: use LEDGER_COLUMNS for column indices;
                    #         apply number format to all 4 numeric columns

tests/
├── features/
│   ├── create_ledger.feature               # UPDATE: column name refs;
│   │                                       # ADD Transaction Value scenarios
│   └── steps/
│       └── create_ledger_steps.py          # UPDATE: column refs in @then steps;
│                                           # ADD invariant + transaction col steps
├── unit/
│   └── create_ledger/
│       └── test_engine.py                  # UPDATE: column name refs throughout;
│                                           # ADD: Transaction cols assertions;
│                                           # UPDATE: LEDGER_COLUMNS schema check
└── integration/
    └── test_create_ledger_e2e.py           # UPDATE: column refs;
                                            # ADD: invariant verification test
```

**Structure Decision**: All changes within existing files. No new files or packages.

## Complexity Tracking

> No constitution violations. Table omitted.

---

## Implementation Notes

### `constants.py` — additions

```python
LEDGER_COL_ACCOUNT_VALUE: str = "Account Value"
LEDGER_COL_ACCOUNT_QUANTITY: str = "Account Quantity"
LEDGER_COL_TRANSACTION_VALUE: str = "Transaction Value"
LEDGER_COL_TRANSACTION_QUANTITY: str = "Transaction Quantity"

LEDGER_COLUMNS: list[str] = [
    "date",
    "account",
    "sub_account",
    "action",
    "reference",
    LEDGER_COL_ACCOUNT_VALUE,
    LEDGER_COL_ACCOUNT_QUANTITY,
    LEDGER_COL_TRANSACTION_VALUE,
    LEDGER_COL_TRANSACTION_QUANTITY,
]
```

### `engine.py` — key diff

Replace the cumsum/drop/return section:

```python
# BEFORE
df["value"] = df.groupby(["account", "sub_account"], sort=False)["adj_value"].cumsum()
df["quantity"] = df.groupby(["account", "sub_account"], sort=False)["adj_quantity"].cumsum()
df = df.drop(columns=["adj_value", "adj_quantity"])
return df[JOURNAL_COLUMNS]

# AFTER
df[LEDGER_COL_ACCOUNT_VALUE] = df.groupby(
    ["account", "sub_account"], sort=False
)["adj_value"].cumsum()
df[LEDGER_COL_ACCOUNT_QUANTITY] = df.groupby(
    ["account", "sub_account"], sort=False
)["adj_quantity"].cumsum()
df[LEDGER_COL_TRANSACTION_VALUE] = df["adj_value"]
df[LEDGER_COL_TRANSACTION_QUANTITY] = df["adj_quantity"]
df = df.drop(columns=["value", "quantity", "adj_value", "adj_quantity"])
return df[LEDGER_COLUMNS]
```

Empty-input early return changes to:

```python
if df.empty:
    return pd.DataFrame(columns=LEDGER_COLUMNS)
```

### `mode.py` — column index update

Replace the JOURNAL_COLUMNS-based column lookups with a loop over the four numeric columns:

```python
for col_name, fmt in [
    (LEDGER_COL_ACCOUNT_VALUE, NUMBER_FORMAT_VALUE),
    (LEDGER_COL_TRANSACTION_VALUE, NUMBER_FORMAT_VALUE),
    (LEDGER_COL_ACCOUNT_QUANTITY, NUMBER_FORMAT_QUANTITY),
    (LEDGER_COL_TRANSACTION_QUANTITY, NUMBER_FORMAT_QUANTITY),
]:
    col_idx = LEDGER_COLUMNS.index(col_name) + 1
    for row in ws.iter_rows(min_row=2, min_col=col_idx, max_col=col_idx):
        for cell in row:
            cell.number_format = fmt
```

Remove the `JOURNAL_COLUMNS` import from `consolidate_journals.constants` (no longer used in
`mode.py`). Add imports of `LEDGER_COLUMNS` and `LEDGER_COL_*` from `create_ledger.constants`.

### Existing test updates (breaking)

**`test_engine.py`** — all `["value"]` → `["Account Value"]`, `["quantity"]` → `["Account Quantity"]`.
Line 164 `list(result.columns) == JOURNAL_COLUMNS` → `list(result.columns) == LEDGER_COLUMNS`.
Add a new `TestTransactionColumns` class with assertions for Transaction Value/Quantity values.
Add a `TestInvariant` class that loops all rows per group and asserts the invariant.

**`create_ledger_steps.py`** — all `df.iloc[x]["value"]` → `df.iloc[x]["Account Value"]` etc.
in the 8+ `@then` step functions. Update step descriptions in the BDD feature file to match.

**`test_create_ledger_e2e.py`** — update column references; add `test_invariant_holds_for_all_rows`.

**`create_ledger.feature`** — update scenario step text wherever "value" / "quantity" columns are
referenced in `Then` assertions.
