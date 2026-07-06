# Tasks: HL Lodgement Action Mapping

**Input**: Design documents from `specs/012-hl-lodgement-action/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓

**Tests**: Tests are MANDATORY per the project constitution. Every user story includes Gherkin
BDD feature file scenarios (`tests/features/`) and `pytest` unit tests (`tests/unit/`). Tests
MUST be written and confirmed failing BEFORE implementation begins (Red-Green-Refactor).

**Organization**: Single user story. Tasks proceed Setup → Foundational → US1 tests → Red
confirmation → Implementation → Green confirmation → Polish.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to
- Exact file paths included in all task descriptions

---

## Phase 1: Setup

**Purpose**: Record baseline and confirm existing tests are green before any changes.

- [X] T001 Run `.venv/Scripts/python -m pytest tests/ -q --tb=no` and record the baseline
  passing count for comparison at T014.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Add the `LODGEMENT` enum value and named constants so test files can import them
without `ImportError` or `AttributeError`. Both tasks touch different files and are parallel.

**⚠️ CRITICAL**: Tests in Phase 3 import `ActionType.LODGEMENT` and `RE_LODGEMENT`. These
must exist before test files are written.

- [X] T002 [P] Add `LODGEMENT = "lodgement"` to the `ActionType` StrEnum in
  `src/modes/consolidate_journals/schema.py`. Insert it after the `DIVIDEND` line to preserve
  logical ordering (all real transaction types before synthetic types). Full file after edit:
  ```python
  class ActionType(StrEnum):
      BUY = "buy"
      SELL = "sell"
      DEPOSIT = "deposit"
      INCOME = "income"
      FEE = "fee"
      TRADING = "trading"  # Synthetic cash offset for buy/sell trades
      DIVIDEND = "dividend"
      LODGEMENT = "lodgement"
  ```

- [X] T003 [P] Add two new named constants to `src/modes/consolidate_journals/constants.py`,
  immediately after the `RE_SELL` line (line 41 in the current file):
  ```python
  RE_LODGEMENT: re.Pattern[str] = re.compile(r"^L\d+$")
  LODGEMENT_DESCRIPTION_PREFIX: str = "Lodgement "
  ```
  This task touches `constants.py` only. Import additions to `parsers/hl.py` are handled
  in T009 (first Phase 3 edit to that file).

**Checkpoint**: `python -c "from src.modes.consolidate_journals.schema import ActionType;
print(ActionType.LODGEMENT)"` prints `lodgement` without error.

---

## Phase 3: User Story 1 — HL Lodgement Rows Correctly Classified (Priority: P1) 🎯 MVP

**Goal**: `consolidate_journals` recognises L+digits references as `lodgement` action and
strips the `"Lodgement "` prefix from the description to derive the sub-account. No existing
action mappings are affected.

**Independent Test**: Run `consolidate_journals` against `tests/data/consolidate_journals/
valid_hl_lodgement.csv`. Verify exit code 0, 2 events in journal, both with `action = lodgement`,
`sub_account` values = `"Barclays plc Ordinary 25p"` and
`"iShares II plc USD TIPS UCITS ETF USD (Acc)"`, no parse errors.

### Tests for User Story 1 ⚠️ (write FIRST — confirm they FAIL before implementing)

- [X] T004 [P] [US1] Create two CSV test fixtures in `tests/data/consolidate_journals/`:

  **Fixture 1** — `valid_hl_lodgement.csv` (2 lodgement rows):
  ```
  Portfolio Summary,,,,,,
  Client Name:,Test Client,,,,,,
  Client Number:,0000000,,,,,,
  Valuation as at,01/01/2024 00:00,,,,,,
  ,,,,,,
  Trade date,Settle date,Reference,Description,Unit cost (p),Quantity,Value (£)
  12/07/2018,12/07/2018,L003538235,Lodgement Barclays plc Ordinary 25p,188.38,1221,-2288.89
  12/07/2018,12/07/2018,L003538236,Lodgement iShares II plc USD TIPS UCITS ETF USD (Acc),15552,1,-155.48
  ```

  **Fixture 2** — `valid_hl_mixed.csv` (1 buy + 1 sell + 1 deposit + 1 lodgement row):
  Use the same preamble header, then 4 data rows with references B000001 (buy), S000001 (sell),
  a reference from `HL_DEPOSIT_REFERENCES` (e.g. `HL_SIPP`), and L003538235 (lodgement). Choose
  values and quantities consistent with what the parser expects for each action type. The exact
  values don't matter; the test only checks total row count = 4.

  The preamble rows ensure the parser's header-detection logic (which scans for `Trade date /
  Settle date`) is exercised correctly.

- [X] T005 [P] [US1] Add new test class `TestLodgementActionMapping` to
  `tests/unit/consolidate_journals/parsers/test_hl_parser.py`. Test via `_map_action` and
  `HLFragmentParser` — there is no `_strip_lodgement_prefix` helper; the stripping is inline in
  `_parse_row()`. Required tests:
  - `test_l_digits_reference_maps_to_lodgement` — `_map_action("L003538235", "Lodgement Barclays plc Ordinary 25p")` returns `ActionType.LODGEMENT`
  - `test_l_digits_short_reference_maps_to_lodgement` — `_map_action("L1", "Lodgement Fund A")` returns `ActionType.LODGEMENT`
  - `test_l_non_digit_suffix_not_lodgement` — `_map_action("LOYALTYU", "Barclays 01 2024 Gross Loyalty")` does NOT return `ActionType.LODGEMENT` (returns `ActionType.DIVIDEND`)
  - `test_l_with_dash_not_lodgement` — `_map_action("L-001", "something")` raises `ValueError` (no digit-only match)
  - `test_lodgement_sub_account_strips_prefix` — parser produces event with `sub_account = "Barclays plc Ordinary 25p"` (not `"Lodgement Barclays plc Ordinary 25p"`)
  - `test_lodgement_sub_account_strips_prefix_second_row` — `sub_account = "iShares II plc USD TIPS UCITS ETF USD (Acc)"`
  - `test_lodgement_event_count` — parsing `valid_hl_lodgement.csv` produces 2 events, 0 errors
  - `test_lodgement_action_type` — both events have `action == ActionType.LODGEMENT`
  - `test_lodgement_value_stored_as_is` — first event `value == Decimal("-2288.89")`
  - `test_lodgement_quantity` — first event `quantity == Decimal("1221")`
  - `test_lodgement_empty_description_falls_back_to_reference` — parse a synthetic row where
    description is exactly `"Lodgement "` (trailing space only); verify `sub_account` equals the
    reference value (FR-004). Construct the row inline without a CSV fixture:
    ```python
    result = _parse_row(reference="L999", description="Lodgement ", ...)
    assert result.sub_account == "L999"
    ```
  - `test_lodgement_mixed_total_event_count` — parse `valid_hl_lodgement.csv` alongside
    existing buy/sell/deposit fixture rows (or create a 4-row inline CSV in `tmp_path` containing
    one B-reference buy, one S-reference sell, one deposit, and one L-reference lodgement row);
    verify total event count = 4 and each action type is present exactly once (SC-003 + acceptance
    scenario 3).

  The `HLFragmentParser` tests (items 5-10, 12) use `DATA_DIR / "valid_hl_lodgement.csv"`.
  The `_map_action` tests (items 1-4) call the function directly.
  Items 11-12 use inline row construction or a `tmp_path` CSV.

- [X] T006 [P] [US1] Add the following scenarios to `tests/features/consolidate_journals.feature`
  (append after the last existing scenario, preserving the existing file content exactly):
  ```gherkin
  Scenario: Maps L-reference to lodgement action
    Given a valid HL CSV file with lodgement rows
    And no existing consolidated journal
    When I run consolidate_journals with method HL and account "Test ISA"
    Then the exit code is 0
    And the journal contains a row with action "lodgement"

  Scenario: Lodgement sub-account strips Lodgement prefix from description
    Given a valid HL CSV file with lodgement rows
    And no existing consolidated journal
    When I run consolidate_journals with method HL and account "Test ISA"
    Then the exit code is 0
    And the journal contains a row with sub_account "Barclays plc Ordinary 25p"

  Scenario: Mixed buy sell deposit and lodgement rows all correctly classified
    Given a valid HL CSV file with mixed buy sell deposit and lodgement rows
    And no existing consolidated journal
    When I run consolidate_journals with method HL and account "Test ISA"
    Then the exit code is 0
    And the journal contains 4 rows
  ```
  The third scenario requires a new `valid_hl_mixed.csv` fixture in
  `tests/data/consolidate_journals/` with one B-reference buy, one S-reference sell, one deposit
  reference, and one L-reference lodgement row. Add this fixture alongside `valid_hl_lodgement.csv`
  in T004 (or as a sub-task of T004).

- [X] T007 [US1] Add the following to `tests/features/steps/consolidate_journals_steps.py`:
  1. **First**: Verify that a `@then` step matching
     `'the journal contains a row with action "{action}"'` already exists. If it does NOT exist,
     add it before writing the new scenario bindings:
     ```python
     @then(parsers.parse('the journal contains a row with action "{action}"'))
     def check_action_present(state: dict, action: str) -> None:
         df = pd.read_excel(state["journal_path"], engine="openpyxl")
         assert action in df["action"].values, (
             f"action '{action}' not found. Values: {df['action'].tolist()}"
         )
     ```
  2. Three `@scenario` bindings (after the existing `@scenario` list):
     ```python
     @scenario(FEATURE_FILE, "Maps L-reference to lodgement action")
     def test_maps_lodgement() -> None:
         pass

     @scenario(FEATURE_FILE, "Lodgement sub-account strips Lodgement prefix from description")
     def test_lodgement_subaccount() -> None:
         pass

     @scenario(FEATURE_FILE, "Mixed buy sell deposit and lodgement rows all correctly classified")
     def test_lodgement_mixed_types() -> None:
         pass
     ```
  3. Two new `@given` steps (in the `# ── Given steps` section, after the existing `@given` steps):
     ```python
     @given("a valid HL CSV file with lodgement rows", target_fixture="state")
     def state_lodgement_dir(tmp_path: Path) -> dict:
         frags_dir = tmp_path / "frags"
         frags_dir.mkdir()
         shutil.copy(DATA_DIR / "valid_hl_lodgement.csv", frags_dir / "valid_hl_lodgement.csv")
         return {"tmp_path": tmp_path, "frags_dir": frags_dir}

     @given("a valid HL CSV file with mixed buy sell deposit and lodgement rows", target_fixture="state")
     def state_mixed_dir(tmp_path: Path) -> dict:
         frags_dir = tmp_path / "frags"
         frags_dir.mkdir()
         shutil.copy(DATA_DIR / "valid_hl_mixed.csv", frags_dir / "valid_hl_mixed.csv")
         return {"tmp_path": tmp_path, "frags_dir": frags_dir}
     ```
  4. Two new `@then` steps (in the `# ── Then steps` section):
     ```python
     @then(parsers.parse('the journal contains a row with sub_account "{sub_account}"'))
     def check_sub_account_present(state: dict, sub_account: str) -> None:
         df = pd.read_excel(state["journal_path"], engine="openpyxl")
         assert sub_account in df["sub_account"].values, (
             f"sub_account '{sub_account}' not found. Values: {df['sub_account'].tolist()}"
         )

     @then(parsers.parse("the journal contains {count:d} rows"))
     def check_row_count(state: dict, count: int) -> None:
         df = pd.read_excel(state["journal_path"], engine="openpyxl")
         assert len(df) == count, f"Expected {count} rows, got {len(df)}"
     ```

### Confirm tests FAIL (Red phase)

- [X] T008 [US1] Run:
  ```
  .venv/Scripts/python -m pytest tests/unit/consolidate_journals/parsers/test_hl_parser.py::TestLodgementActionMapping tests/features/ -v --tb=short
  ```
  Expected: All `TestLodgementActionMapping` tests fail (either `AttributeError` on
  `ActionType.LODGEMENT` if Phase 2 not done, or `ValueError` from `_map_action` if Phase 2 is
  done but implementation not yet written). BDD scenarios for lodgement fail likewise.
  Record the failure count. If any lodgement test unexpectedly passes, stop and investigate.

### Implementation for User Story 1

- [X] T009 [US1] Update `src/modes/consolidate_journals/parsers/hl.py` — this is the first
  edit to this file. Do both changes in a single edit pass:
  1. Extend the existing import from `src.modes.consolidate_journals.constants` to include
     `RE_LODGEMENT` and `LODGEMENT_DESCRIPTION_PREFIX`.
  2. In `_map_action()`, insert the following check immediately after the `if RE_SELL.match(ref):`
     block and before the `if ref in HL_DEPOSIT_REFERENCES` check:
     ```python
     if RE_LODGEMENT.match(ref):
         return ActionType.LODGEMENT
     ```

- [X] T010 [US1] Update `_parse_row()` in `src/modes/consolidate_journals/parsers/hl.py`
  (continuing from T009 which already added the required imports). In the sub-account derivation
  block (the `if str(action) in CASH_ACTION_TYPES:` / `elif action is ActionType.DIVIDEND:` /
  `else:` chain), insert a new `elif` branch for lodgement between the DIVIDEND branch and the
  `else` branch:
  ```python
  elif action is ActionType.LODGEMENT:
      stripped = description.removeprefix(LODGEMENT_DESCRIPTION_PREFIX).strip()
      sub_account = stripped if stripped else (description or reference)
  ```

### Confirm tests PASS (Green phase)

- [X] T011 [US1] Run:
  ```
  .venv/Scripts/python -m pytest tests/unit/consolidate_journals/parsers/test_hl_parser.py::TestLodgementActionMapping tests/features/ -v
  ```
  All `TestLodgementActionMapping` tests (12 tests) and all three new BDD scenarios must pass.
  Existing tests must also pass (check with `tests/unit/consolidate_journals/` and
  `tests/features/` in the same run). Record pass count.

**Checkpoint**: US1 complete. `consolidate_journals` correctly maps L+digits references to
`lodgement` action and derives sub-account from description prefix. Zero regressions.

---

## Phase 4: Polish & Cross-Cutting Concerns

**Purpose**: Mandatory quality gates per project constitution.

- [X] T012 [P] Run `mypy --strict src/` — zero errors required (Constitution gate III).
  Pay attention to any new type annotations in `schema.py`, `constants.py`, and `parsers/hl.py`.

- [X] T013 [P] Run `ruff check .` and `ruff format --check .` — zero violations required
  (Constitution gate IV). Fix any E501 line-length or import-sort (I001) violations introduced.

- [X] T014 Run full test suite:
  ```
  .venv/Scripts/python -m pytest tests/ -q
  ```
  All tests must pass. New count must be ≥ baseline (T001) + 12 unit tests (T005) + 3 BDD
  scenarios (T006). Confirm zero regressions in existing `consolidate_journals`,
  `create_ledger`, and `create_capital_ledger` suites.

- [X] T015 Verify no `print()` statements in modified production files (`schema.py`,
  `constants.py`, `parsers/hl.py`) and confirm the existing `_logger.debug("HL parse complete",
  ...)` call in `HLFragmentParser.parse()` continues to cover all rows including lodgement rows
  (no additional log sites needed — logging is inherited from the existing parse loop).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — run T001 immediately
- **Foundational (Phase 2)**: Depends on Phase 1; T002 and T003 are parallel (different files)
- **US1 (Phase 3)**: Depends on Phase 2 (T002, T003 must be done so tests can import the new
  constants); T004, T005, T006 can run in parallel; T007 depends on T006 (binds scenarios);
  T008 confirms Red; T009 then T010 implement sequentially (both edit `hl.py`); T011 confirms Green
- **Polish (Phase 4)**: Depends on Phase 3 complete

### Within User Story 1

1. Write fixture + tests (T004, T005, T006 parallel) → add step bindings (T007) → confirm Red (T008)
2. Implement action mapping (T009) → implement sub-account derivation (T010) → confirm Green (T011)
3. Run quality gates (T012, T013 parallel) → full suite (T014) → logging review (T015)

### Parallel Opportunities

- T002 + T003 (schema + constants): both foundational, different files
- T004 + T005 + T006 (fixture + unit tests + BDD scenarios): all independent, different files
- T012 + T013 (mypy + ruff): independent tools

---

## Implementation Strategy

### MVP (only one user story — all tasks are MVP)

1. Complete Phase 1: Setup (T001)
2. Complete Phase 2: Foundational enum + constants (T002, T003)
3. Write US1 tests (T004–T006), add step bindings (T007), confirm Red (T008)
4. Implement (T009, T010), confirm Green (T011)
5. Polish (T012–T015)

---

## Notes

- **Total tasks**: 15 (T001–T015)
- **US1 tasks**: 8 (T004–T011)
- **Polish tasks**: 4 (T012–T015)
- **[P] tasks** (parallelisable): T002, T003, T004, T005, T006, T012, T013
- Modified source files: `schema.py`, `constants.py`, `parsers/hl.py`
- `parsers/hl.py` import additions are done in T009 (Phase 3); T003 touches `constants.py` only
- New test fixtures: `tests/data/consolidate_journals/valid_hl_lodgement.csv` (T004),
  `tests/data/consolidate_journals/valid_hl_mixed.csv` (T004, 4-row mixed-type fixture)
- Modified test files: `test_hl_parser.py` (12 tests), `consolidate_journals.feature`
  (3 new scenarios), `consolidate_journals_steps.py`
- No new source files, no new pipeline modes, no changes to `run_pipeline.ps1`
- The `CASH_ACTION_TYPES` frozenset is intentionally unchanged — lodgement is not a cash action
- `str.removeprefix()` requires Python 3.9+ — satisfied by the project's Python 3.11+ requirement
- There is no `_strip_lodgement_prefix` helper; the prefix stripping is inline in `_parse_row()`
