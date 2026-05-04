<!--
SYNC IMPACT REPORT
==================
Version change: [unset template] → 1.0.0 (MAJOR: first concrete constitution from blank template)

Principles added (all new):
  I.   SOLID Design Principles
  II.  Standard Dependencies
  III. BDD Test-First (NON-NEGOTIABLE)
  IV.  Code Quality Standards
  V.   Observability & Logging
  VI.  OpenAPI-First

Sections added:
  - Core Principles (6 principles)
  - Development Workflow
  - Quality Gates
  - Governance

Templates requiring updates:
  ✅ .specify/templates/plan-template.md — Constitution Check gates updated to reference these principles
  ✅ .specify/templates/spec-template.md — Acceptance Scenarios note updated to mandate Gherkin format
  ✅ .specify/templates/tasks-template.md — BDD feature file tasks marked mandatory (not optional)

Follow-up TODOs:
  - None; all placeholders resolved.
-->

# Market Data Web Service Constitution

## Core Principles

### I. SOLID Design Principles

Every module, class, and function in this codebase MUST conform to the SOLID principles:

- **Single Responsibility**: Each class or module has one reason to change. Services, repositories, and controllers are separate concerns and MUST NOT be merged.
- **Open/Closed**: New behaviour is added by extension (new classes, strategies, decorators), not by modifying existing stable code.
- **Liskov Substitution**: Subtypes and implementations MUST be substitutable for their abstractions without altering program correctness.
- **Interface Segregation**: Clients MUST NOT depend on interfaces they do not use. Prefer narrow, focused interfaces over broad, monolithic ones.
- **Dependency Inversion**: High-level modules MUST depend on abstractions; low-level modules implement them. Dependencies are injected, never directly instantiated inside business logic.

Violations require documented justification in the plan's Complexity Tracking table.

### II. Standard Dependencies

Industry-standard, well-maintained packages MUST be preferred over bespoke or niche alternatives.

- Before writing a utility or helper, verify no established library already solves the problem.
- All dependencies MUST be pinned to a specific version in the project's dependency manifest.
- A dependency is acceptable if it has active maintenance, community adoption, and an OSI-approved licence.
- Internal utilities that replicate standard-library or well-known package functionality are prohibited.

### III. BDD Test-First (NON-NEGOTIABLE)

All features MUST be specified as executable Gherkin scenarios before any implementation begins.

- Feature files (`.feature`) in Gherkin syntax constitute the living specification and documentation.
- Tests MUST be written first, confirmed to fail (red), then implementation written to make them pass (green).
- Each user story in the spec MUST map to at least one `.feature` file with `Given / When / Then` scenarios.
- End-to-end scenarios covering the full request/response lifecycle are MANDATORY for every API endpoint.
- Unit tests are permitted in addition to BDD scenarios but MUST NOT replace them.
- The Red-Green-Refactor cycle is strictly enforced: no implementation task begins without a failing test.

### IV. Code Quality Standards

All code MUST comply with a single, project-wide linting and static analysis configuration.

- Linter and formatter configurations are committed to the repository root and MUST NOT be overridden per-file.
- CI MUST block merges when linting or static analysis violations are detected.
- Type annotations are MANDATORY in all Python modules; `mypy` (or equivalent) runs in strict mode.
- Code reviews MUST verify linting compliance before approval; style discussions belong in automated tooling, not review comments.
- The same rules apply equally to test code and production code.

### V. Observability & Logging

Every execution MUST produce structured log output with full operational detail.

- Structured JSON log files are written for every run, capturing: timestamp, log level, component, operation, duration, and outcome.
- Log levels follow standard severity: DEBUG, INFO, WARNING, ERROR, CRITICAL.
- All API requests and responses MUST be logged at INFO level (excluding sensitive fields).
- Errors and exceptions MUST be logged at ERROR level with full stack traces.
- Log files are written to a configurable output directory; console output mirrors the log stream.
- Performance metrics (latency, throughput) MUST be emitted as structured log entries for every significant operation.

### VI. OpenAPI-First for APIs

All HTTP APIs MUST be specified and documented using the OpenAPI (Swagger) standard before implementation.

- An `openapi.yaml` (or `openapi.json`) contract file is the authoritative source of truth for every API surface.
- The OpenAPI spec MUST be written or generated first; implementation MUST conform to it.
- Interactive Swagger UI MUST be served at `/docs` (or equivalent) in all non-production environments.
- Breaking changes to the API contract MUST trigger a major version increment and MUST NOT be deployed without consumer notification.
- All request/response schemas MUST be defined as named components in the OpenAPI spec; inline anonymous schemas are prohibited.

## Development Workflow

All feature development follows this sequence:

1. **Specify**: Author the feature spec with Gherkin acceptance scenarios.
2. **Plan**: Produce an implementation plan; pass the Constitution Check gate.
3. **BDD First**: Write and commit `.feature` files and step definitions; confirm all scenarios are red.
4. **Implement**: Write production code to satisfy the failing scenarios.
5. **Quality Gate**: Linting, static analysis, and full BDD suite must be green before merge.
6. **Review**: Code review verifies SOLID compliance, dependency hygiene, logging coverage, and OpenAPI alignment.

No step may be skipped. The BDD-First step MUST produce failing tests before the Implement step begins.

## Quality Gates

The following gates block merge to the main branch:

- All Gherkin scenarios pass (end-to-end BDD suite green).
- Linting and static analysis report zero violations.
- Type checking passes with no errors.
- OpenAPI spec is present and validates with no errors.
- Log output verified to contain structured entries for the new feature.
- Constitution Check in the plan is marked passing.

## Governance

This constitution supersedes all other development practices within this project. Any practice that conflicts with these principles MUST be resolved in favour of the constitution.

**Amendment procedure**:
1. Propose the change as a pull request modifying this file.
2. State the rationale, impact on existing work, and version bump type.
3. Update all affected templates and notify active feature branches.
4. Increment the version per semantic versioning: MAJOR for removals or redefinitions, MINOR for new principles or sections, PATCH for clarifications.

All pull requests and code reviews MUST verify compliance with this constitution. Complexity violations MUST be documented in the plan's Complexity Tracking table before work begins.

**Version**: 1.0.0 | **Ratified**: 2026-05-04 | **Last Amended**: 2026-05-04
