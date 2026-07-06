# Research: HL Action Mapping — Card Web, FPC, Commission

## Summary

No external research required. All technical decisions are resolved from the existing codebase.

---

## Decision 1: Location of new mapping logic

**Decision**: Add new reference constants to `constants.py` and extend `_map_action()` in `src/modes/consolidate_journals/parsers/hl.py`.

**Rationale**: `_map_action` is the single function responsible for reference→action classification; it is the correct and only place to add new cases. The constitution prohibits magic strings, so new reference literals must be extracted to `constants.py`. No new module or class is needed — the extension is additive (Open/Closed principle satisfied by adding branches, not modifying existing ones).

**Alternatives considered**:
- Adding new references to `HL_DEPOSIT_REFERENCES` frozenset: rejected because `HL_DEPOSIT_REFERENCES` is compared case-sensitively (`ref in HL_DEPOSIT_REFERENCES`), and the spec requires case-insensitive matching. Changing the semantics of `HL_DEPOSIT_REFERENCES` to uppercase storage would require updating all callers.
- A lookup table / dict approach: unnecessary complexity for 3 new entries.

---

## Decision 2: Case-insensitivity implementation

**Decision**: Store new deposit aliases as uppercase strings in a new `HL_DEPOSIT_REFERENCE_ALIASES` frozenset; compare with `ref.upper() in HL_DEPOSIT_REFERENCE_ALIASES`. Store commission and existing income references as uppercase in a new `HL_INCOME_REFERENCES` frozenset; replace the existing hardcoded tuple `("INTEREST", "RDP CR")` in `_map_action` with this constant.

**Rationale**: The existing pattern for `MANAGE FEE`, `INTEREST`, and `RDP CR` already uses `ref.upper()`. This approach is consistent, avoids magic strings (constitution gate II), and simultaneously fixes a minor constitution violation where `"INTEREST"` and `"RDP CR"` are currently hardcoded strings inside `_map_action`.

**Alternatives considered**:
- `ref.lower() ==` comparisons (as used for `"contrib"`): inconsistent with the uppercase comparison pattern used for all other non-pattern references in the same function.
- `re.compile(r"^card web$", re.IGNORECASE)`: overkill for a fixed-string comparison; regex introduces unnecessary overhead and complexity.

---

## Decision 3: Sub-account assignment for new action types

**Decision**: No code change required for sub-account assignment. The existing rule in `_parse_row` — "if `str(action) in CASH_ACTION_TYPES`, sub_account = `CASH_SUB_ACCOUNT`" — already covers both `deposit` and `income`, so "Card Web", "FPC", and "Commission" rows will automatically receive the "Cash" sub-account once mapped to the correct action type.

**Rationale**: `CASH_ACTION_TYPES = frozenset({"deposit", "fee", "income"})` already includes all three relevant types. This is a zero-change inference.

---

## Decision 4: Test fixture approach

**Decision**: Add three new minimal CSV fixture files to `tests/data/consolidate_journals/`:
- `valid_hl_card_web.csv` — one "Card Web" row + one "card web" (lowercase) row
- `valid_hl_fpc.csv` — one "FPC" row + one "fpc" row
- `valid_hl_commission.csv` — one "Commission" row + one "COMMISSION" row

**Rationale**: The existing test pattern uses per-scenario fixture CSV files (e.g., `valid_hl_contrib.csv`, `valid_hl_fee_interest.csv`). Two rows per fixture covers both canonical casing and the required case-insensitivity.

**Alternatives considered**: A single combined CSV with all new reference types — makes individual test failures harder to isolate. Inline test data without fixture files — inconsistent with the established test pattern.

---

## Decision 5: BDD coverage

**Decision**: Add new scenarios to `tests/features/consolidate_journals.feature`. Three scenarios: one for "Card Web"→deposit, one for "FPC"→deposit, one for "Commission"→income. No new feature file needed.

**Rationale**: Action mapping scenarios already live in `consolidate_journals.feature`. Adding to the existing file is consistent and avoids fragmentation.
