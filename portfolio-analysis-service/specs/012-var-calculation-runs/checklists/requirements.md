# Specification Quality Checklist: Historical-Simulation VaR Calculation Runs

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-10-03
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

- Endpoint paths, HTTP status codes, the identifier-mapping field names, the CSV/JSON store and the
  two script names appear in the spec on purpose. The user asked for them explicitly, they form the
  external contract other features and scripts depend on, and earlier specs in this repo follow the
  same convention. No language, framework or library is named.
- Formulas (VaR rank, ES, rescale) are part of the required behaviour, not implementation choices.
  The reference cases were checked by hand: losses 1–520 give VaR 494/507/515 and ES
  507.5/514/(2590 + 103)/5.2.
- No clarification markers were needed. Open questions in the proposal's §12 were resolved with its
  recommended defaults and recorded under Assumptions (risky-value denominators, sparse threshold 80%,
  store under the account directory, CSV, quality thresholds).
- Revised 2026-10-03 after `/speckit-analyze`:
  - FR-004 now counts the return source actually used (own or proxy) as observed.
  - FR-010 measures sparseness only from an instrument's first price.
  - FR-020 defines "skipped".
  - New FR-033 adds correlation IDs to this feature's errors and runs (constitution Principle IV).
- Dependency: market-data-web-service `009-observed-price-history` must be delivered before this
  feature can run against real data (FR-026 fails closed until then).
