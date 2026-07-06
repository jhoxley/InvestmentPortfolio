# Contract: CLI — consolidate_journals Mode

**Feature**: 002-consolidate-journals
**Date**: 2026-05-31
**Type**: CLI argument contract

## Overview

The `consolidate_journals` mode is invoked as a subcommand of `pipeline.py`. It accepts four
positional arguments defining the output path, the input directory, the parsing strategy, and the
account label.

## Invocation

```
python pipeline.py consolidate_journals <journal_path> <fragments_dir> <method> <account>
```

## Arguments

| Position | Name | Type | Required | Description |
|---|---|---|---|---|
| 1 | `journal_path` | file path | Yes | Path to the consolidated journal XLSX. Created if absent; updated in place if present. |
| 2 | `fragments_dir` | directory path | Yes | Path to the directory containing fragment files to process. Must exist. |
| 3 | `method` | enum string | Yes | Consolidation method. Currently accepted values: `HL`. Case-sensitive. |
| 4 | `account` | free text | Yes | Account name label written into the `account` column of every row in the output journal. |

## Exit Codes

| Code | Meaning |
|---|---|
| 0 | All files processed; consolidated journal written (even if some rows had errors) |
| 1 | Unrecognised mode (handled by dispatcher, not this mode) |
| 2 | Invalid arguments (missing required argument, unrecognised method value, `fragments_dir` does not exist) |
| 3 | Fatal error (unable to write output file, unhandled exception) |

## Examples

**First-time consolidation** — creates a new XLSX from a directory of HL CSV exports:
```
python pipeline.py consolidate_journals \
    data/my_account_journal.xlsx \
    data/hl_exports/ \
    HL \
    "ISA 2024"
```

**Incremental update** — merges new CSVs into an existing journal:
```
python pipeline.py consolidate_journals \
    data/my_account_journal.xlsx \
    data/hl_exports/2025_q1/ \
    HL \
    "ISA 2024"
```

## Validation Rules

1. `journal_path` parent directory MUST exist; the pipeline does not create intermediate directories.
2. `fragments_dir` MUST be an existing directory; a non-existent path produces exit code 2.
3. `method` MUST be one of the registered `ConsolidationMethod` enum values (currently `HL`);
   unrecognised values produce exit code 2.
4. `account` MUST be non-empty; a blank string produces exit code 2.

## Standard Output

On success, the mode prints a two-section summary to stdout:

```
=== Consolidation Summary ===

SUCCESS
  Files processed:  <N>
  Events inserted:  <N>
  Events merged:    <N>
  Events removed:   <N>

ERRORS (<N> total)
  [<filename>] Line <N>: <error message>
  [<filename>] <error message>
```

If there are no errors the ERRORS section reads:

```
ERRORS
  None
```

## Structured Log Output

In addition to stdout, the mode emits a structured JSON log record at INFO level on completion:

```json
{
  "timestamp": "2026-05-31T12:34:56.789Z",
  "level": "INFO",
  "logger": "pipeline.modes.consolidate_journals",
  "message": "Consolidation complete",
  "correlation_id": "<uuid>",
  "mode_name": "consolidate_journals",
  "files_processed": 5,
  "events_inserted": 142,
  "events_merged": 18,
  "events_removed": 0,
  "error_count": 1
}
```

Each parse error is also emitted as a separate WARNING log record:

```json
{
  "level": "WARNING",
  "message": "Fragment parse error",
  "correlation_id": "<uuid>",
  "file": "fragment_2024_q1.csv",
  "line": 47,
  "detail": "Invalid value '£abc' in Value column"
}
```
