<!--
SYNC IMPACT REPORT
==================
Version change: [template] → 1.0.0 (initial ratification — template fully instantiated)

Added sections:
- I. Python-First & Dependency Management (new)
- II. SOLID Design (new)
- III. Type Safety (new)
- IV. Code Quality Standards (new)
- V. Test-Driven Development with BDD (new)
- VI. Structured Observability (new)
- Technology Stack & Toolchain (new)
- Quality Gates & Definition of Done (new)
- Governance (filled from template)

Modified principles: N/A (first real version)
Removed sections: N/A

Templates updated:
- ✅ .specify/templates/plan-template.md — Constitution Check gates updated
- ✅ .specify/templates/tasks-template.md — testing task structure updated
- ✅ .specify/templates/spec-template.md — no changes required (technology-agnostic)
- ✅ .specify/templates/constitution-template.md — source template unchanged (correct)

Deferred TODOs: None
-->

# AccountPreparationPipeline Constitution

## Core Principles

### I. Python-First & Dependency Management

All code MUST be written in standard Python (3.11+) using a virtual environment (`.venv`) local to
the project. Package dependencies MUST be declared in `requirements.txt` (runtime) and
`requirements-dev.txt` (dev/test tooling), managed exclusively via `pip`. Project-wide
configuration MUST use `pyproject.toml` for tool settings (MyPy, Ruff, pytest, behave).

No magic numbers or magic strings are permitted anywhere in source code — all such values MUST be
extracted into named constants in a dedicated `constants.py` or equivalent config module. Prefer
stable, well-established Python libraries over custom implementations of the same functionality;
any exception MUST be justified in the relevant spec or plan document.

**Rationale**: Reproducible environments and declared dependencies prevent "works on my machine"
failures. Named constants make intent explicit and changes auditable.

### II. SOLID Design (NON-NEGOTIABLE)

All production code MUST adhere to the five SOLID principles:

- **Single Responsibility**: Every class and module has one reason to change.
- **Open/Closed**: Extend behaviour via new classes or strategies, not by modifying existing code.
- **Liskov Substitution**: Subtypes are fully substitutable for their base types without altering
  correctness.
- **Interface Segregation**: Depend only on the interfaces a client actually uses; no fat interfaces.
- **Dependency Inversion**: High-level modules depend on abstractions; concrete details are injected.

Where existing code violates SOLID, it MUST be refactored before new functionality is added to
that module. Complexity MUST be justified — design patterns are adopted when they reduce coupling
or increase testability, not for their own sake.

**Rationale**: SOLID code is independently testable, replaceable, and extensible without cascading
changes — critical for a pipeline that will grow over time.

### III. Type Safety (NON-NEGOTIABLE)

All source code MUST carry complete PEP 484 / PEP 526 type annotations. `mypy --strict` MUST
report zero errors before any code is considered complete. Use of `Any` is forbidden unless
accompanied by a `# type: ignore[misc]` comment explaining why the exception is necessary and
time-bounded. Third-party stubs (`types-*` packages) MUST be installed as dev dependencies when
available.

**Rationale**: Type annotations act as machine-checked documentation and catch entire classes of
bugs at authoring time rather than at runtime.

### IV. Code Quality Standards (NON-NEGOTIABLE)

`ruff check` and `ruff format --check` MUST both pass with zero violations before code is
considered complete. The Ruff configuration in `pyproject.toml` is the single source of truth for
style rules. Dead code, unused imports, and unreachable branches MUST be removed, not commented
out. PEP 8 naming conventions MUST be followed throughout.

**Rationale**: Consistent style reduces cognitive overhead and automated checking ensures
standards are enforced uniformly rather than relying on reviewer attention.

### V. Test-Driven Development with BDD (NON-NEGOTIABLE)

Every feature MUST have BDD-style acceptance tests written in Gherkin syntax (`.feature` files)
using `behave` or `pytest-bdd`. Every lower-level function and class MUST have a corresponding
`pytest` unit test suite. The sequence is strictly: write tests → confirm they fail → implement →
confirm they pass. No feature is considered complete until:

1. All Gherkin scenarios pass.
2. All unit tests pass.
3. MyPy reports zero errors.
4. Ruff reports zero violations.

Tests live in `tests/` with subdirectories `tests/features/` (BDD), `tests/unit/`, and
`tests/integration/`. Test data lives in `tests/data/` organised by function or scenario name.

**Rationale**: Tests written before implementation prove requirements are understood, prevent
regressions, and make refactoring safe. BDD scenarios serve as living documentation for
non-technical stakeholders.

### VI. Structured Observability

All code MUST use structured logging via Python's standard `logging` library. Every log record
MUST include at minimum: ISO 8601 timestamp, a correlation/run ID, the module name, the log
level, and sufficient contextual state (key variable values, entity identifiers) to trace data
flow and diagnose issues without attaching a debugger. Log levels MUST be used semantically:
DEBUG for detailed trace state, INFO for normal flow milestones, WARNING for recoverable
anomalies, ERROR for failures. No `print()` statements are permitted in production code.

**Rationale**: Pipelines process data in batch; without structured, correlated logs it is
impossible to diagnose which record caused a failure or to replay partial runs confidently.

## Technology Stack & Toolchain

| Concern | Tool | Notes |
|---|---|---|
| Language | Python 3.11+ | Standard CPython; venv in `.venv/` |
| Dependency management | pip + `requirements*.txt` | `pyproject.toml` for tool config |
| Type checking | MyPy (`--strict`) | Zero errors required |
| Linting / formatting | Ruff | Zero violations required |
| Unit testing | pytest | `tests/unit/` |
| BDD testing | behave or pytest-bdd | `tests/features/*.feature` |
| Integration testing | pytest | `tests/integration/` |
| Logging | stdlib `logging` | Structured JSON or key=value format |

All toolchain versions MUST be pinned in `requirements-dev.txt` and updated deliberately.

## Quality Gates & Definition of Done

Code is **not complete** until ALL four gates are green:

1. **Tests pass** — `pytest` exits 0 and all Gherkin scenarios pass.
2. **Type safe** — `mypy --strict src/` exits 0.
3. **Standards met** — `ruff check .` and `ruff format --check .` both exit 0.
4. **Logging present** — structured log statements cover all significant entry/exit points and
   data-processing milestones.

These gates MUST be verified locally before any code review or merge request is raised. CI MUST
enforce the same gates automatically.

## Governance

This constitution supersedes all other documented practices within this project. Amendments MUST:

1. Increment the version number following semantic versioning (MAJOR for breaking governance
   changes, MINOR for additions, PATCH for clarifications).
2. Update `LAST_AMENDED_DATE`.
3. Record the change in the Sync Impact Report comment at the top of this file.
4. Propagate any affected changes to dependent templates (plan, spec, tasks).
5. Be committed with message: `docs: amend constitution to vX.Y.Z (<summary>)`.

All pull requests and code reviews MUST verify compliance with this constitution. Any violation
that cannot be remediated immediately MUST be logged as a tracked issue with a resolution target
date — it does not block merge but MUST not be left indefinitely.

**Version**: 1.0.0 | **Ratified**: 2026-05-31 | **Last Amended**: 2026-05-31
