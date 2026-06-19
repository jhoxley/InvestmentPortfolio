# Data Model: Income Dividend Action Mappings

**Branch**: `009-income-dividend-mappings` | **Date**: 2026-06-18

## ActionType enum change (`src/modes/consolidate_journals/schema.py`)

| Value       | String repr  | Status     | Sub-account rule          |
|-------------|--------------|------------|---------------------------|
| `BUY`       | `"buy"`      | existing   | holding name from description |
| `SELL`      | `"sell"`     | existing   | holding name from description |
| `DEPOSIT`   | `"deposit"`  | existing   | `"Cash"` (CASH_ACTION_TYPES) |
| `INCOME`    | `"income"`   | existing   | `"Cash"` (CASH_ACTION_TYPES) |
| `FEE`       | `"fee"`      | existing   | `"Cash"` (CASH_ACTION_TYPES) |
| `WITHDRAWAL`| `"withdrawal"`| existing  | `"Cash"` (CASH_ACTION_TYPES) |
| `TRADING`   | `"trading"`  | existing   | synthetic cash offset      |
| **`DIVIDEND`** | **`"dividend"`** | **new** | **holding name from description (NOT in CASH_ACTION_TYPES)** |

`DIVIDEND` must NOT be added to `CASH_ACTION_TYPES`. Its sub-account is populated by `_strip_dividend_suffix()`, not set to `"Cash"`.

## New constants (`src/modes/consolidate_journals/constants.py`)

### HL_DIVIDEND_REFERENCES

```python
HL_DIVIDEND_REFERENCES: frozenset[str] = frozenset({"ST DIV", "OVR CR", "UTC CR", "LOYALTYU"})
```

- Stored uppercase; matched via `ref.upper() in HL_DIVIDEND_REFERENCES` in `_map_action()`
- All four values confirmed present in real HL ISA Income Account fragment files

### HL_DIVIDEND_SUFFIX_MAP

```python
HL_DIVIDEND_SUFFIX_MAP: dict[str, tuple[str, ...]] = {
    "ST DIV": (" Dividend Payment",),
    "OVR CR": (" Overseas Dividend Payment",),
    "UTC CR": (" Eql - UT Cash Payment", " UT Cash Payment"),
}
```

- Keys are uppercase reference strings, consistent with `HL_DIVIDEND_REFERENCES`
- `UTC CR` has two suffix variants; they are tried in order — longer first so the `" Eql -"` prefix is not left behind
- `LOYALTYU` is absent from this map because its suffix is dynamic (handled by `RE_LOYALTYU_SUFFIX`)

### RE_LOYALTYU_SUFFIX

```python
RE_LOYALTYU_SUFFIX: re.Pattern[str] = re.compile(r" \d{2} \d{2} Gross Loyalty$")
```

- Matches ` MM YY Gross Loyalty` at end of string where `MM` and `YY` are exactly two decimal digits each (zero-padded)
- `$` anchors to end of string; does not use `re.MULTILINE` (single description value, no newlines)
- Real examples confirmed: `" 04 26 Gross Loyalty"` (April 2026)

## Mapping table: reference → action → sub-account derivation

| Reference | Action   | Sub-account derivation                                        | Real example description |
|-----------|----------|---------------------------------------------------------------|--------------------------|
| `ST DIV`  | dividend | Strip `" Dividend Payment"` suffix                           | `"Barclays plc Ordinary 25p Dividend Payment"` → `"Barclays plc Ordinary 25p"` |
| `OVR CR`  | dividend | Strip `" Overseas Dividend Payment"` suffix                  | `"Man Group plc ORD USD0.0342857142 Overseas Dividend Payment"` → `"Man Group plc ORD USD0.0342857142"` |
| `UTC CR`  | dividend | Strip `" Eql - UT Cash Payment"` or `" UT Cash Payment"`    | `"HSBC FTSE 250 Index Class S - Income (GBP) Eql - UT Cash Payment"` → `"HSBC FTSE 250 Index Class S - Income (GBP)"` |
| `LOYALTYU`| dividend | Strip `RE_LOYALTYU_SUFFIX` (` \d{2} \d{2} Gross Loyalty$`)  | `"JPMorgan Emerging Markets Class C - Accumulation (GBP) 04 26 Gross Loyalty"` → `"JPMorgan Emerging Markets Class C - Accumulation (GBP)"` |

## New helper function (`src/modes/consolidate_journals/parsers/hl.py`)

### `_strip_dividend_suffix(reference: str, description: str) -> str`

**Responsibility**: Pure function — derives the sub-account string for a dividend event by stripping the reference-specific suffix from the description field.

**Inputs**:
- `reference`: raw reference string from CSV (may have leading/trailing whitespace)
- `description`: raw description string from CSV

**Output**: cleaned sub-account string; never empty (falls back to `description` then `reference`)

**Behaviour**:
1. Normalise `reference` via `.strip().upper()`
2. If `LOYALTYU`: apply `RE_LOYALTYU_SUFFIX.sub("", description).strip()`
3. Otherwise: look up `HL_DIVIDEND_SUFFIX_MAP`; try each suffix via `str.endswith()` + slice; break on first match
4. Return `result or description or reference`

## JournalEvent schema — no structural change

The `JournalEvent` dataclass is unchanged. The `action` field accepts any `ActionType` value; `dividend` slots in naturally. The `sub_account` field already accepts arbitrary strings.

## No migration required

This feature adds new constants and a new enum member. No existing data is modified. No parquet or file-based state is affected. No schema migration is needed.
