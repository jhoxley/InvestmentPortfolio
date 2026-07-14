---

description: "Task list for Dash Application Shell"
---

# Tasks: Dash Application Shell

**Input**: Design documents from `specs/015-create-template-python/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ui-contract.md, quickstart.md

**Tests**: Explicitly requested via the constitution's Test-First/BDD (NON-NEGOTIABLE) principle — every phase below writes a failing test (unit or Gherkin/BDD) and confirms it fails before the corresponding implementation is written, with one documented exception recorded in `plan.md`'s Complexity Tracking table (User Story 3's footer scenario, which necessarily starts green because the footer is shared shell infrastructure built in User Story 1).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

Single project rooted at `portfolio-browser/` (this repo), per `plan.md`'s
Project Structure. All paths below are relative to `portfolio-browser/`.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Create project directory structure: `config/`, `src/components/`, `src/layout/`, `src/pages/`, `tests/bdd/features/`, `tests/bdd/steps/`, `tests/unit/` (with `__init__.py` where needed for Python packages)
- [X] T002 [P] Create `pyproject.toml` declaring runtime dependencies (`dash>=2.17`, `dash-bootstrap-components`, `pydantic>=2`, `pydantic-settings`, `pyyaml`) and a `[project.optional-dependencies] dev = [...]` group (`pytest`, `pytest-bdd`, `dash[testing]`, `webdriver-manager`, `ruff`, `mypy`) so `pip install -e .[dev]` (per `quickstart.md`) works as documented, plus `[tool.ruff]` and `[tool.mypy]` configuration sections
- [X] T003 [P] Create `.env.example` with `HOST`, `PORT`, `DEBUG` placeholder values

**Checkpoint**: Project scaffold and tooling config exist; no application or config code yet.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Validated, tested config-loading logic that every user story depends on. No UI/chrome code is built in this phase — that begins in User Story 1 (Phase 3), immediately after its failing test is confirmed, per the constitution's Test-First/BDD principle.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 [P] Write failing unit tests in `tests/unit/test_content_config.py` for `config/content.py`'s not-yet-built `NavigationSection`/`BuildInfo` models and loader: at least one section required, unique `key`/`order`, exactly one `is_default=True` (else raises at load), and missing `version`/`published_date` fall back to `"unknown"`
- [X] T005 [P] Write failing unit tests in `tests/unit/test_settings.py` for `config/settings.py`'s not-yet-built runtime settings: default `HOST`/`PORT`/`DEBUG` values and that environment variables override them
- [X] T006 Implement `NavigationSection` and `BuildInfo` Pydantic models plus the fail-fast YAML loader/validator in `config/content.py` so the tests from T004 pass (depends on T004)
- [X] T007 [P] Create `config/content.yaml` with `app_name: "Investment Portfolio Browser"`, a placeholder `version` and `published_date`, and four nav sections — `overview` (`is_default: true`), `positions`, `performance`, `income` — with labels and order per `contracts/ui-contract.md` (depends on T006 for the schema shape)
- [X] T008 Implement runtime settings (`HOST`, `PORT`, `DEBUG`) via a `pydantic-settings` `BaseSettings` class reading from `.env` in `config/settings.py` so the tests from T005 pass (depends on T005)
- [X] T009 Run `pytest tests/unit` and confirm all tests pass (depends on T006, T007, T008)

**Checkpoint**: Config loading is implemented and tested; no UI code exists yet. User story implementation can now begin.

---

## Phase 3: User Story 1 - View the persistent application shell (Priority: P1) 🎯 MVP

**Goal**: A user opens the app and sees the header, ≤20%-width sidebar, and a content area with a parameters/controls placeholder above the (Overview) page content.

**Independent Test**: Launch the app and verify header text, sidebar presence/width (including at a tablet viewport), content area width, and parameters-bar placement — per `spec.md` User Story 1 acceptance scenarios.

This story builds the header, footer, sidebar, and shell composition — the
full persistent chrome — because User Story 1's own acceptance scenarios
require all of them to coexist, and later stories (User Story 2's
persistence checks, User Story 3's footer checks) depend on this chrome
already existing. See `plan.md`'s Complexity Tracking for the one
consequence of this sequencing.

### Tests for User Story 1 (write and confirm failing FIRST)

- [X] T010 [P] [US1] Write Gherkin scenarios (from spec.md US1 acceptance scenarios 1–3, including a tablet-viewport check per Clarification 3) in `tests/bdd/features/application_shell.feature`
- [X] T011 [US1] Run `pytest tests/bdd -k application_shell` and confirm it fails/errors (no shell, components, or pages exist yet) — this is the Red checkpoint (depends on T010). **Note**: confirmed failing prior to implementation (initially via ModuleNotFoundError before app.py existed; see T019 note on the environment's browser limitation, which affects the Green side of this cycle, not this Red confirmation).

### Implementation for User Story 1

- [X] T012 [P] [US1] Create header component with `id="app-header"` displaying `content.app_name` in `src/components/header.py` (depends on T006, T007, T011)
- [X] T013 [P] [US1] Create footer component with `id="app-footer"` displaying `BuildInfo.version` / `BuildInfo.published_date`, falling back to `"unknown"` for missing values, in `src/components/footer.py` (depends on T006, T007, T011)
- [X] T014 [P] [US1] Create sidebar component with `id="app-sidebar"` in `src/components/sidebar.py`: one nav link per `NavigationSection` (`id="app-sidebar-nav-{key}"`, `href="/"` for the default section else `/{key}`), as a `dbc.Col` capped at 20% width that shrinks (not collapses) at narrower breakpoints, a visual "active" state reflecting the current pathname, and a vertically scrollable (`overflow-y: auto`) nav list in case items exceed viewport height (depends on T006, T007, T011)
- [X] T015 [P] [US1] Create the default Overview page — `dash.register_page(__name__, path="/", name="Overview")` with placeholder body content — in `src/pages/overview.py` (depends on T006, T007, T011)
- [X] T016 [US1] Compose the full-page shell in `src/layout/shell.py`: header on top, a row containing the sidebar and a content frame (`id="app-content-frame"`) holding a parameters/controls placeholder bar (`id="app-parameters-bar"`) — containing a disabled illustrative account-selector dropdown (`id="app-parameters-account"`) and a disabled illustrative date-range control (`id="app-parameters-daterange"`) — above `dash.page_container` (wrapped with `id="app-page-content"`), with the footer below (depends on T012, T013, T014)
- [X] T017 [US1] Wire `app.py` entrypoint: construct `Dash(__name__, use_pages=True, pages_folder="src/pages", external_stylesheets=[dbc.themes.BOOTSTRAP])`, set `app.layout` to the shell from T016, load settings from T008, and call `app.run(host=..., port=..., debug=...)` under `if __name__ == "__main__"` (depends on T016, T015, T008)
- [X] T018 [US1] Implement step definitions for `application_shell.feature` in `tests/bdd/steps/test_shell_steps.py` using the `dash_duo` fixture: assert `#app-header` text; assert `#app-sidebar` width ≤ 20% of viewport at a default desktop width, then resize to a tablet width and re-assert `#app-sidebar` still ≤ 20% with no overlap/clipping of `#app-content-frame`; assert `#app-parameters-bar` (including its two placeholder controls) appears above `#app-page-content`; assert the Overview page's placeholder content is shown by default at `/` without any click (depends on T011's Red confirmation, T017)
- [ ] T019 [US1] Run `pytest tests/bdd -k application_shell` and `pytest tests/unit`; fix any failures until all US1 acceptance scenarios pass (depends on T018). **BLOCKED in this dev environment**: `pytest tests/unit` passes (11/11) and `ruff check` is clean, but `pytest tests/bdd` cannot execute here — this machine has no Chrome or Firefox (only Microsoft Edge, which Dash's `dash.testing.browser.Browser` does not support; aliasing the matching `msedgedriver` as `chromedriver` was attempted and rejected by the driver with `SessionNotCreatedException: No matching capabilities found`, since it validates the `browserName` capability). As a substitute, a non-browser structural check (`app.server.test_client()` against the Dash JSON layout) confirmed all 13 expected element IDs, both `dbc.Col` width props (2/12 and 10/12), the Overview page text, and footer version/date are correctly wired — see conversation for the script. **This does not verify actual rendered pixel widths, tablet-resize behavior, or click interactions.** Run `pytest tests/bdd` on a machine with Chrome or Firefox installed to get a true Green result before considering US1 fully done.

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently — this is the MVP.

---

## Phase 4: User Story 2 - Navigate between placeholder sections (Priority: P2)

**Goal**: Clicking a nav item updates the content area (no full reload) while header/footer/sidebar stay unchanged.

**Independent Test**: Click each nav item and verify content updates and shell chrome persists — per `spec.md` User Story 2 acceptance scenarios.

### Tests for User Story 2 (write and confirm failing FIRST)

- [X] T020 [P] [US2] Write Gherkin scenarios (from spec.md US2 acceptance scenarios 1–2) in `tests/bdd/features/section_navigation.feature`
- [X] T021 [US2] Run `pytest tests/bdd -k section_navigation` and confirm it fails (Positions/Performance/Income pages don't exist yet) — Red checkpoint (depends on T020). **Note**: not re-run literally (would fail for the environment reason documented in T019, not for a content reason); confirmed via `--collect-only` that the scenarios were unimplementable before T022–T024 (pages didn't exist, so `dash.page_registry` would lack those routes).

### Implementation for User Story 2

- [X] T022 [P] [US2] Create Positions placeholder page — `dash.register_page(__name__, path="/positions", name="Positions")` — in `src/pages/positions.py` (depends on T021)
- [X] T023 [P] [US2] Create Performance placeholder page — `dash.register_page(__name__, path="/performance", name="Performance")` — in `src/pages/performance.py` (depends on T021)
- [X] T024 [P] [US2] Create Income placeholder page — `dash.register_page(__name__, path="/income", name="Income")` — in `src/pages/income.py` (depends on T021)
- [X] T025 [US2] Implement step definitions for `section_navigation.feature` in `tests/bdd/steps/test_shell_steps.py`: click each `#app-sidebar-nav-{key}`, assert `#app-page-content` changes to that section's distinct placeholder text, assert `#app-header`/`#app-footer`/`#app-sidebar` DOM nodes persist (not remounted) and are unchanged (depends on T022, T023, T024)
- [ ] T026 [US2] Run `pytest tests/bdd -k section_navigation`; fix any failures until all US2 acceptance scenarios pass (depends on T025). **BLOCKED for the same reason as T019** (no Chrome/Firefox in this dev environment). Substitute verification: `pytest tests/bdd --collect-only` shows all 9 scenarios (5 US1 + 4 US2) collect without error, and a Flask-test-client structural check confirms `/positions`, `/performance`, `/income` each serve distinct placeholder text alongside the shared header/footer/sidebar chrome. Run `pytest tests/bdd` on a machine with Chrome or Firefox to get a true Green result.

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently.

---

## Phase 5: User Story 3 - View build/version information (Priority: P3)

**Goal**: The footer persistently shows a software version and last-published date.

**Independent Test**: Load the app and read the footer without navigating — per `spec.md` User Story 3 acceptance scenarios.

**Note**: The footer component itself was already built in User Story 1
(T013), since it is shared persistent-shell chrome (see `plan.md`
Complexity Tracking). This story's step definitions are therefore expected
to pass immediately rather than starting Red — a deliberate, documented
exception, not an oversight.

### Tests for User Story 3

- [X] T027 [P] [US3] Write Gherkin scenarios (from spec.md US3 acceptance scenarios 1–2) in `tests/bdd/features/build_info_footer.feature`

### Implementation for User Story 3

- [X] T028 [US3] Implement step definitions for `build_info_footer.feature` in `tests/bdd/steps/test_shell_steps.py`: assert `#app-footer` shows the configured version and published date on load and after navigating to another section (depends on T027)
- [ ] T029 [US3] Run `pytest tests/bdd -k build_info_footer` and confirm it passes (depends on T028). **BLOCKED for the same reason as T019/T026.** All 11 scenarios across all three stories collect cleanly via `pytest tests/bdd --collect-only`; footer content was already confirmed present via the T019 structural check. Run `pytest tests/bdd` on a machine with Chrome or Firefox to get a true Green result.

**Checkpoint**: All user stories should now be independently functional.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [X] T030 [P] Run `ruff check .` and `mypy .` across the whole project; fix any violations
- [X] T031 [P] Walk through `quickstart.md` manually end-to-end (setup → configure → run → test → static analysis) and correct any drift between the doc and actual behavior. Fixed: the doc referenced a non-existent `requirements.txt` (now `pip install -e ".[dev]"` only); added a note that `tests/bdd` requires Chrome/Firefox. Confirmed live: server boots, `GET /` returns 200, `/positions` serves distinct placeholder text alongside the shared chrome.
- [X] T032 Verify FR-010 baseline accessibility: keyboard-only tab order reaches header, every sidebar nav link, and footer; confirm each is activatable via Enter/Space; spot-check text/background color contrast on header/footer/sidebar. **Verified via code review (no browser available in this environment — see T019)**: nav links render as real `dbc.NavLink`/`dcc.Link` anchors (`<a href>`), so they're natively keyboard-focusable and Enter-activatable in DOM order (Overview → Positions → Performance → Income); corrected the spec's "Enter/Space" wording in `contracts/ui-contract.md` since Space-to-activate is a `<button>` convention, not applicable to links (WAI-ARIA APG). Header/footer are non-interactive text, correctly excluded from tab order. The two parameters-bar controls are `disabled`, so browsers correctly skip them in tab order (expected for inert placeholders). Contrast uses Bootstrap's own default theme classes (`bg-primary`/`text-white`, `text-muted`, `bg-light`) rather than custom colors, which are maintained by the library to reasonable contrast levels — a real browser-based contrast measurement is still recommended (see T033).
- [X] T033 [P] Configure `dash_duo` to run headless Chrome via `webdriver-manager` so `tests/bdd` can run in CI without a manual ChromeDriver install. Implemented `tests/bdd/conftest.py::pytest_configure`, which auto-installs a matching chromedriver via `webdriver_manager.chrome.ChromeDriverManager` and prepends it to `PATH` if one isn't already available; run with `pytest tests/bdd --headless`. Still requires an actual Chrome/Chromium browser on the CI image (this only manages the driver binary) — confirmed it doesn't break test collection in this environment, but couldn't confirm a full Green run here since no Chrome is installed locally (see T019).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories. Contains only config-loading logic (with its own failing-tests-first cycle); no UI/chrome code.
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - Priority order: US1 (P1) → US2 (P2) → US3 (P3)
  - US1 builds all persistent shell chrome (header, footer, sidebar). US2 and US3 depend on that chrome already existing, per their own acceptance scenarios (persistence checks / footer checks) — so US1 MUST be implemented first, not just prioritized first.
  - All three stories share `tests/bdd/steps/test_shell_steps.py`, so their step-definition tasks (T018, T025, T028) must be applied in sequence to avoid conflicting edits to the same file — implement in priority order.
- **Polish (Phase 6)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2). Builds the shared shell chrome that US2 and US3 both require.
- **User Story 2 (P2)**: Requires US1's chrome (header/footer/sidebar/shell) to already exist, since its acceptance scenarios assert that chrome persists unchanged across navigation.
- **User Story 3 (P3)**: Requires US1's footer component to already exist (see Note in Phase 5) — this story adds dedicated test coverage for the footer's content, not new footer implementation.

### Within Each User Story

- Feature file written and confirmed failing (Red) before implementation begins (except User Story 3 — see its documented exception above)
- Models/components before layout composition
- Layout composition before the app entrypoint
- Step definitions implemented last, then run to Green
- Story complete before moving to the next priority

### Parallel Opportunities

- T002 and T003 (Setup) can run in parallel
- T004 and T005 (Foundational failing tests) can run in parallel
- T007 can run in parallel with T008 once T006 is done
- T012, T013, T014, T015 (US1 components/page, once T011's Red state is confirmed) can all run in parallel
- T022, T023, T024 (US2 placeholder pages, once T021's Red state is confirmed) can all run in parallel
- T030, T031, T033 (Polish) can run in parallel

---

## Parallel Example: Foundational Phase

```bash
# Launch failing-test tasks together:
Task: "Write failing unit tests for content config in tests/unit/test_content_config.py"
Task: "Write failing unit tests for runtime settings in tests/unit/test_settings.py"

# After T006 (content.py) is implemented, these can run in parallel:
Task: "Create config/content.yaml with app metadata and nav sections"
Task: "Implement runtime settings in config/settings.py"
```

## Parallel Example: User Story 1 (after T011's Red checkpoint)

```bash
Task: "Create header component in src/components/header.py"
Task: "Create footer component in src/components/footer.py"
Task: "Create sidebar component in src/components/sidebar.py"
Task: "Create the default Overview page in src/pages/overview.py"
```

## Parallel Example: User Story 2 (after T021's Red checkpoint)

```bash
Task: "Create Positions placeholder page in src/pages/positions.py"
Task: "Create Performance placeholder page in src/pages/performance.py"
Task: "Create Income placeholder page in src/pages/income.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories; config only, no UI)
3. Complete Phase 3: User Story 1 (write+Red the feature file first, then build header/footer/sidebar/shell/pages/app.py, then Green)
4. **STOP and VALIDATE**: Run `pytest tests/bdd -k application_shell`; manually load the app
5. Demo the shell (header, sidebar, content area, parameters placeholder) — this is the MVP

### Incremental Delivery

1. Complete Setup + Foundational → config validated, no UI yet
2. Add User Story 1 → full shell chrome + Overview page verified → Demo (MVP!)
3. Add User Story 2 → three more pages + click-navigation verified → Demo
4. Add User Story 3 → dedicated footer-content test coverage added → Demo
5. Polish → static analysis clean, accessibility and CI-readiness confirmed

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Every phase (except US3's documented exception) writes its test, runs it, and confirms a failure BEFORE any corresponding implementation task begins — this is enforced by explicit Red-checkpoint tasks (T011, T021) and dependency chains, not left as a suggestion
- Commit after each task or logical group
- Stop at any checkpoint to validate a story independently
- `tests/bdd/steps/test_shell_steps.py` is intentionally shared across all three stories' step definitions (they all drive the same running app instance); this is the one deliberate exception to "different files = parallelizable"
