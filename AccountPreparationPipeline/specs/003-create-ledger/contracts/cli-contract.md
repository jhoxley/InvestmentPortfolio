# Contract: CLI — create_ledger Mode

**Feature**: 003-create-ledger
**Date**: 2026-06-03
**Type**: CLI argument contract

## Overview

The `create_ledger` mode is invoked as a subcommand of `pipeline.py`. It accepts two positional
arguments: the path to the input consolidated journal XLSX and the path for the output ledger XLSX.

## Invocation

```
python pipeline.py create_ledger <input_path> <output_path>
```

## Arguments

| Position | Name | Type | Required | Description |
|---|---|---|---|---|
| 1 | `input_path` | file path | Yes | Path to an existing consolidated journal XLSX produced by `consolidate_journals`. Must exist and be readable. |
| 2 | `output_path` | file path | Yes | Path for the ledger output XLSX. Created (or overwritten) by this mode. Parent directory must exist. |

## Exit Codes

| Code | Meaning |
|---|---|
| 0 | Success — ledger written |
| 1 | Unrecognised mode (handled by dispatcher) |
| 2 | Invalid arguments (missing argument, input file not found, missing required columns) |
| 3 | Unhandled execution failure |

## Examples

**Generate a ledger from a consolidated journal:**
```
python pipeline.py create_ledger \
    data/group_sipp_journal.xlsx \
    data/group_sipp_ledger.xlsx
```

**Overwrite an existing ledger:**
```
python pipeline.py create_ledger data/journal.xlsx data/ledger.xlsx
```

## Standard Output

On success, a one-line completion message is printed to stdout:

```
Ledger written: 492 rows processed → data/group_sipp_ledger.xlsx
```

## Structured Log Output

On completion the mode emits an INFO log record:

```json
{
  "level": "INFO",
  "logger": "pipeline.modes.create_ledger",
  "message": "Ledger written",
  "correlation_id": "<uuid>",
  "input_path": "data/group_sipp_journal.xlsx",
  "output_path": "data/group_sipp_ledger.xlsx",
  "rows_processed": 492,
  "rows_written": 492
}
```

On input validation failure, an ERROR log record is emitted and exit code 2 is returned:

```json
{
  "level": "ERROR",
  "message": "Invalid input journal",
  "detail": "Input file not found: data/missing.xlsx"
}
```
