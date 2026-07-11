<!--
  SYNC IMPACT REPORT
  Version change: 1.0.0 → 1.0.1
  Bump type: PATCH — clarification of preferred linting/static-analysis tooling (ruff)
  Modified principles:
    - III. Type Safety & Code Quality — replaced generic "(e.g., ruff)" with explicit ruff mandate
  Added sections: N/A
  Removed sections: N/A
  Templates requiring updates:
    - .specify/templates/plan-template.md  ✅ updated — Constitution Check gate III now names ruff
    - .specify/templates/spec-template.md  ✅ no change required
    - .specify/templates/tasks-template.md ✅ no change required
  Follow-up TODOs: None
-->

# Portfolio Analysis Service Constitution

## Core Principles

### I. Test-First Development (NON-NEGOTIABLE)

TDD MUST be followed for all feature development:

- Tests MUST be written and reviewed before implementation begins.
- BDD acceptance tests MUST be expressed in Gherkin syntax (Given/When/Then) and stored
  alongside the feature spec.
- Tests MUST fail before implementation; the implementation MUST make them pass.
- The Red-Green-Refactor cycle is strictly enforced — no green test without a prior red test.
- Every feature MUST include unit tests, integration tests, and at least one BDD acceptance scenario.

**Rationale**: Writing tests against a specification before code is written validates behaviour
at the point of design, not after. Gherkin scenarios serve as living documentation that bridges
business intent and technical verification, and remain readable to non-engineers.

### II. SOLID Software Design

All code MUST adhere to the SOLID principles, applied at class, module, and service level:

- **Single Responsibility**: Each class or module MUST have exactly one reason to change.
- **Open/Closed**: Modules MUST be open for extension but closed for modification;
  new behaviour is added by extending, not by editing existing code.
- **Liskov Substitution**: Subtypes MUST be fully substitutable for their declared base types
  without altering the correctness of the program.
- **Interface Segregation**: Interfaces and protocols MUST be specific; no component MUST be
  forced to depend on methods it does not use.
- **Dependency Inversion**: High-level modules MUST NOT depend on low-level modules; both
  MUST depend on abstractions (protocols, interfaces, abstract base classes).

**Rationale**: SOLID design produces components that can be independently tested, extended, and
replaced — essential for a long-lived financial data service where requirements evolve.

### III. Type Safety & Code Quality

All code MUST meet the following quality gates before any PR is merged:

- Full type annotations MUST be present on all functions, methods, and class attributes.
- `mypy --strict` MUST pass with zero errors.
- `ruff` is the preferred linter and static analysis tool. `ruff check` MUST pass with zero
  errors; `ruff format` MUST be applied for consistent code formatting.
- Static analysis MUST be clean: no unresolved types, unreachable code, or unused imports.
- All public classes, functions, and methods MUST have docstrings documenting purpose,
  parameters, return values, and raised exceptions.
- Pydantic models (or equivalent validation library) MUST be used at all external data
  boundaries (API request/response bodies, config, external API responses).

**Rationale**: Type safety catches whole classes of bugs at analysis time rather than at runtime.
Documented code reduces onboarding friction and maintenance cost in a shared codebase.

### IV. Observability & Structured Logging

All services MUST emit structured, machine-readable telemetry:

- All log output MUST be in structured JSON format, following OpenTelemetry semantic conventions
  or an equivalent industry standard.
- Every HTTP request/response cycle MUST be logged with: correlation ID, HTTP method, path,
  response status code, and request duration.
- Business-significant events (market data fetch, cache hit/miss, portfolio computation,
  error conditions) MUST be logged at the appropriate level (INFO/WARNING/ERROR).
- A health endpoint (`GET /health`) and a readiness endpoint (`GET /ready`) MUST be exposed
  and MUST return structured JSON.
- All errors MUST include a structured payload containing: error type, message, correlation ID,
  and full stack trace (in non-production environments, stack traces MAY be suppressed for
  security).

**Rationale**: Financial services require audit trails and operational visibility. Structured logs
enable automated alerting, dashboards, and incident diagnosis without brittle log parsing.

### V. RESTful API Design with OpenAPI & HATEOAS

All HTTP APIs MUST conform to REST principles and be formally specified:

- An OpenAPI 3.x specification MUST be maintained alongside the implementation; it MUST be
  the authoritative contract for all consumers.
- Resources MUST be modelled as nouns; HTTP verbs MUST convey semantics
  (GET = read, POST = create, PUT = replace, PATCH = partial update, DELETE = remove).
- All collection and resource responses MUST include a `_links` object (HATEOAS) containing
  at minimum a `self` link, and any relevant related-resource or action links.
- API versioning MUST be explicit via a path prefix (e.g., `/v1/`).
- All error responses MUST use RFC 7807 Problem Details format
  (`Content-Type: application/problem+json`).
- The live OpenAPI specification MUST be accessible at `/openapi.json` (or `/docs` with UI).

**Rationale**: A machine-readable contract decouples API consumers from implementation details.
HATEOAS enables API evolution without breaking clients. RFC 7807 standardises error handling
across all consumers.

## Code Quality Standards

All pull requests MUST satisfy these quality gates before merge:

- **Linting**: `ruff check` MUST pass with zero errors (preferred linter); `ruff format` MUST
  be applied. Both enforced in CI.
- **Type checking**: `mypy --strict` MUST pass with zero errors.
- **BDD coverage**: All new user-facing behaviour MUST have at least one Gherkin scenario
  (Given/When/Then) that passes.
- **Unit coverage**: New business logic MUST have corresponding unit tests.
- **Documentation**: All public symbols MUST have docstrings; new or changed endpoints MUST
  appear in the OpenAPI specification.
- **No secrets**: Credentials, tokens, and keys MUST NOT appear in committed source code.
- **Dependency pinning**: All dependencies MUST be pinned to exact versions in `requirements.txt`
  or an equivalent lock file.

## Development Workflow

Feature development follows the Spec Kit workflow:

1. **Specify** (`/speckit-specify`): Capture user stories; acceptance criteria MUST be expressed
   in Gherkin format (Given/When/Then).
2. **Plan** (`/speckit-plan`): Design technical approach; the Constitution Check MUST pass
   before Phase 0 research begins, and MUST be re-verified after Phase 1 design.
3. **Tasks** (`/speckit-tasks`): Generate dependency-ordered tasks; BDD and unit test tasks
   MUST appear before their corresponding implementation tasks.
4. **Implement** (`/speckit-implement`): Execute tasks; every test MUST be written and verified
   to fail before its implementation task begins.
5. **Review**: All PRs require at least one review. The reviewer MUST verify the Constitution
   Check below is satisfied.

**PR Constitution Check** (reviewer responsibility):

- [ ] SOLID principles not violated (justify any deviation in the plan's Complexity Tracking table)
- [ ] Type annotations complete; `mypy --strict` passes; `ruff check` and `ruff format` clean
- [ ] Gherkin BDD scenarios cover all acceptance criteria
- [ ] Structured JSON logging added to new code paths
- [ ] OpenAPI specification updated for any new or changed endpoints
- [ ] RFC 7807 Problem Details used for all error responses
- [ ] HATEOAS `_links` present in new resource/collection responses

## Governance

This constitution supersedes all other development practices and guidelines.

**Amendment procedure**:
1. Author writes a rationale explaining why the change is necessary.
2. The version MUST be incremented (see below).
3. All dependent templates (`.specify/templates/`) MUST be reviewed and updated where needed.
4. The Sync Impact Report comment at the top of this file MUST be updated.

**Versioning policy** (semantic versioning):
- **MAJOR**: Removal or redefinition of a principle (backward-incompatible governance change).
- **MINOR**: New principle added, or materially expanded guidance in an existing principle.
- **PATCH**: Clarifications, wording improvements, typo fixes, non-semantic refinements.

**Compliance**: Every PR review MUST include verification of the PR Constitution Check above.
Complexity that deviates from any principle MUST be justified in the plan's Complexity Tracking
table. Unjustified deviations are grounds to block merge.

**Version**: 1.0.1 | **Ratified**: 2026-07-06 | **Last Amended**: 2026-07-06
