# Specification Quality Checklist: Fix Cash Offset Signs

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-06-10
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

- All items pass. Spec is ready for `/speckit-plan`.
- Root cause confirmed by inspection of real journal data: HL exports store buy values as
  negative and sell values as positive. The feature 004 `_make_offset` formula `value = -event.value`
  therefore inverted both signs incorrectly.
- Fix is a one-line logic change plus test fixture/CSV data corrections.
- FR-005 documents the self-healing behaviour on re-run — no manual journal correction needed.
- SC-004 provides the observable acceptance test for the re-run correction scenario.
