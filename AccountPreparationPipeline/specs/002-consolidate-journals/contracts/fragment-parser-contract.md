# Contract: FragmentParser Protocol

**Feature**: 002-consolidate-journals
**Date**: 2026-05-31
**Type**: Python structural interface contract

## Overview

Every consolidation method is implemented as a `FragmentParser`. The parser is responsible for
reading a single fragment file, mapping its rows to `JournalEvent` instances, and collecting any
per-row or file-level errors into `ParseError` instances. The design mirrors the `ModeInterface`
pattern already established in this project.

## Protocol Definition

```python
from pathlib import Path
from typing import Protocol

class FragmentParser(Protocol):
    """Contract every fragment parser implementation must satisfy."""

    def parse(self, file_path: Path, account: str) -> ParseResult:
        """Parse a single fragment file and return events + errors.

        Args:
            file_path: Absolute path to the fragment file to parse.
            account:   The account label to assign to every JournalEvent.

        Returns:
            ParseResult containing:
                - events: successfully parsed JournalEvent instances (may be empty)
                - errors: ParseError instances for any row or file-level failures

        Must NOT raise exceptions — all failure conditions are encoded as ParseError.
        """
        ...
```

## Rules for Parser Implementors

1. **Never raise**: All failure conditions (header not found, invalid value, unknown action)
   MUST be encoded as `ParseError` instances in the returned `ParseResult`. The parser must
   not let exceptions propagate to the `ConsolidationEngine`.

2. **Partial results**: If a file has some valid rows and some invalid rows, both the valid
   `JournalEvent` instances AND the `ParseError` instances MUST be returned in the same
   `ParseResult`. Do not discard valid rows because later rows are invalid.

3. **Line numbers**: Use the CSV reader's `line_num` attribute for row-level errors.
   File-level errors (e.g., header not found) MUST set `line_number = None`.

4. **Account passthrough**: The `account` argument MUST be written unchanged into
   `JournalEvent.account` for every event produced by this parser.

5. **Reference passthrough**: The raw reference string from the source file MUST be written
   unchanged into `JournalEvent.reference`.

## HL Parser Rules (HLFragmentParser)

The `HLFragmentParser` implements the following rules for Hargreaves Lansdown CSV exports:

### Header Discovery
- Scan rows sequentially until a row is found where:
  - `row[0].strip() == "Trade date"` AND `row[1].strip() == "Settle date"`
- All rows before this header are silently discarded.
- If no such header row exists in the file, produce a single `ParseError` (file-level,
  `line_number=None`) with message `"No header row found"` and return an empty events list.

### Column Mapping (after header discovery)

| Source column | Target field | Notes |
|---|---|---|
| `Settle date` | `JournalEvent.date` | Parse as date; produce `ParseError` if unparseable |
| `Reference` | `JournalEvent.reference` | Passed through unchanged |
| `Reference` | `JournalEvent.action` | Apply action mapping rules below |
| `Description` | `JournalEvent.sub_account` | Strip unit-cost/quantity suffix |
| `Value (£)` or `Value` | `JournalEvent.value` | Parse as `Decimal`; strip currency symbols |
| `Qty` or `Quantity` | `JournalEvent.quantity` | Parse as `Decimal`; `None` if column absent or cell empty |

### Action Mapping Rules (applied to `Reference` column)

| Condition | Mapped action |
|---|---|
| `Reference` matches regex `^B\d+$` | `ActionType.BUY` |
| `Reference` matches regex `^S\d+$` | `ActionType.SELL` |
| Action/type column equals `"Deposit"` or `"BACS"` | `ActionType.CONTRIB` |
| No condition matches | `ParseError` for that row |

### Description Stripping

Strip the trailing unit-cost/quantity suffix from the `Description` column. The suffix has the
form `<quantity> @ <unit_cost>` where `@` separates quantity from unit cost. Everything after
and including the `@` token and the preceding quantity token is removed; leading/trailing
whitespace is stripped from the result.

Examples:
- `"Vanguard US Equity Index Fund Acc 10.00 @ £200.00"` → `"Vanguard US Equity Index Fund Acc"`
- `"Barclays PLC"` (no suffix) → `"Barclays PLC"` (returned unchanged)

If the stripped result is empty, produce a `ParseError` for that row.

## Registration

Parsers are registered via a factory function in the `ConsolidationEngine`:

```python
def _get_parser(method: ConsolidationMethod) -> FragmentParser:
    if method is ConsolidationMethod.HL:
        return HLFragmentParser()
    raise ValueError(f"No parser registered for method {method!r}")
```

Adding a new method: (1) add enum value to `ConsolidationMethod`, (2) implement `FragmentParser`,
(3) add a branch to `_get_parser`. Zero other changes required.
