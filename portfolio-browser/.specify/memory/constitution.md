<!--
Sync Impact Report
Version change: [TEMPLATE] → 1.0.0 (initial ratification)
Modified principles: n/a (first fill of template placeholders)
Added sections:
  - I. API-Sourced Data, No Local Business Logic
  - II. Layered API Architecture
  - III. Test-First with BDD (NON-NEGOTIABLE)
  - IV. Configuration Over Hard-Coding
  - V. Standard Libraries and SOLID Design
  - User Experience Standards (replaces template's generic Section 2)
  - Development Workflow (replaces template's generic Section 3)
  - Governance (amendment procedure, versioning policy, compliance review)
Removed sections: none
Templates requiring updates:
  - .specify/templates/plan-template.md: ✅ no changes needed (Constitution Check
    section is already generic — "[Gates determined based on constitution file]")
  - .specify/templates/spec-template.md: ✅ no changes needed (no
    constitution-specific references)
  - .specify/templates/tasks-template.md: ✅ no changes needed (no
    constitution-specific references)
  - .claude/skills/speckit-*/SKILL.md: ✅ reviewed, generic guidance, no
    agent-specific (CLAUDE-only) references requiring update
Follow-up TODOs: none
-->

# Portfolio Browser Constitution

## Core Principles

### I. API-Sourced Data, No Local Business Logic
The UI is a presentation layer only. All portfolio, transaction, pricing, and
analytical data MUST be retrieved from backing services (e.g.
`portfolio-analysis-service`, `market-data-web-service`) via their APIs — the
UI MUST NOT read source files (Excel, JSON, parquet caches) directly, nor
re-implement financial calculations (returns, PnL, weights, aggregations)
client-side. If a screen needs a derived value that no API currently exposes,
the correct fix is a new/extended API endpoint in the owning service, not a
client-side calculation. UI code MAY perform purely presentational
transforms (formatting, sorting, pagination, client-side view filtering of
already-fetched data) but MUST NOT derive new financial facts.

**Rationale**: Keeping calculations in the API layer gives a single source of
truth, lets calculation logic be unit-tested once against the domain, and
prevents the UI and API from silently drifting to different answers for the
same figure.

### II. Layered API Architecture
Within each API service, three responsibilities MUST remain in separate,
independently testable layers: (1) data access — requesting, filtering, and
caching upstream/source data; (2) calculation — deriving metrics and
aggregates from that data; (3) transport — request/response handling and
serialization. A calculation module MUST NOT perform I/O or caching, and a
data-access module MUST NOT contain financial-domain logic. Dependencies
flow one direction (transport → calculation → data access); the reverse MUST
NOT occur.

**Rationale**: This mirrors the existing `PortfolioAnalysis.py` → `MarketData.py`
→ `DataFormatting.py` → `AnalysisFuncs.py` pipeline already used in this
codebase, and keeps caching/fetching concerns from leaking into and
complicating calculation logic (and vice versa).

### III. Test-First with BDD (NON-NEGOTIABLE)
Every change MUST follow Red-Green-Refactor: a failing test is written and
reviewed before implementation begins. User-facing behaviour (API endpoints,
user journeys, drill-down interactions) MUST be captured as Gherkin
`Given/When/Then` scenarios before the corresponding code is written, and
those scenarios MUST be kept executable (e.g. via `behave`, `pytest-bdd`,
Cucumber, or the ecosystem-equivalent BDD runner) rather than left as
documentation. Lower-level unit tests supplement, but do not replace,
scenario coverage for user-visible behaviour.

**Rationale**: TDD/BDD keeps calculation logic (Principle I/II) verifiably
correct, and Gherkin scenarios double as living documentation of the drill-down
user journeys this dashboard exists to support.

### IV. Configuration Over Hard-Coding
Credentials, API base URLs, environment-specific settings, and any constant
that could plausibly change between environments or deployments (thresholds,
feature flags, cache TTLs, labels used in more than one place) MUST live in a
well-formed configuration file (e.g. `.env` + typed config loader, `config.yaml`,
`appsettings.json`) and MUST NOT be inlined as string/number literals in
source code. Configuration files MUST be validated at startup (fail fast on a
missing/malformed value) rather than failing later at point of use. Secrets
MUST NOT be committed to version control.

**Rationale**: Magic strings and inline credentials are a recurring source of
environment-specific bugs and accidental secret leakage; centralizing them
makes the system's external dependencies auditable at a glance.

### V. Standard Libraries and SOLID Design
Prefer well-established, actively maintained libraries over custom
implementations for solved problems (HTTP clients, caching, validation,
charting, state management, date/time handling). Justify any bespoke
implementation of something a standard library already solves in the PR
description. Code MUST follow SOLID principles — in particular, single
responsibility (a module/class has one reason to change) and dependency
inversion (higher-level modules depend on abstractions, not concrete
data-access or calculation details) — favoring readable, maintainable code
over clever code. Static analysis MUST run clean in CI: `ruff` and `mypy`
(strict mode where practical) for Python code, and the equivalent
linter/type-checker pairing (e.g. ESLint + TypeScript strict mode) for any
frontend/UI code.

**Rationale**: Re-inventing solved problems is a maintenance liability;
SOLID and static analysis keep a multi-layer, multi-service codebase legible
as it grows.

## User Experience Standards

The dashboard's core value proposition is letting a user explain a number —
not just see it. Every summary or aggregate figure surfaced in the UI MUST
have a drill-down or look-through path to the underlying detail that produced
it (e.g. a portfolio total MUST be traceable down to position, then
transaction, level). Navigation between related views (position ↔
transactions ↔ income ↔ performance) MUST be reachable in no more than two
interactions from any screen that references the related entity.
Interactions that trigger an API call MUST give feedback (loading state)
within 100ms and MUST NOT block the rest of the UI. Pages/views MUST remain
usable (readable, navigable, no clipped content) across common desktop and
tablet viewport widths; mobile support may be limited but MUST NOT be
broken/unusable.

**Rationale**: This is explicitly a drill-down/explainability dashboard per
project intent — responsiveness and navigability are product requirements,
not nice-to-haves, and are called out separately from general engineering
principles so they get equal weight in review.

## Development Workflow

All new behaviour starts with a Gherkin scenario (Principle III) reviewed
before implementation. Pull requests MUST include: the scenario(s) covering
the change, passing tests (unit + BDD as applicable), and a clean run of the
project's static analysis tools (Principle V). PRs that introduce a UI
element performing a calculation that belongs in an API (Principle I), or
that mix data-access and calculation code in one module (Principle II), MUST
be rejected or revised before merge. Any deviation from these principles
MUST be recorded in the relevant plan's Complexity Tracking table with a
justification, per `.specify/templates/plan-template.md`.

## Governance

This constitution supersedes other informal practices for this project.
Amendments are proposed via the `/speckit-constitution` command, which
updates this file, recomputes the version per semantic versioning (MAJOR:
backward-incompatible principle removal/redefinition; MINOR: new
principle/section or materially expanded guidance; PATCH: clarification/
wording), and propagates any required changes to
`.specify/templates/plan-template.md`, `spec-template.md`, and
`tasks-template.md`. Every `/speckit-plan` run MUST pass the Constitution
Check gate before Phase 0 research begins and again after Phase 1 design;
unresolved violations block progression unless justified in Complexity
Tracking. Reviewers are expected to check PRs against these principles
directly; this constitution is the final authority when guidance conflicts
with prior undocumented convention.

**Version**: 1.0.0 | **Ratified**: 2026-07-13 | **Last Amended**: 2026-07-13
