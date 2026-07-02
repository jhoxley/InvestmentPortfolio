# Data Model: HL Lodgement Action Mapping

**Feature**: 012-hl-lodgement-action
**Date**: 2026-07-02

## Modified Entities

### `ActionType` (StrEnum) — `src/modes/consolidate_journals/schema.py`

One new value added to the existing enumeration:

| Value | String | Description |
|-------|--------|-------------|
| `ActionType.LODGEMENT` | `"lodgement"` | In-specie transfer of a named security into the account |

Existing values (`buy`, `sell`, `deposit`, `income`, `fee`, `trading`, `dividend`) are unchanged.

### New Constants — `src/modes/consolidate_journals/constants.py`

Two new named constants, added alongside the existing `RE_BUY` and `RE_SELL`:

| Constant | Type | Value | Purpose |
|----------|------|-------|---------|
| `RE_LODGEMENT` | `re.Pattern[str]` | `re.compile(r"^L\d+$")` | Matches L+digits references (e.g. `L003538235`) |
| `LODGEMENT_DESCRIPTION_PREFIX` | `str` | `"Lodgement "` | Prefix stripped from description to derive sub-account |

## Modified Behaviour

### `_map_action()` — `src/modes/consolidate_journals/parsers/hl.py`

New branch inserted after the `RE_SELL` check:

```
if RE_LODGEMENT.match(ref):
    return ActionType.LODGEMENT
```

No other changes to `_map_action`.

### `_parse_row()` — `src/modes/consolidate_journals/parsers/hl.py`

New branch added to the sub-account derivation block. Lodgement sub-account logic:

```
elif action is ActionType.LODGEMENT:
    stripped = description.removeprefix(LODGEMENT_DESCRIPTION_PREFIX).strip()
    sub_account = stripped if stripped else (description or reference)
```

The branch is inserted between the DIVIDEND branch and the existing BUY/SELL/other branch.

## Unchanged

- `CASH_ACTION_TYPES` — lodgement is intentionally excluded (not a cash transaction)
- `journal_store.py` — no changes (no cash offset generation for lodgements)
- `create_ledger` — no changes (reads existing `action` column; lodgement is a new passthrough value)
- `run_pipeline.ps1` — no changes

## Test Fixtures

New CSV fixture required:

**`tests/data/consolidate_journals/valid_hl_lodgement.csv`**

Columns: `Trade date, Settle date, Reference, Description, Unit cost (p), Quantity, Value (£)`

Content (matching real-world format from the sample file):

| Trade date | Settle date | Reference | Description | Unit cost (p) | Quantity | Value (£) |
|------------|-------------|-----------|-------------|---------------|----------|-----------|
| 12/07/2018 | 12/07/2018 | L003538235 | Lodgement Barclays plc Ordinary 25p | 188.38 | 1221 | -2288.89 |
| 12/07/2018 | 12/07/2018 | L003538236 | Lodgement iShares II plc USD TIPS UCITS ETF USD (Acc) | 15552 | 1 | -155.48 |

This fixture must include the standard HL preamble header (Portfolio Summary rows) and the
`Trade date / Settle date / Reference / Description / ...` header row to match the real file
format.
