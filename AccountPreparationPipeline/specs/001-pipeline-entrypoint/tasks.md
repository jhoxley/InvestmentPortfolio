---
description: "Task list for Pipeline Entrypoint & Mode Dispatch (001-pipeline-entrypoint)"
---

# Tasks: Pipeline Entrypoint & Mode Dispatch

**Input**: Design documents from `specs/001-pipeline-entrypoint/`
**Prerequisites**: plan.md âœ… spec.md âœ… research.md âœ… data-model.md âœ… contracts/ âœ…

**Tests**: Tests are MANDATORY per constitution (Principle V). All user stories include Gherkin
BDD feature files and pytest unit tests. Tests MUST be written and confirmed failing BEFORE
implementation begins (Red-Green-Refactor).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1â€“US4)
- Exact file paths are included in all implementation descriptions

---

## Phase 1: Setup (Project Initialization)

**Purpose**: Create the project skeleton â€” directory structure, dependency files, tool config.

- [x] T001 Create project directory structure: `src/`, `src/modes/`, `tests/unit/`, `tests/features/steps/`, `tests/integration/`, `tests/data/`
- [x] T002 Create `pyproject.toml` with `[tool.mypy]` (strict mode), `[tool.ruff]`, `[tool.ruff.lint]`, and `[tool.pytest.ini_options]` sections (testpaths = tests/, markers for bdd)
- [x] T003 [P] Create `requirements.txt` with pinned runtime dependency: `python-json-logger>=2.0,<3.0`
- [x] T004 [P] Create `requirements-dev.txt` with pinned dev/test dependencies: `pytest`, `pytest-bdd`, `pytest-cov`, `mypy`, `ruff`, `types-python-json-logger`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that ALL user stories depend on. No story work begins until
this phase is complete.

**âš ï¸ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T005 Create `src/__init__.py` (empty, marks src as a package)
- [x] T006 [P] Create `src/constants.py` â€” define named constants: `EXIT_SUCCESS = 0`, `EXIT_UNKNOWN_MODE = 1`, `EXIT_INVALID_ARGS = 2`, `EXIT_EXECUTION_FAILURE = 3`; log field names `LOG_CORRELATION_ID`, `LOG_MODE_NAME`, `LOG_EVENT`; sentinel `METRICS_EVENT = "metrics"`
- [x] T007 [P] Create `src/interfaces.py` â€” define `ModeInterface` using `typing.Protocol` with attributes `name: str`, `description: str`, and methods `register_arguments(parser: ArgumentParser) -> None`, `execute(context: ExecutionContext, args: Namespace) -> int`
- [x] T008 [P] Create `src/context.py` â€” define `ExecutionContext` as a frozen `dataclass` with fields: `correlation_id: str`, `start_time: datetime`, `mode_name: str`, `raw_args: list[str]`; include a factory `classmethod create(mode_name, raw_args) -> ExecutionContext` that generates a UUID4 correlation ID and captures UTC now
- [x] T009 Create `src/logging_config.py` â€” implement `configure_logging(level: str) -> logging.Logger` that installs a `python_json_logger.JsonFormatter` handler on the root logger; formatter MUST include `timestamp`, `level`, `module`, and any `extra` fields passed to log calls
- [x] T010 [P] Create `src/metrics.py` â€” define `MetricsRecord` frozen dataclass with `correlation_id`, `mode_name`, `start_time`, `end_time`, `duration_seconds` (derived property), `exit_status`; implement `emit_metrics(record: MetricsRecord, logger: logging.Logger) -> None` that logs at INFO with `extra={LOG_EVENT: METRICS_EVENT, ...record fields}`
- [x] T011 Create `src/registry.py` â€” implement `ModeRegistry` class with `register(mode: ModeInterface) -> None` (raises `ValueError` on duplicate name), `get(name: str) -> ModeInterface` (raises `KeyError` if not found), `list_all() -> list[ModeInterface]` (sorted by name), `contains(name: str) -> bool`
- [x] T012 Create `tests/__init__.py`, `tests/unit/__init__.py`, `tests/integration/__init__.py`, `tests/features/__init__.py`, `tests/features/steps/__init__.py`
- [x] T013 Create `tests/conftest.py` â€” define shared pytest fixtures: `example_registry()` (a ModeRegistry pre-loaded with ExampleMode), `base_context()` (an ExecutionContext with fixed test values), `run_pipeline(tmp_path)` (a helper that invokes `pipeline.py` as a subprocess and captures stdout/stderr/exit code)

**Checkpoint**: Foundation ready â€” user story implementation can now begin in parallel.

---

## Phase 3: User Story 1 â€” Run a Supported Pipeline Mode (Priority: P1) ðŸŽ¯ MVP

**Goal**: A mode can be executed end-to-end â€” args parsed, mode dispatched, logs emitted,
metrics printed.

**Independent Test**: Run `python pipeline.py example --message "hello"` â†’ mode executes,
structured JSON logs appear on stderr, metrics record on stdout, exit code 0.

### Tests for User Story 1 âš ï¸ (MANDATORY â€” write FIRST, ensure they FAIL before implementation)

- [x] T014 [P] [US1] Write `tests/features/run_mode.feature` â€” Gherkin scenarios covering: valid mode + args executes successfully (exit 0, logs present, metrics present); missing required arg exits non-zero with error message; extraneous arg exits non-zero with informative message
- [x] T015 [P] [US1] Write `tests/features/steps/run_mode_steps.py` â€” pytest-bdd step implementations for all scenarios in `run_mode.feature`; use `run_pipeline` fixture from conftest
- [x] T016 [P] [US1] Write `tests/unit/test_registry.py` â€” unit tests for `ModeRegistry`: register succeeds, duplicate name raises `ValueError`, get returns correct mode, get on missing name raises `KeyError`, list_all returns sorted list, contains returns correct bool
- [x] T017 [P] [US1] Write `tests/unit/test_dispatcher.py` â€” unit tests for `dispatch()`: valid mode + parsed args â†’ `execute()` called and exit code returned; covers happy path only (error cases in US4)
- [x] T018 [P] [US1] Write `tests/unit/test_context.py` â€” unit tests for `ExecutionContext.create()`: `correlation_id` is valid UUID4, `start_time` is UTC-aware, `mode_name` matches input, `raw_args` preserved
- [x] T019 [P] [US1] Write `tests/unit/test_metrics.py` â€” unit tests for `MetricsRecord`: `duration_seconds` equals `(end_time - start_time).total_seconds()`; `emit_metrics` emits an INFO log record with `event = "metrics"` and all required fields

### Implementation for User Story 1

- [x] T020 [P] [US1] Create `src/modes/__init__.py` and `src/modes/example/__init__.py` (empty package markers)
- [x] T021 [P] [US1] Create `src/modes/example/mode.py` â€” implement `ExampleMode` class: `name = "example"`, `description = "Placeholder mode for framework validation"`, `register_arguments` adds `--message` (required str, help text explains purpose), `execute` logs the message at INFO and returns `EXIT_SUCCESS`
- [x] T022 [US1] Create `src/dispatcher.py` â€” implement `dispatch(registry: ModeRegistry, context: ExecutionContext, args: Namespace) -> int`; logs dispatch start with correlation ID and mode name; calls `mode.execute(context, args)`; returns the mode's exit code
- [x] T023 [US1] Create `pipeline.py` entrypoint â€” build `ArgumentParser` with `--log-level` flag; call `registry.register(ExampleMode())`; create subparsers, call `mode.register_arguments(subparser)` for each mode; parse args; create `ExecutionContext`; call `configure_logging`; call `dispatch`; capture exit code
- [x] T024 [US1] Wire metrics emission in `pipeline.py` â€” after `dispatch` returns, capture `end_time = datetime.now(UTC)`; construct `MetricsRecord`; call `emit_metrics`; pass exit code to `sys.exit()`

**Checkpoint**: `python pipeline.py example --message "test"` executes end-to-end with logs + metrics.
User Story 1 is fully functional and independently testable.

---

## Phase 4: User Story 2 â€” Discover Available Modes (Priority: P2)

**Goal**: `python pipeline.py --help` (and zero-arg invocation) lists all registered modes
with descriptions.

**Independent Test**: Run `python pipeline.py --help` â†’ output contains "example" and its
description; exit code 0.

### Tests for User Story 2 âš ï¸ (MANDATORY â€” write FIRST, ensure they FAIL before implementation)

- [x] T025 [P] [US2] Write `tests/features/help_system.feature` â€” Gherkin scenarios for top-level help: invoking with no args shows mode list and exits 0; invoking with `--help` shows mode list and exits 0; every registered mode appears in output with a non-empty description
- [x] T026 [P] [US2] Write `tests/features/steps/help_steps.py` â€” pytest-bdd step implementations for all scenarios in `help_system.feature` (top-level help section)
- [x] T027 [P] [US2] Write `tests/unit/test_pipeline_help.py` â€” unit tests verifying `ArgumentParser` formatter output includes all registered mode names and descriptions when `--help` is passed

### Implementation for User Story 2

- [x] T028 [US2] Update `pipeline.py` argparse setup â€” set `prog`, `description`, and `formatter_class = argparse.RawDescriptionHelpFormatter`; configure subparsers `title = "Available modes"` so mode names and descriptions appear in `--help` output automatically
- [x] T029 [US2] Handle zero-argument invocation in `pipeline.py` â€” if `sys.argv[1:]` is empty, call `parser.print_help()` and `sys.exit(EXIT_SUCCESS)` before parsing

**Checkpoint**: `python pipeline.py` and `python pipeline.py --help` both list all modes.
User Stories 1 AND 2 are independently functional.

---

## Phase 5: User Story 3 â€” Discover Mode-Specific Arguments (Priority: P3)

**Goal**: `python pipeline.py example --help` lists the mode's accepted arguments with
human-readable descriptions.

**Independent Test**: Run `python pipeline.py example --help` â†’ output lists `--message`,
marks it as required, and shows a non-empty description; exit code 0.

### Tests for User Story 3 âš ï¸ (MANDATORY â€” write FIRST, ensure they FAIL before implementation)

- [x] T030 [P] [US3] Extend `tests/features/help_system.feature` with US3 scenarios â€” mode-level `--help` shows mode name, description, and full argument list with required/optional status and human-readable explanations for each argument
- [x] T031 [P] [US3] Write `tests/unit/test_example_mode.py` â€” unit tests for `ExampleMode.register_arguments`: verifies `--message` is registered with `required=True` and a non-empty `help` string; verifies `ExampleMode.description` is non-empty

### Implementation for User Story 3

- [x] T032 [US3] Verify mode-level `--help` works via argparse subparser (no new code needed in dispatcher â€” confirm by running `python pipeline.py example --help` after T023)
- [x] T033 [US3] Enrich `src/modes/example/mode.py` â€” update `--message` help text to be a full human-readable explanation suitable for end-user documentation per FR-006; add `metavar` for clarity

**Checkpoint**: `python pipeline.py example --help` shows full argument documentation.
User Stories 1, 2, AND 3 are independently functional.

---

## Phase 6: User Story 4 â€” Handle Unsupported Modes Gracefully (Priority: P4)

**Goal**: Any invalid invocation (bad mode name, missing args, execution exception) produces a
clean error message â€” no stack trace, non-zero exit code, valid modes listed.

**Independent Test**: Run `python pipeline.py nonexistent` â†’ clean error message lists valid
modes, no Python traceback visible, exit code 1.

### Tests for User Story 4 âš ï¸ (MANDATORY â€” write FIRST, ensure they FAIL before implementation)

- [x] T034 [P] [US4] Write `tests/features/error_handling.feature` â€” Gherkin scenarios: unrecognised mode exits 1 with clean error (no traceback) listing valid modes; mode raises exception â†’ exits 3 with clean message and correlation ID (no traceback)
- [x] T035 [P] [US4] Write `tests/features/steps/error_steps.py` â€” pytest-bdd step implementations for all scenarios in `error_handling.feature`
- [x] T036 [P] [US4] Extend `tests/unit/test_dispatcher.py` â€” unit tests for error paths: unrecognised mode name returns `EXIT_UNKNOWN_MODE` and message contains valid mode list; exception in `execute()` returns `EXIT_EXECUTION_FAILURE` and no exception propagates

### Implementation for User Story 4

- [x] T037 [US4] Implement unrecognised-mode error handling in `src/dispatcher.py` â€” if mode name not in registry, log WARNING with correlation ID and mode name, write clean error to stderr listing all valid modes from `registry.list_all()`, return `EXIT_UNKNOWN_MODE`
- [x] T038 [US4] Implement exception catch in `src/dispatcher.py` â€” wrap `mode.execute(context, args)` in `try/except Exception`, log ERROR with correlation ID and exception message (no traceback to stderr), return `EXIT_EXECUTION_FAILURE`
- [x] T039 [US4] Validate no stack trace exposure â€” run all error-scenario tests and grep stderr output for `Traceback` to confirm none is present

**Checkpoint**: All US4 error scenarios pass; stderr contains no raw tracebacks.
All four user stories are independently functional.

---

## Phase N: Polish & Cross-Cutting Concerns

**Purpose**: End-to-end validation, quality gates, and observability audit.

- [x] T040 [P] Write `tests/integration/test_pipeline_e2e.py` â€” subprocess-based end-to-end tests exercising all four user stories as a black box: valid execution, top-level help, mode help, unknown mode; assert exit codes, stdout/stderr content, JSON log structure
- [x] T041 [P] Run `mypy --strict src/` â€” resolve any type errors until exit code is 0 (Constitution gate III)
- [x] T042 [P] Run `ruff check .` and `ruff format --check .` â€” resolve all violations until both exit 0 (Constitution gate IV)
- [x] T043 Audit structured logging coverage â€” manually review that every key milestone in `pipeline.py`, `dispatcher.py`, `registry.py`, `metrics.py` emits a log record with `correlation_id` in `extra={}` (Constitution gate VI)
- [x] T044 Run full test suite `pytest` â€” confirm all BDD scenarios and unit tests pass with exit 0 (Constitution gate V)
- [x] T045 Validate `specs/001-pipeline-entrypoint/quickstart.md` â€” follow setup and run instructions end-to-end and confirm all steps succeed as documented

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies â€” start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 completion â€” BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Phase 2 completion â€” MVP; unblocks US2, US3, US4
- **User Story 2 (Phase 4)**: Depends on Phase 2; integrates with US1 `pipeline.py` â€” can start
  in parallel with US1 after Phase 2 if staffed
- **User Story 3 (Phase 5)**: Depends on Phase 2; extends US1 `ExampleMode` â€” write tests after
  US1 implementation, or in parallel if using a stub
- **User Story 4 (Phase 6)**: Depends on Phase 2; extends `dispatcher.py` from US1
- **Polish (Phase N)**: Depends on all desired user stories being complete

### User Story Dependencies

- **US1 (P1)**: Can start after Foundational (Phase 2) â€” no dependencies on other stories
- **US2 (P2)**: Can start after Foundational â€” modifies `pipeline.py` (integrate after US1 done)
- **US3 (P3)**: Can start after Foundational â€” modifies `ExampleMode` (can overlap with US1)
- **US4 (P4)**: Can start after Foundational â€” extends `dispatcher.py` (integrate after US1 done)

### Within Each User Story

- Write tests FIRST â†’ confirm they FAIL â†’ implement â†’ confirm they PASS
- Models/dataclasses before services
- Core logic before entrypoint wiring
- Complete story before moving to next priority

---

## Parallel Opportunities

### Phase 1 Setup

```
T001 (create dirs)
T002 (pyproject.toml)    T003 [P] (requirements.txt)    T004 [P] (requirements-dev.txt)
```

### Phase 2 Foundational

```
T006 [P] (constants.py)    T007 [P] (interfaces.py)    T008 [P] (context.py)    T010 [P] (metrics.py)
         â†“ (all complete) â†“
T009 (logging_config.py)    T011 (registry.py)
         â†“ (all complete) â†“
T012 (test __init__.py files)    T013 (conftest.py)
```

### Phase 3 User Story 1

```
T014 [P] (run_mode.feature)
T015 [P] (run_mode_steps.py)
T016 [P] (test_registry.py)      â† all WRITE + FAIL in parallel
T017 [P] (test_dispatcher.py)
T018 [P] (test_context.py)
T019 [P] (test_metrics.py)
         â†“ (all fail confirmed) â†“
T020 [P] (modes/__init__.py)    T021 [P] (example/mode.py)
         â†“ (complete) â†“
T022 (dispatcher.py)
T023 (pipeline.py)    â† depends on T022
T024 (metrics wiring) â† depends on T023
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001â€“T004)
2. Complete Phase 2: Foundational (T005â€“T013) â€” CRITICAL BLOCKER
3. Complete Phase 3: User Story 1 (T014â€“T024)
4. **STOP and VALIDATE**: Run `python pipeline.py example --message "test"` and confirm logs +
   metrics
5. All 4 quality gates must pass before declaring MVP done

### Incremental Delivery

1. Setup + Foundational â†’ skeleton ready
2. User Story 1 â†’ **MVP**: pipeline executes a mode (demo-able)
3. User Story 2 â†’ `--help` discoverable (add to MVP)
4. User Story 3 â†’ mode help discoverable (add to MVP)
5. User Story 4 â†’ production-grade error handling
6. Polish â†’ full quality gate compliance + integration tests

### Parallel Team Strategy

With two developers after Phase 2:

- Developer A: US1 (core dispatch) â†’ US4 (error handling, extends dispatcher)
- Developer B: US2 (top-level help) â†’ US3 (mode help, extends ExampleMode)

---

## Notes

- `[P]` = different files, no incomplete-task dependencies â€” safe to run in parallel
- `[USn]` label maps each task to a specific user story for traceability
- Tests MUST be written and confirmed failing before implementation begins (BDD Red-Green-Refactor)
- Each story's checkpoint must be validated independently before moving to the next priority
- Commit after each completed phase or user story
- Quality gates (T041â€“T042) may surface issues that require backtracking to earlier tasks
