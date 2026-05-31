# Feature Specification: Pipeline Entrypoint & Mode Dispatch

**Feature Branch**: `001-pipeline-entrypoint`
**Created**: 2026-05-31
**Status**: Draft
**Input**: User description: "Create a Python script that takes a set of command-line arguments and
represents the main account preparation pipeline. It should have a 'mode' command line argument
that indicates which functionality to execute and passes through other command line arguments to
this as parameters. It should verify the 'mode' is a supported one and offer a 'help' option to
discover legal permutations. Each mode executed should delegate to a separate module but follow a
common format and interface, exposing the validation and required arguments and supporting the
'help' option to discover what parameters are allowed (and a human readable explanation of each).
The script should have structured logging and metrics output. This feature sets the groundwork for
adding modes in future."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run a supported pipeline mode (Priority: P1)

A developer invokes the pipeline with a mode name and any mode-specific arguments. The pipeline
validates the mode exists, delegates to the appropriate module, and produces structured log output
and a metrics summary at the end of the run.

**Why this priority**: This is the core value proposition — without the ability to execute a mode,
the pipeline delivers no value. Everything else supports or extends this story.

**Independent Test**: Run the pipeline with a known valid mode and a valid set of arguments.
Confirm the mode executes, logs appear, and a metrics summary is printed. Delivers: a working
end-to-end execution path.

**Acceptance Scenarios**:

1. **Given** the pipeline is invoked with a valid `mode` argument and valid mode-specific
   arguments, **When** it executes, **Then** the mode's logic runs to completion, structured logs
   (with timestamps and a correlation ID) are emitted, and a metrics summary (mode name, duration,
   exit status) is printed.
2. **Given** the pipeline is invoked with a valid `mode` argument but missing required
   mode-specific arguments, **When** it executes, **Then** the pipeline exits with a non-zero
   status and prints a clear error message listing the missing arguments — no stack trace is shown.
3. **Given** the pipeline is invoked with a valid `mode` argument and extraneous/unrecognised
   arguments, **When** it executes, **Then** the pipeline rejects the call with an informative
   error message identifying the unexpected arguments.

---

### User Story 2 - Discover available modes (Priority: P2)

A developer runs the pipeline with a `--help` flag (and no mode) and receives a formatted list of
all registered modes with a one-line human-readable description for each.

**Why this priority**: Without this, new developers cannot discover what the pipeline can do.
Essential for usability and self-documenting operation, but the pipeline still works without it
once modes are known.

**Independent Test**: Run `pipeline --help` (no mode). Confirm output lists at least the pipeline
name, a usage summary, and each registered mode with its description. Delivers: discoverability
for any operator new to the tool.

**Acceptance Scenarios**:

1. **Given** the pipeline is invoked with no arguments, **When** it executes, **Then** it prints a
   usage summary and a list of all supported modes with brief descriptions, then exits with status
   0.
2. **Given** the pipeline is invoked with `--help` and no mode, **When** it executes, **Then** it
   produces the same output as invoking with no arguments and exits with status 0.
3. **Given** one or more modes are registered, **When** help is displayed, **Then** every
   registered mode appears exactly once with a non-empty description.

---

### User Story 3 - Discover mode-specific arguments (Priority: P3)

A developer runs the pipeline with a valid mode name and `--help` and receives a formatted list of
all accepted arguments for that mode, including each argument's name, whether it is required, and a
human-readable explanation.

**Why this priority**: Enables self-service use of any mode without consulting external
documentation. Dependent on US1 (mode dispatch works) but independently demonstrable.

**Independent Test**: Run `pipeline <mode> --help`. Confirm output lists the mode's accepted
arguments, marks required vs optional, and provides a description for each. Delivers: inline
documentation per mode.

**Acceptance Scenarios**:

1. **Given** the pipeline is invoked with a valid mode and `--help`, **When** it executes, **Then**
   it prints the mode name, a description, and a table/list of accepted arguments — each with its
   name, requirement status, and a human-readable explanation — then exits with status 0.
2. **Given** a mode with no optional arguments is invoked with `--help`, **When** it executes,
   **Then** the output clearly states that only required arguments exist (no missing sections or
   empty lists).

---

### User Story 4 - Handle an unsupported mode gracefully (Priority: P4)

A developer mistypes a mode name or provides a mode that has not been registered. The pipeline
exits cleanly with a clear error message that lists the valid modes — no unhandled exception or
stack trace.

**Why this priority**: Defensive error handling protects against user error and is important for a
professional tool, but is an enhancement layer on top of the core dispatch story (P1).

**Independent Test**: Run the pipeline with a mode name that does not exist. Confirm a clean error
message is printed, valid modes are listed, and the exit code is non-zero. Delivers: a
professional failure experience.

**Acceptance Scenarios**:

1. **Given** the pipeline is invoked with an unrecognised mode name, **When** it executes, **Then**
   it exits with a non-zero status, prints a message identifying the unrecognised mode, and lists
   all valid mode names.
2. **Given** the pipeline exits due to an unrecognised mode, **When** the output is inspected,
   **Then** no Python stack trace or internal exception detail is visible to the user.

---

### Edge Cases

- What happens when the pipeline is invoked with no arguments at all? → Should display top-level
  help (same as `--help`) and exit with status 0.
- What happens when a mode module fails to load at startup (e.g., import error)? → The pipeline
  should detect this at startup and report which mode failed to register, preventing a confusing
  runtime error later.
- What happens when two modes attempt to register under the same name? → The second registration
  must be rejected or logged as a warning; the registry must remain consistent.
- What happens when a mode raises an unhandled exception during execution? → The pipeline catches
  it, logs the error with the correlation ID, prints a clean user-facing message, and exits with a
  non-zero status.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The pipeline MUST accept a positional `mode` argument as the first argument,
  identifying which operation to perform.
- **FR-002**: The pipeline MUST validate the provided mode against the registry of supported modes
  before execution and exit with a non-zero status and an informative message if the mode is not
  found.
- **FR-003**: The pipeline MUST support a `--help` flag at the top level (with no mode argument)
  that outputs a formatted list of all available modes and their one-line descriptions.
- **FR-004**: Each mode MUST be implemented in a dedicated module that conforms to a documented
  common interface specifying at minimum: mode name, mode description, argument schema, and an
  execute function.
- **FR-005**: Each mode MUST declare its accepted arguments (names, types, whether required, and
  human-readable descriptions) through the common interface.
- **FR-006**: The pipeline MUST support a `--help` flag for a specific mode, which displays the
  mode name, description, and its full argument list with human-readable explanations, then exits
  with status 0.
- **FR-007**: The pipeline MUST pass all remaining arguments (after `mode` and pipeline-level
  flags) through to the selected mode's execute function.
- **FR-008**: The pipeline MUST emit structured log entries (with ISO 8601 timestamp and
  correlation ID) at key milestones: startup, mode selection, execution start, execution
  completion, and any error conditions.
- **FR-009**: The pipeline MUST output an execution metrics summary at the end of every run,
  including: mode name, start time, end time, total duration, and exit status.
- **FR-010**: The mode registry MUST be extensible such that adding a new mode requires only
  creating a new conformant module and registering it — zero changes to the dispatcher are
  required.
- **FR-011**: The pipeline MUST exit with status 0 on success and a non-zero status on any
  failure, including unrecognised mode, validation failure, or execution error.
- **FR-012**: Unhandled exceptions within a mode's execution MUST be caught at the pipeline level,
  logged with the correlation ID, and presented as a clean error message — no raw stack traces
  exposed to the user.

### Key Entities

- **Mode Registry**: The authoritative mapping of mode names to their module implementations and
  metadata. Populated at startup; consulted for every dispatch and help request.
- **Mode Interface (Contract)**: The formal contract all mode modules must satisfy — defines the
  required attributes and callable signatures each module must expose.
- **Argument Schema**: The structured description of a mode's accepted arguments — name,
  type/format, required flag, and human-readable description — used for validation and help output.
- **Execution Context**: A value object created at startup containing the correlation ID, start
  timestamp, mode name, and any pipeline-level configuration. Passed to the mode on execution.
- **Metrics Record**: A structured record capturing timing (start/end/duration), mode, and outcome.
  Emitted to the log at the end of every run.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer can discover all available modes and their purpose using a single command
  invocation, without reading source code or external documentation.
- **SC-002**: A developer can discover all accepted arguments for any registered mode using a single
  command invocation.
- **SC-003**: Running an unrecognised mode name produces a clean error (no stack trace) and lists
  valid alternatives — response time under 1 second.
- **SC-004**: Registering a new mode requires creating exactly one new file; zero changes to the
  core dispatcher are required to make it available.
- **SC-005**: Every execution (success or failure) produces at least one structured log entry
  containing timestamp, correlation ID, mode name, and outcome.
- **SC-006**: Every execution produces a metrics summary including mode name, duration, and exit
  status, output to the log.
- **SC-007**: All test scenarios (BDD Gherkin + unit) pass, type checking reports zero errors, and
  linting reports zero violations before the feature is considered complete.

## Assumptions

- The pipeline is operated by developers and operators from a command line; no GUI or web interface
  is in scope for this feature.
- The initial delivery of this feature ships with zero concrete mode implementations beyond a
  placeholder/example mode used for testing; all real modes are added in subsequent iterations.
- Mode modules are discovered via an explicit registration mechanism (not dynamic filesystem
  scanning), making the set of available modes deterministic and auditable.
- Modes execute synchronously; concurrent or parallel mode execution is out of scope for this
  feature.
- Metrics output is written to the structured log (not sent to an external metrics system); a
  future feature may add export to an external sink.
- The pipeline is invoked from an activated virtual environment; dependency management is handled
  externally.
- All log output goes to stderr; metrics summary goes to stdout (or both to stdout — the exact
  stream is a detail for the plan phase, not the spec).
