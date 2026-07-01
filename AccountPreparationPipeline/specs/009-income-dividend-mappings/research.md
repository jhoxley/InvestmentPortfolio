# Research: Income Dividend Action Mappings

**Branch**: `009-income-dividend-mappings` | **Date**: 2026-06-18

## Decision 1: New ActionType value vs. reusing INCOME

**Decision**: Add `ActionType.DIVIDEND = "dividend"` as a distinct enum value; do not reuse `INCOME`.

**Rationale**: Dividends and income are distinct financial concepts in the ledger. `INCOME` (mapped from `RDP CR`, `INTEREST`, `COMMISSION`) represents platform/product income events that HL always assigns to cash. `DIVIDEND` represents investment return events tied to a specific holding — their sub-account carries the holding name so downstream ledger steps and analysis joins can attribute the income back to the correct position. Collapsing both into `INCOME` would lose the holding-level linkage and force consumers to re-parse descriptions that are already being cleaned here.

**Alternatives considered**:
- Reuse `INCOME` with description-based sub-account: ruled out because `INCOME` events currently always resolve to `CASH_SUB_ACCOUNT` (enforced by `CASH_ACTION_TYPES`); changing that rule would silently break Commission/INTEREST/RDP CR sub-accounts.
- Add `DIVIDEND` to `CASH_ACTION_TYPES`: ruled out for the same reason — dividend sub-accounts must carry the holding name.

---

## Decision 2: Suffix stripping mechanism — static map + dedicated regex vs. extending SUB_ACCOUNT_STRIP_SUFFIXES

**Decision**: Introduce `HL_DIVIDEND_SUFFIX_MAP` (a `dict[str, tuple[str, ...]]` keyed by uppercase reference) and `RE_LOYALTYU_SUFFIX` (a compiled regex), handled in a new pure helper `_strip_dividend_suffix(reference, description)` called from an `elif action is ActionType.DIVIDEND` branch in `_parse_row()`.

**Rationale**: The existing `SUB_ACCOUNT_STRIP_SUFFIXES` mechanism applies the same suffixes to *every* non-cash, non-dividend row; adding dividend-specific suffixes there would risk stripping them from descriptions that legitimately end with those phrases in other contexts. The LOYALTYU suffix is inherently dynamic (month-year digits) and cannot be expressed as a `str.removesuffix()` call at all — a compiled regex is the right tool. Centralising all four reference-specific strip rules in a single helper satisfies Single Responsibility and keeps `_parse_row()` free of conditional string-manipulation logic.

**Alternatives considered**:
- Extend `SUB_ACCOUNT_STRIP_SUFFIXES` with static strings: ruled out because it would incorrectly strip " Dividend Payment" from any non-dividend row whose description happens to end with that phrase, and cannot handle LOYALTYU's dynamic suffix.
- Per-reference if/elif in `_parse_row()`: ruled out — disperses string-manipulation policy into the row-parsing function, violating Single Responsibility.

---

## Decision 3: Reference matching strategy — case-insensitive via .upper() vs. exact case match

**Decision**: Use `ref.upper() in HL_DIVIDEND_REFERENCES` (with `HL_DIVIDEND_REFERENCES` stored as uppercase), consistent with how `HL_INCOME_REFERENCES`, `HL_DEPOSIT_REFERENCE_ALIASES`, and `MANAGE FEE` are already matched in `_map_action()`.

**Rationale**: Real data shows these references arrive in uppercase from HL exports, but defensive case-insensitive matching is the established project pattern. All comparisons in `_map_action()` already normalise to uppercase; deviating to case-sensitive matching for the new references would be an inconsistency that could cause silent failures if HL ever exports with different casing.

**Alternatives considered**:
- Case-sensitive exact match: ruled out as inconsistent with project convention and fragile against future HL export format changes.

---

## Decision 4: Suffix map key format — uppercase reference strings

**Decision**: `HL_DIVIDEND_SUFFIX_MAP` keys are uppercase strings (e.g., `"ST DIV"`, `"OVR CR"`). The `_strip_dividend_suffix()` helper accesses the map via `reference.strip().upper()`.

**Rationale**: Consistent with `HL_INCOME_REFERENCES` and `HL_DEPOSIT_REFERENCE_ALIASES` which are also stored uppercase. A single normalisation point prevents case-mismatch bugs if the raw reference arrives with unexpected casing.

---

## Decision 5: Fallback when suffix stripping leaves an empty string

**Decision**: `_strip_dividend_suffix()` returns `result or description or reference` — first the stripped result, then the full unstripped description, then the reference itself.

**Rationale**: The spec requires (FR-009) that an empty sub-account is never stored. The fallback chain ensures graceful degradation without raising an exception: if an unexpected description format causes the stripped result to be empty, the full description is preserved as a meaningful sub-account value. If description is also empty, the reference string is used as a last resort.

---

## Confirmation: all references in real income account files are covered

Scanned all 8 HL ISA Income Account fragment CSV files. Unique reference values found:

| Reference  | Count | Current handling          | After this feature |
|------------|-------|---------------------------|--------------------|
| ST DIV     | 4     | Unmapped → dropped        | `dividend`         |
| OVR CR     | 4     | Unmapped → dropped        | `dividend`         |
| UTC CR     | 2     | Unmapped → dropped        | `dividend`         |
| LOYALTYU   | 1     | Unmapped → dropped        | `dividend`         |
| MANAGE FEE | 8     | `fee` ✓                   | unchanged          |
| Transfer   | 8     | `deposit` ✓               | unchanged          |

After this feature, zero unmapped references remain in the income account history.
