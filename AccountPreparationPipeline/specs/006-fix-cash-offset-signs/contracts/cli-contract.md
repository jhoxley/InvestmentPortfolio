# Contract: CLI — consolidate_journals Mode (offset sign correction)

**Feature**: 006-fix-cash-offset-signs
**Date**: 2026-06-10
**Type**: CLI behaviour contract (delta from feature 004 contract)

## Overview

No changes to the CLI invocation signature, arguments, exit codes, or console output format.
The change is entirely in the **value and quantity** of the synthetic Cash offset rows written
to the output journal XLSX.

## Invocation (unchanged)

```
python pipeline.py consolidate_journals <journal_path> <fragments_dir> <method> <account>
```

## Output Journal Schema Change

The `value` and `quantity` columns of `trading` action rows (Cash offsets) change sign:

| Scenario | Feature 004 (buggy) | Feature 006 (corrected) |
|----------|---------------------|-------------------------|
| Buy trade (e.g. value = −£1 000) | offset `value` = `+1 000` | offset `value` = `−1 000` |
| Sell trade (e.g. value = +£500) | offset `value` = `−500` | offset `value` = `+500` |

The `quantity` column always equals the `value` column for Cash offset rows (unchanged rule).

## Self-Healing Re-Run

Journals produced by the buggy feature 004 implementation contain wrong-sign offsets. Re-running
`consolidate_journals` after this fix is deployed will automatically replace those rows with
correct-sign offsets via the existing merge/deduplication mechanism. No manual intervention
is required.

## Exit Codes (unchanged)

| Code | Meaning |
|------|---------|
| 0 | Success |
| 2 | Invalid input |
| 3 | Unhandled failure |

## Breaking Change Notice

Consumers that read the consolidated journal XLSX and use the `value` or `quantity` columns of
`trading` action rows will observe sign-reversed values after this fix. This is a correction of
incorrect data — consumers should update any downstream logic that depended on the wrong signs.
