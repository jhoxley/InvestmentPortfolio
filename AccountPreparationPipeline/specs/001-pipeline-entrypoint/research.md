# Research: Pipeline Entrypoint & Mode Dispatch

**Feature**: 001-pipeline-entrypoint
**Date**: 2026-05-31

## Decision 1: CLI Argument Parsing & Mode Dispatch

**Decision**: Use Python's stdlib `argparse` with subparsers for top-level dispatch.

**Rationale**:
- `argparse.add_subparsers()` maps directly to the spec's mode concept — each registered mode
  adds its own subparser, providing automatic `--help` at both the top level and per-mode.
- Zero additional runtime dependency (stdlib).
- Subparsers integrate cleanly with a registry pattern: each mode module calls
  `register_arguments(subparser)` to declare its accepted arguments, satisfying FR-005/FR-006.
- The `set_defaults(func=...)` idiom on subparsers allows clean dispatch without any `if/elif`
  chains in the dispatcher — satisfying OCP (FR-010).

**Alternatives considered**:
- `click` groups: More ergonomic API but adds a runtime dependency. Constitution says prefer
  stdlib where it meets the requirement. Rejected.
- Custom argument tokeniser: Unnecessary complexity. Rejected.

---

## Decision 2: Mode Interface Contract

**Decision**: Define the mode interface using `typing.Protocol` (PEP 544).

**Rationale**:
- Structural subtyping: mode modules satisfy the contract by matching the expected attribute and
  method signatures — no inheritance from a base class required (OCP, ISP, DIP).
- Type-safe: `mypy --strict` enforces the contract at check time without runtime overhead.
- New modes are created by writing a conformant module; the registry and dispatcher never change
  (OCP / FR-010 satisfied).

**Alternatives considered**:
- Abstract Base Class (`abc.ABC`): Requires inheritance, creating tight coupling. Rejected.
- Duck typing with no formal interface: No type safety. Rejected.

---

## Decision 3: Structured Logging

**Decision**: Use Python's stdlib `logging` module with `python-json-logger` for JSON-structured
output.

**Rationale**:
- Constitution (Principle VI) mandates stdlib `logging`. `python-json-logger` wraps it with a
  JSON formatter — no architectural change, just a different formatter class.
- JSON output includes timestamp, level, module, message, and arbitrary extra fields, making it
  trivial to include correlation ID and mode name in every record.
- `python-json-logger` is stable, widely used, and actively maintained (5M+ weekly downloads).

**Alternatives considered**:
- `structlog`: More opinionated and feature-rich, but adds complexity. For this use case,
  `python-json-logger` is sufficient and lighter. Rejected.
- Custom `Formatter` subclass (stdlib only): Achievable but non-trivial to get right for all
  edge cases. `python-json-logger` provides this robustly. Rejected.

---

## Decision 4: BDD Testing Framework

**Decision**: Use `pytest-bdd` for Gherkin-style BDD tests.

**Rationale**:
- Integrates BDD scenarios directly into pytest, meaning a single `pytest` invocation runs unit
  tests, integration tests, and BDD scenarios together.
- Supports all pytest fixtures, which makes sharing setup (e.g., pipeline subprocess runner)
  between BDD steps and unit tests straightforward.
- `.feature` files are standard Gherkin, satisfying the constitution's requirement for Gherkin
  syntax (Principle V).

**Alternatives considered**:
- `behave`: A mature standalone BDD framework with its own runner. Requires separate invocation
  from pytest, complicating CI. Rejected.

---

## Decision 5: Metrics Output

**Decision**: Emit metrics as a structured log record (at INFO level) at the end of every
execution; no external sink in this feature.

**Rationale**:
- Spec assumption: "Metrics are written to stdout/log; a future feature may add export to an
  external sink."
- A `MetricsRecord` dataclass is serialised to JSON and emitted via the structured logger. This
  means metrics appear in the same log stream as trace events, making correlation trivial.
- Future export can be added by intercepting/parsing the metrics log record or by adding a
  metrics handler — no structural change required (OCP).

---

## Resolved NEEDS CLARIFICATION

None. All decisions derivable from the spec assumptions and the project constitution.
