# Research: Journal Fragment Consolidation

**Feature**: 002-consolidate-journals
**Date**: 2026-05-31

## Decision 1: XLSX Read/Write Library

**Decision**: Use `pandas` (>=2.0) with `openpyxl` as the XLSX engine.

**Rationale**:
- The consolidated journal is inherently tabular (fixed schema, row-oriented) — a pandas DataFrame
  is the natural in-memory representation throughout the merge/dedup pipeline.
- `pandas.read_excel` and `DataFrame.to_excel` (backed by `openpyxl`) handle XLSX read/write with
  a single line each, avoiding hand-rolled cell iteration.
- Deduplication (`DataFrame.drop_duplicates`) and merge operations are first-class pandas
  operations, drastically reducing implementation complexity vs. manual row comparison.
- Both `pandas` and `openpyxl` are established, widely-used, actively-maintained libraries with
  full type stubs — compatible with `mypy --strict`.
- The parent project (PortfolioAnalysis.py) already depends on pandas, confirming it is a
  trusted dependency in this domain.

**Alternatives considered**:
- `openpyxl` alone (no pandas): Requires manual row iteration, dict accumulation, and
  custom dedup logic. Significantly more error-prone for a tabular pipeline. Rejected.
- `xlsxwriter`: Write-only; cannot read existing XLSX files. Rejected.
- `xlrd`: Read-only for legacy `.xls` files; no `.xlsx` write support. Rejected.

---

## Decision 2: CSV Parsing Library

**Decision**: Use Python's stdlib `csv` module for HL fragment file parsing.

**Rationale**:
- The HL CSV format is a standard delimited text file. The stdlib `csv.reader` handles quoting,
  line endings, and encoding edge cases correctly, with no additional dependency.
- The HL parser must scan for the header row by examining column values — this is trivially
  done with row-by-row iteration, which `csv.reader` supports natively.
- `csv.reader` provides line numbers via `reader.line_num`, satisfying FR-017 (error reporting
  with line numbers).

**Alternatives considered**:
- `pandas.read_csv`: Cannot scan for a dynamic header row position; always reads from row 0
  or a fixed skip count. The HL format requires header discovery. Rejected for the HL parser
  (pandas is still used for the consolidated journal store).

---

## Decision 3: Deduplication Key

**Decision**: Use `date + reference` as the composite key for identifying duplicate events
(resolving FR-003 — the [NEEDS CLARIFICATION] from the spec was not answered before planning).

**Rationale**:
- The `reference` column in HL exports (e.g., `B12345`, `S67890`) is a unique transaction
  identifier within the provider system. Combined with `date`, this forms a tight, reliable key
  with no realistic false positives.
- `sub_account` is excluded from the key because the same reference will always map to the same
  position; including it adds no discrimination and increases key surface area.
- For `contrib`/`BACS`/`Deposit` rows where no reference exists, a synthetic key of
  `date + action + value` is used to avoid dropping legitimate same-day cash events.

**Alternatives considered**:
- `date + reference + sub_account`: Wider key but provides no additional safety; reference
  is already unique per transaction. Rejected as unnecessarily complex.
- `date + sub_account + value + quantity`: Content-based; vulnerable to false positives if the
  same position is traded at the same price on the same day. Rejected.

---

## Decision 4: Fragment Parser Strategy Pattern

**Decision**: Define a `FragmentParser` Protocol with a single `parse()` method. Register
parsers per `ConsolidationMethod` enum value. The `ConsolidationEngine` resolves the correct
parser at runtime via a factory function.

**Rationale**:
- Mirrors the existing `ModeInterface` Pattern already established in the codebase — structural
  typing via `typing.Protocol` satisfies OCP: adding a new consolidation method (e.g., `AJ`,
  `IBKR`) requires only a new parser class, with zero changes to the engine or mode.
- The factory function maps `ConsolidationMethod.HL → HLFragmentParser()` — making the
  extension point explicit and type-safe.

---

## Decision 5: Summary Output Format

**Decision**: Emit the summary as both a structured log record (JSON, at INFO level) and a
human-readable two-section block to `stdout`.

**Rationale**:
- Constitution Principle VI mandates structured logging. The summary data (counts, file errors)
  is captured in a `ConsolidationSummary` dataclass, serialised to a log record, then also
  rendered as a human-readable block for interactive use.
- `print()` to stdout is acceptable for interactive summary output; it is not production data
  flow (the constitution prohibits `print()` in data-processing code, not in UI/summary output
  paths). The mode's execute method can call a dedicated `render_summary()` function that wraps
  this boundary cleanly.

**Alternatives considered**:
- Log-only (no stdout block): Would require users to parse JSON logs to see results. Poor
  interactive experience. Rejected.
- Rich / Click / tabulate for formatted tables: Additional dependency not justified for a
  two-section text block. Rejected.

---

## Decision 6: ActionType Enumeration

**Decision**: Define `ActionType` as a `str`-mixin `Enum` with values `buy`, `sell`, `contrib`,
`withdrawal`. Unknown HL action patterns produce a `ParseError` rather than a fallback value.

**Rationale**:
- A `str`-mixin enum serialises cleanly to the XLSX `action` column without a custom converter.
- Keeping the enum closed (no `UNKNOWN` catch-all) forces new action patterns to be explicitly
  handled when they appear, preventing silent data corruption.
- The spec (Assumption 8) confirms unmatched references must be logged as errors.

---

## Resolved NEEDS CLARIFICATION

- **FR-003 (deduplication key)**: Resolved as Decision 3 above — `date + reference`, with a
  synthetic fallback for rows that carry no reference (cash movements). User did not provide an
  answer before `/speckit-plan` was invoked; this default will be documented in plan.md and can
  be revised before implementation if the user prefers a different key.
