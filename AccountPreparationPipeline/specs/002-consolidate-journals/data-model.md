# Data Model: Journal Fragment Consolidation

**Feature**: 002-consolidate-journals
**Date**: 2026-05-31

## Entities

### ActionType

String-mixin enumeration of all valid normalised action values that can appear in the
consolidated journal. Every fragment parser maps raw provider-specific action tokens to one of
these values.

| Value | String | Trigger (HL method) |
|---|---|---|
| `BUY` | `"buy"` | Reference matches pattern `B` + one or more digits |
| `SELL` | `"sell"` | Reference matches pattern `S` + one or more digits |
| `CONTRIB` | `"contrib"` | Action/type field equals `"Deposit"` or `"BACS"` |
| `WITHDRAWAL` | `"withdrawal"` | Reserved for future provider mappings |

**Validation rules**:
- No `UNKNOWN` or fallback value exists. Rows whose action cannot be mapped produce a `ParseError`.
- The string representation is used directly when writing the `action` column to XLSX.

---

### JournalEvent

Immutable value object representing a single normalised financial event. All parser output is
expressed as a sequence of `JournalEvent` instances.

| Field | Type | Required | Description |
|---|---|---|---|
| `date` | `datetime.date` | Yes | Settlement date (preferred); trade date used only if settlement date is absent |
| `account` | `str` | Yes | Free-text account identifier passed as the fourth CLI argument |
| `sub_account` | `str` | Yes | Investment or position name, derived from the source Description with unit-cost/quantity suffix stripped |
| `action` | `ActionType` | Yes | Normalised action type |
| `reference` | `str` | Yes | Original reference string from the source journal (e.g. `"B12345"`), passed through unchanged |
| `value` | `Decimal` | Yes | Transaction value in GBP |
| `quantity` | `Decimal \| None` | No | Number of units involved; `None` for cash-only events |

**Validation rules**:
- `date` MUST be a valid calendar date.
- `account` MUST be non-empty.
- `sub_account` MUST be non-empty.
- `value` MUST be a finite decimal; infinite or NaN values produce a `ParseError`.
- `quantity`, when present, MUST be a finite, non-negative decimal.

**Deduplication key** (for merge into consolidated journal):
- Primary: `date + reference` (where `reference` is non-empty and contains a provider transaction ID).
- Fallback for cash/deposit rows (no unique reference): `date + action + value` to avoid
  coalescing distinct same-day cash events.

---

### ParseError

Represents a single failure encountered while parsing a journal fragment. File-level failures
(e.g. header not found) have no `line_number`; row-level failures include the originating line.

| Field | Type | Required | Description |
|---|---|---|---|
| `file_path` | `pathlib.Path` | Yes | Absolute path to the fragment file that produced the error |
| `line_number` | `int \| None` | No | CSV reader line number where the failure occurred; `None` for file-level errors |
| `message` | `str` | Yes | Human-readable description of the error |

**Validation rules**:
- `message` MUST be non-empty.
- `line_number`, when present, MUST be a positive integer.

---

### ParseResult

Return value from any `FragmentParser.parse()` call. Aggregates successfully parsed events and
all errors encountered during parsing of a single fragment file. A result with an empty events
list and a non-empty errors list indicates a completely unparseable file.

| Field | Type | Required | Description |
|---|---|---|---|
| `events` | `list[JournalEvent]` | Yes | All events successfully extracted from the fragment |
| `errors` | `list[ParseError]` | Yes | All errors encountered during parsing |

**Validation rules**:
- Both lists are always present (never `None`); either may be empty.
- A file with a header but zero data rows produces `ParseResult(events=[], errors=[])` —
  not an error condition.

---

### ConsolidationMethod

Enumeration of supported fragment-parsing strategies. Determines which `FragmentParser`
implementation is used.

| Value | String | Description |
|---|---|---|
| `HL` | `"HL"` | Hargreaves Lansdown CSV export format |

**Extension rule**: Adding a new method requires (a) a new enum value, (b) a new `FragmentParser`
implementation, and (c) a factory mapping — no other code changes.

---

### ConsolidationSummary

Immutable record of the outcome of a single `consolidate_journals` invocation. Emitted as both
a structured log record and a human-readable console block on completion.

| Field | Type | Required | Description |
|---|---|---|---|
| `files_processed` | `int` | Yes | Number of fragment files attempted (including those with errors) |
| `events_inserted` | `int` | Yes | Net new rows added to the consolidated journal |
| `events_merged` | `int` | Yes | Rows from fragments that matched an existing row by dedup key (skipped) |
| `events_removed` | `int` | Yes | Rows removed from the journal during this run (reserved; always 0 in initial implementation) |
| `errors` | `list[ParseError]` | Yes | All errors encountered across all fragment files |

**Validation rules**:
- `events_inserted`, `events_merged`, `events_removed` MUST all be non-negative.
- `files_processed` MUST equal the number of fragment files iterated (whether or not they
  produced errors).

---

### JournalStore

Stateful service responsible for loading the existing consolidated journal from XLSX (or
initialising an empty store) and persisting the merged result. Owns the canonical column schema.

**XLSX schema** (column order is fixed):

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `date` | date (YYYY-MM-DD) | No | |
| `account` | str | No | |
| `sub_account` | str | No | |
| `action` | str | No | One of the `ActionType` string values |
| `reference` | str | No | |
| `value` | decimal/float | No | GBP |
| `quantity` | decimal/float | Yes | Empty cell when not applicable |

**Operations**:

| Operation | Signature | Behaviour |
|---|---|---|
| `load` | `(path: Path) -> JournalStore` | Reads existing XLSX or returns empty store if file absent |
| `merge` | `(events: list[JournalEvent]) -> tuple[int, int]` | Inserts new events, skips duplicates; returns (inserted, merged) |
| `save` | `(path: Path) -> None` | Writes current state to XLSX, creating parent directories as needed |

**Validation rules**:
- Column names and order MUST match the schema exactly; any mismatch when loading raises a
  descriptive `ValueError`.
- `save` MUST be atomic with respect to the file; write to a temporary path then rename.

---

### FragmentParser (Protocol)

The formal contract every parser module must satisfy. Structural typing via `typing.Protocol` —
no inheritance required.

| Method | Signature | Behaviour |
|---|---|---|
| `parse` | `(file_path: Path, account: str) -> ParseResult` | Parses a single fragment file and returns all events and errors |

**Implementors**:
- `HLFragmentParser` — implements the `HL` consolidation method.

---

## Entity Relationships

```
CLI invocation
    │
    ├─ creates ─────────────────► ConsolidationEngine
    │                                   │
    │                         ┌─────────┴─────────────┐
    │                         │                       │
    │                    resolves                  loads/saves
    │                         │                       │
    │                   FragmentParser           JournalStore
    │                   (Protocol)                    │
    │                         │                   contains ──► JournalEvent (0..N)
    │                   parse(file) ──────────►
    │                                        ParseResult
    │                                            │
    │                               ┌────────────┴────────────┐
    │                               │                         │
    │                        list[JournalEvent]          list[ParseError]
    │                               │
    │                       merge into JournalStore
    │
    └─ produces ────────────────► ConsolidationSummary (1 per run)
```
