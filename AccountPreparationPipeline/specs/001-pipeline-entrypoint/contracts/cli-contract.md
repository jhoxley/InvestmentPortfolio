# Contract: Pipeline CLI Interface

**Feature**: 001-pipeline-entrypoint
**Date**: 2026-05-31
**Type**: CLI command contract

## Overview

The pipeline exposes a single entry-point script (`pipeline.py`) that accepts a mode name as a
positional argument followed by mode-specific arguments. The script supports `--help` at both the
top level and per-mode.

## Top-Level Usage

```
python pipeline.py [--help] [--log-level {DEBUG,INFO,WARNING,ERROR}] <mode> [mode-args...]
```

### Top-Level Arguments

| Argument | Required | Default | Description |
|---|---|---|---|
| `mode` | Yes (unless `--help`) | — | The name of the pipeline mode to execute |
| `--help` | No | — | Print available modes and their descriptions; exit 0 |
| `--log-level` | No | `INFO` | Set the minimum log level for structured output |

## Invocation Patterns

### Pattern 1 — Top-level help

```
python pipeline.py
python pipeline.py --help
```

**Output** (stdout):

```
usage: pipeline.py [-h] [--log-level {DEBUG,INFO,WARNING,ERROR}] <mode> ...

Account Preparation Pipeline

Available modes:
  example    A placeholder mode used for framework validation

optional arguments:
  -h, --help            show this help message and exit
  --log-level {DEBUG,INFO,WARNING,ERROR}
                        Minimum log level (default: INFO)
```

**Exit code**: 0

---

### Pattern 2 — Mode-level help

```
python pipeline.py <mode> --help
```

**Output** (stdout): mode name, description, and argument list.

**Exit code**: 0

---

### Pattern 3 — Execute a mode

```
python pipeline.py [--log-level LEVEL] <mode> [mode-specific-args...]
```

**Stdout**: Metrics summary (JSON) at the end of execution.
**Stderr**: Structured log records (JSON) throughout execution.
**Exit code**: 0 on success; non-zero on failure (see Exit Code Contract below).

---

### Pattern 4 — Unrecognised mode

```
python pipeline.py unknownmode
```

**Stderr**: Error message identifying the unknown mode and listing valid alternatives.
**Exit code**: 1

---

## Exit Code Contract

| Code | Meaning |
|---|---|
| `0` | Execution completed successfully |
| `1` | Unrecognised mode name |
| `2` | Invalid or missing mode arguments |
| `3` | Mode execution failed (exception caught at pipeline level) |

## Log Output Contract

Every structured log record emitted to stderr MUST contain:

| Field | Type | Example |
|---|---|---|
| `timestamp` | ISO 8601 UTC | `"2026-05-31T10:00:00.000Z"` |
| `level` | string | `"INFO"` |
| `correlation_id` | UUID string | `"a1b2c3d4-..."` |
| `module` | string | `"dispatcher"` |
| `message` | string | `"Dispatching to mode: example"` |

Additional context fields (e.g., `mode_name`, `exit_status`) MAY be included in any record.

## Metrics Output Contract

At the end of every execution, a metrics record is emitted as a structured log record at INFO
level with the following fields:

| Field | Type | Example |
|---|---|---|
| `event` | `"metrics"` | Fixed sentinel value to identify metrics records |
| `correlation_id` | UUID string | `"a1b2c3d4-..."` |
| `mode_name` | string | `"example"` |
| `start_time` | ISO 8601 UTC | `"2026-05-31T10:00:00.000Z"` |
| `end_time` | ISO 8601 UTC | `"2026-05-31T10:00:01.250Z"` |
| `duration_seconds` | float | `1.25` |
| `exit_status` | integer | `0` |
