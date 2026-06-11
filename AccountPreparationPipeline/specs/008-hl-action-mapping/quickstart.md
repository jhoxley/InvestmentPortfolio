# Quickstart: HL Action Mapping

## Overview

This feature adds three new reference→action mappings to the HL fragment parser:

| Reference (any case) | Action |
|---|---|
| `Card Web` | `deposit` |
| `FPC` | `deposit` |
| `Commission` | `income` |

All three produce sub-account = `"Cash"` and zero parse errors.

---

## Test Scenarios

### Scenario 1: Card Web → deposit

**Input CSV** (`valid_hl_card_web.csv`):
```csv
Trade date,Settle date,Reference,Description,Unit cost (£),Qty,Value (£)
15/03/2024,15/03/2024,Card Web,Card payment deposit,,,500.00
16/03/2024,16/03/2024,card web,card payment deposit,,,250.00
```

**Expected output** (consolidated journal):
- 2 events, both with `action = deposit`, `sub_account = Cash`
- 0 parse errors
- References preserved verbatim: `"Card Web"` and `"card web"`

---

### Scenario 2: FPC → deposit

**Input CSV** (`valid_hl_fpc.csv`):
```csv
Trade date,Settle date,Reference,Description,Unit cost (£),Qty,Value (£)
20/03/2024,20/03/2024,FPC,FPC transfer,,,1000.00
21/03/2024,21/03/2024,fpc,fpc transfer,,,750.00
```

**Expected output**:
- 2 events, both with `action = deposit`, `sub_account = Cash`
- 0 parse errors

---

### Scenario 3: Commission → income

**Input CSV** (`valid_hl_commission.csv`):
```csv
Trade date,Settle date,Reference,Description,Unit cost (£),Qty,Value (£)
10/04/2024,10/04/2024,Commission,Commission rebate,,,12.50
11/04/2024,11/04/2024,COMMISSION,Commission rebate annual,,,8.75
```

**Expected output**:
- 2 events, both with `action = income`, `sub_account = Cash`
- 0 parse errors

---

### Scenario 4: Canonical sort key

These new mappings produce `deposit` and `income` events which feed the standard `TRANSACTION_ID_SORT_COLS = ["date", "account", "sub_account", "reference"]` sort in the ledger engine. A `Card Web` deposit event on 2024-03-15 with sub_account `Cash` will sort before a `Vanguard Fund` buy on the same date.

---

## Regression check

After implementing, run:

```powershell
python -m pytest tests/unit/consolidate_journals/parsers/test_hl_parser.py -v
python -m pytest tests/features/ -k "consolidate" -v
```

All existing `TestActionMapping` tests and BDD scenarios must still pass. Zero regressions.

---

## Edge-case verification

| Input reference | Expected action | Notes |
|---|---|---|
| `"Card Web"` | `deposit` | Canonical casing |
| `"CARD WEB"` | `deposit` | All-caps |
| `"card web"` | `deposit` | All-lowercase |
| `"Card Web2"` | **ParseError** | Only exact match; no prefix/substring |
| `"FPC"` | `deposit` | Canonical |
| `"fpc"` | `deposit` | Lowercase |
| `"Commission"` | `income` | Canonical |
| `"commission"` | `income` | Lowercase |
| `"COMMISSION"` | `income` | All-caps |
| `"Deposit"` | `deposit` | Existing — must be unaffected |
| `"INTEREST"` | `income` | Existing — must be unaffected |
| `"MANAGE FEE"` | `fee` | Existing — must be unaffected |
