# Specification Quality Checklist: Projection Page (replaces Income)

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-22
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- Items marked incomplete require spec updates before `/speckit-clarify` or `/speckit-plan`

### Validation history

**Iteration 1 (2026-09-22)** — all items pass on first review. Every ambiguity in the source
request had a reasonable, low-impact default available (documented in Assumptions), so zero
`[NEEDS CLARIFICATION]` markers were needed — unlike 008 and 021, which each carried one.

**Post-`/speckit-clarify` (2026-09-22)** — three of the four judgment calls below were put to the
user directly rather than left as unconfirmed assumptions. Two confirmed the original draft
(zero-returns-selected behaviour; start date as a visible control). One reversed it: FR-014 now
requires an inline validation message on a rejected projection date, not a silent revert. All
three are recorded in the spec's own Clarifications section; still pass all 16 checklist items
after the update.

### Decisions worth revisiting in `/speckit-clarify`

- **The four preset horizons are counted from the current start date, not always from today** — a
  direct consequence of the start date being movable (confirmed by clarification); flagged because
  it is easy to misread as "1Y always means one year from today."
- **The new backend capability's own contract (its inputs' exact validation rules, its response
  shape) is deliberately left undetailed here** (FR-018 states only the outcome it must produce).
  This mirrors how 021 depended on 008: the capability is a documented prerequisite, to be spec'd
  and planned on its own terms as a separate effort, most naturally in `portfolio-analysis-service`.
