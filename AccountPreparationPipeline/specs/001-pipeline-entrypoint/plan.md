# Implementation Plan: Pipeline Entrypoint & Mode Dispatch

**Branch**: `001-pipeline-entrypoint` | **Date**: 2026-05-31 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/001-pipeline-entrypoint/spec.md`

## Summary

Build the main `pipeline.py` entrypoint script and its supporting `src/` package to provide a
mode-dispatch CLI for the Account Preparation Pipeline. The dispatcher uses `argparse` subparsers
and a `typing.Protocol`-based `ModeInterface` registry so new modes can be added by creating a
single conformant module — zero changes to the dispatcher. Every execution emits structured JSON
logs (stdlib `logging` + `python-json-logger`) with timestamps and correlation IDs, and outputs a
metrics record at completion. An `example` placeholder mode is included to validate the framework.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: `python-json-logger` (runtime); `pytest`, `pytest-bdd`, `pytest-cov`,
`mypy`, `ruff` (dev/test)
**Storage**: N/A
**Testing**: `pytest` (unit + integration), `pytest-bdd` (Gherkin BDD scenarios)
**Target Platform**: Command-line; Windows / macOS / Linux (Python standard only)
**Project Type**: CLI tool / pipeline script
**Performance Goals**: Sub-1s response for help display and unrecognised-mode errors (SC-003)
**Constraints**: No stack traces exposed to users; extensible without modifying dispatcher (FR-010)
**Scale/Scope**: Single-developer tool; initial delivery includes one placeholder mode (`example`)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] Virtual environment (`.venv`) planned; `requirements.txt` + `requirements-dev.txt` +
  `pyproject.toml` defined in project structure
- [x] No magic strings — mode names, exit codes, log field names, and format strings extracted to
  `src/constants.py`
- [x] SOLID principles applied — `ModeRegistry` (SRP), `Protocol`-based interface (OCP/LSP/ISP),
  `ExecutionContext` injected into modes (DIP), dispatcher has single reason to change (SRP)
- [x] All code fully type-annotated; `mypy --strict src/` planned as CI quality gate
- [x] `ruff check .` + `ruff format --check .` planned as CI quality gates
- [x] BDD Gherkin scenarios in `tests/features/`; pytest unit tests in `tests/unit/`; BDD
  framework: `pytest-bdd`
- [x] Structured logging with ISO 8601 timestamps and UUID correlation IDs covers all key
  milestones (startup, dispatch, mode start/end, metrics emission)

**Post-design re-check**: All gates confirmed after Phase 1 design. No violations.

## Project Structure

### Documentation (this feature)

```text
specs/001-pipeline-entrypoint/
├── plan.md              # This file
├── research.md          # Phase 0 decisions
├── data-model.md        # Entity definitions
├── quickstart.md        # Setup + run instructions
├── contracts/
│   ├── cli-contract.md          # CLI usage contract
│   └── mode-interface-contract.md  # Python Protocol contract
└── tasks.md             # Phase 2 output (/speckit-tasks — not yet created)
```

### Source Code (repository root)

```text
pipeline.py                  # Entrypoint script — argument parsing, registry setup, dispatch

src/
├── __init__.py
├── constants.py             # Named constants (exit codes, log field names, etc.)
├── context.py               # ExecutionContext dataclass
├── interfaces.py            # ModeInterface Protocol definition
├── registry.py              # ModeRegistry — register, get, list, contains
├── dispatcher.py            # Core dispatch logic — resolve mode, validate args, call execute
├── logging_config.py        # Structured logging setup (python-json-logger formatter + handlers)
├── metrics.py               # MetricsRecord dataclass + emit function
└── modes/
    ├── __init__.py
    └── example/
        ├── __init__.py
        └── mode.py          # ExampleMode — placeholder mode for framework validation

tests/
├── __init__.py
├── conftest.py              # Shared fixtures (registry, context, subprocess runner)
├── features/                # BDD Gherkin .feature files
│   ├── run_mode.feature     # US1 — execute a supported mode
│   ├── help_system.feature  # US2/US3 — top-level and mode-level help
│   ├── error_handling.feature  # US4 — unsupported mode, bad args, exceptions
│   └── steps/
│       └── pipeline_steps.py   # pytest-bdd step implementations
├── unit/
│   ├── test_registry.py
│   ├── test_dispatcher.py
│   ├── test_context.py
│   ├── test_metrics.py
│   ├── test_logging_config.py
│   └── test_example_mode.py
└── integration/
    └── test_pipeline_e2e.py  # Subprocess-level end-to-end tests

requirements.txt             # python-json-logger>=2.0
requirements-dev.txt         # pytest, pytest-bdd, pytest-cov, mypy, ruff, types-*
pyproject.toml               # Tool config: mypy, ruff, pytest sections
```

**Structure Decision**: Single project layout at repository root. `pipeline.py` is the executable
entrypoint; all supporting logic lives in `src/`. Tests mirror the `src/` structure under
`tests/unit/` and add BDD scenarios in `tests/features/`.

## Complexity Tracking

> No constitution violations. Table omitted.
