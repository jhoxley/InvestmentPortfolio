# Data Model: Pipeline Entrypoint & Mode Dispatch

**Feature**: 001-pipeline-entrypoint
**Date**: 2026-05-31

## Entities

### ExecutionContext

Immutable value object created at pipeline startup and passed to the selected mode's execute
function. Provides all pipeline-level metadata needed for logging and tracing.

| Field | Type | Required | Description |
|---|---|---|---|
| `correlation_id` | `str` (UUID4) | Yes | Unique identifier for this execution run; appears in every log record |
| `start_time` | `datetime` (UTC) | Yes | Pipeline startup timestamp (UTC, timezone-aware) |
| `mode_name` | `str` | Yes | The mode name resolved from the command line |
| `raw_args` | `list[str]` | Yes | The raw command-line arguments passed to the pipeline (for audit logging) |

**Validation rules**:
- `correlation_id` MUST be a non-empty string; set once at startup; never mutated.
- `start_time` MUST be timezone-aware (UTC).
- `mode_name` MUST match an entry in the ModeRegistry before the context is passed to execute.

**State transitions**: None — this is an immutable value object. Created once, passed by
reference, never modified.

---

### ModeInterface (Protocol)

The formal contract every mode module must satisfy. Defined using `typing.Protocol` for
structural subtyping (no inheritance required).

| Attribute / Method | Type | Required | Description |
|---|---|---|---|
| `name` | `str` | Yes | Unique mode identifier; used as the subcommand name on the CLI |
| `description` | `str` | Yes | One-line human-readable description shown in top-level `--help` |
| `register_arguments(parser)` | `(ArgumentParser) -> None` | Yes | Adds the mode's accepted arguments to its argparse subparser |
| `execute(context, args)` | `(ExecutionContext, Namespace) -> int` | Yes | Executes the mode logic; returns an exit code (0 = success) |

**Validation rules**:
- `name` MUST be unique within the registry; lowercase, hyphen-separated, no spaces.
- `description` MUST be non-empty.
- `execute` MUST return an integer exit code; 0 = success; non-zero = failure.
- `register_arguments` MUST NOT raise exceptions during argument registration.

---

### ModeRegistry

The authoritative, singleton mapping of mode names to mode implementations. Populated at
application startup.

| Field | Type | Description |
|---|---|---|
| `_modes` | `dict[str, ModeInterface]` | Internal mapping of name → mode implementation |

**Operations**:

| Operation | Signature | Behaviour |
|---|---|---|
| `register` | `(mode: ModeInterface) -> None` | Adds a mode; raises `ValueError` if name already registered |
| `get` | `(name: str) -> ModeInterface` | Returns mode; raises `KeyError` if not found |
| `list_all` | `() -> list[ModeInterface]` | Returns all registered modes sorted by name |
| `contains` | `(name: str) -> bool` | Returns `True` if a mode with that name is registered |

**Validation rules**:
- Duplicate mode names MUST raise `ValueError` at registration time.
- `get` on an unregistered name MUST raise `KeyError` (not return `None`).

---

### MetricsRecord

Immutable summary of a single pipeline execution. Created at the end of each run and emitted as a
structured log record.

| Field | Type | Required | Description |
|---|---|---|---|
| `correlation_id` | `str` | Yes | Matches the `ExecutionContext.correlation_id` for this run |
| `mode_name` | `str` | Yes | The mode that was executed (or `"unknown"` if dispatch failed) |
| `start_time` | `datetime` | Yes | UTC start time |
| `end_time` | `datetime` | Yes | UTC end time |
| `duration_seconds` | `float` | Yes | `(end_time - start_time).total_seconds()` |
| `exit_status` | `int` | Yes | The final exit code returned to the OS |

**Validation rules**:
- `end_time` MUST be >= `start_time`.
- `duration_seconds` MUST be derived from `end_time - start_time`; never manually set.
- `exit_status` MUST be an integer.

---

### ArgumentSchema

A structured description of a single argument accepted by a mode. Used for help generation and
validation.

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | `str` | Yes | Argument name as it appears on the CLI (e.g., `--input-file`) |
| `description` | `str` | Yes | Human-readable explanation of the argument's purpose |
| `required` | `bool` | Yes | Whether the argument must be provided |
| `value_type` | `str` | Yes | Human-readable type description (e.g., `"file path"`, `"date YYYY-MM-DD"`) |
| `default` | `str \| None` | No | Default value description if the argument is optional |

**Validation rules**:
- `name` MUST begin with `--` for optional arguments; no prefix for positional.
- `description` MUST be non-empty.

## Entity Relationships

```
pipeline startup
    │
    ├─ creates ──────────────► ExecutionContext (1 per run)
    │                              │
    │                              └─ passed to ──► ModeInterface.execute()
    │
    ├─ consults ─────────────► ModeRegistry (singleton)
    │                              │
    │                              └─ contains ──► ModeInterface (0..N modes)
    │                                                  │
    │                                                  └─ declares ──► ArgumentSchema (0..N args)
    │
    └─ produces ─────────────► MetricsRecord (1 per run, emitted to log)
```
