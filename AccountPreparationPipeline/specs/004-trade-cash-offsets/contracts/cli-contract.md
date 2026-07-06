# Contract: CLI — consolidate_journals Mode (offset extension)

**Feature**: 004-trade-cash-offsets
**Date**: 2026-06-05
**Type**: CLI behaviour contract (delta from existing contract)

## Overview

This feature extends the existing `consolidate_journals` mode. No new mode, subcommand, or
argument is added. The CLI invocation signature is unchanged.

## Invocation (unchanged)

```
python pipeline.py consolidate_journals JOURNAL_PATH FRAGMENTS_DIR METHOD ACCOUNT
```

## Behaviour Change

After this feature is implemented, running `consolidate_journals` against input files that
contain `buy` or `sell` events produces additional rows in the output journal. These rows are
not visible in the argument contract but are observable in the output XLSX.

### Output XLSX change

For each `buy` or `sell` event inserted in the current run, the output journal gains one
additional row with:

| Column | Value |
|--------|-------|
| `date` | Same as the originating trade |
| `account` | Same as the originating trade |
| `sub_account` | `"Cash"` |
| `action` | `"trading"` |
| `reference` | Trade reference + `"-offset"` (e.g. `"B12345-offset"`) |
| `value` | Negated trade value |
| `quantity` | Negated trade value |

### Console output change

The `Events inserted` count in the success summary includes offset rows. A run that inserts
3 trade events and generates 2 offsets (e.g. 2 buys and 1 non-trade deposit) reports
`Events inserted: 5`.

## Exit Codes (unchanged)

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Unrecognised mode (handled by dispatcher) |
| 2 | Invalid arguments |
| 3 | Unhandled execution failure |

## Idempotency (unchanged)

Running `consolidate_journals` twice with the same inputs still produces an identical
output journal. Offset rows from the first run are deduplicated on the second run
using the `date + reference` dedup key (e.g. `"B12345-offset"` uniquely identifies the
offset for trade `"B12345"` on a given date).
