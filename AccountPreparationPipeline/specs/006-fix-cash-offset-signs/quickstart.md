# Quickstart: Fix Cash Offset Signs

**Feature**: 006-fix-cash-offset-signs
**Date**: 2026-06-10

## Prerequisites

- Python 3.11+, virtual environment activated
- A real journal already produced by `consolidate_journals` (e.g. `HL_SIPP_Journal.xlsx`)

## Verifying the Fix

After deploying the fix, re-run `consolidate_journals` to self-heal any existing wrong-sign
offsets:

```powershell
.venv\Scripts\python.exe pipeline.py consolidate_journals `
    C:\Users\jhoxl\OneDrive\Investments\Journals\HL_SIPP_Journal.xlsx `
    "C:\Users\jhoxl\OneDrive\Investments\Journals\HL Group Sipp - Capital Account" `
    HL `
    "HL Group SIPP"
```

Then inspect the journal. For any buy trade (e.g. `B915160961`, `value = −1 031.25`):

```python
import pandas as pd
df = pd.read_excel("C:/Users/jhoxl/OneDrive/Investments/Journals/HL_SIPP_Journal.xlsx")
buy = df[df['reference'] == 'B915160961'].iloc[0]
offset = df[df['reference'] == 'B915160961-offset'].iloc[0]
assert buy['value'] < 0            # buy has negative value (HL convention)
assert offset['value'] == buy['value']  # offset mirrors buy — also negative
assert offset['value'] < 0         # cash decreases on buy
```

For any sell trade (e.g. `S872695061`, `value = 81.87`):

```python
sell = df[df['reference'] == 'S872695061'].iloc[0]
offset = df[df['reference'] == 'S872695061-offset'].iloc[0]
assert sell['value'] > 0           # sell has positive value (HL convention)
assert offset['value'] == sell['value']  # offset mirrors sell — also positive
assert offset['value'] > 0         # cash increases on sell
```

## Running Tests

```powershell
# Unit tests for the offset generator
python -m pytest tests/unit/consolidate_journals/test_offset_generator.py -v

# Full suite
python -m pytest tests/ -v
```

## Quality Gates

```powershell
mypy --strict src/ pipeline.py
ruff check .
ruff format --check .
```
