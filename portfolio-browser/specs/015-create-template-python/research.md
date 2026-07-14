# Research: Dash Application Shell

All Technical Context items were resolvable from the feature description,
the project constitution, and established Dash ecosystem practice — no
`NEEDS CLARIFICATION` markers remained after the spec/clarify stages, so
this covers technology-choice research rather than unknown resolution.

## Multi-page navigation without full reload

**Decision**: Use Dash's built-in Pages feature (`Dash(..., use_pages=True)`
with a `pages_folder`), registering one page per navigation section via
`dash.register_page()`.

**Rationale**: This is the framework's own, officially supported answer to
"multiple sections, no full page reload, one click to switch" (SC-003,
FR-007) — it uses `dcc.Location`/client-side routing under the hood without
requiring the project to hand-build that mechanism. It also gives each
future feature a natural, isolated place (one page module) to add real
content, without touching routing/shell code — directly supporting the
constitution's Principle V (prefer standard libraries over reinventing a
solved problem) and Principle II's spirit of keeping concerns separated.

**Alternatives considered**:
- Hand-rolled routing via a single `dcc.Location` + a big callback
  `if/elif` dispatching on pathname — rejected: reinvents what Dash Pages
  already provides, and concentrates all section content in one callback,
  violating single-responsibility.
- A JavaScript SPA framework (React/Vue) calling a Python API — rejected:
  the user explicitly asked for "all code in Python" as a Dash app; this
  would also introduce a frontend/backend split this feature doesn't need.

## Layout / responsive grid

**Decision**: Use `dash-bootstrap-components` (`dbc.Container`, `dbc.Row`,
`dbc.Col`) to implement the header/sidebar/content split.

**Rationale**: Bootstrap's column system natively expresses "sidebar ≤20%,
content remaining space" as `dbc.Col(width=2)` / `dbc.Col(width=10)|width="auto"`,
and its responsive breakpoint classes give the "shrink proportionally, don't
collapse behind a toggle" tablet behavior (Clarification 3) without custom
CSS. Bootstrap's shipped components also carry baseline ARIA roles and
keyboard-operable nav markup out of the box, supporting FR-010's baseline
accessibility bar with minimal bespoke work. It is the most widely used,
actively maintained Dash component library for exactly this purpose —
avoiding reinvention (Principle V).

**Alternatives considered**:
- Hand-written CSS Grid/Flexbox in a custom stylesheet — rejected: more
  code to own and test for a solved layout problem, and higher risk of
  missing accessibility affordances that Bootstrap ships by default.
- `dash-mantine-components` — a reasonable alternative UI kit, but less
  ubiquitous in the Dash ecosystem than dash-bootstrap-components and would
  introduce a second design-system dependency without a concrete need.

## Configuration management

**Decision**: Two-tier config, both validated at startup and both
constitution-Principle-IV compliant:
- `config/settings.py` — a `pydantic-settings` `BaseSettings` class for
  runtime/environment concerns (host, port, debug flag), overridable via
  `.env`.
- `config/content.py` + `config/content.yaml` — a plain Pydantic model that
  loads and validates a YAML file holding non-secret, human-edited content
  (app name, version, published date, the ordered list of nav section
  labels). Both fail fast (raise on missing/malformed values at import
  time) rather than at first point of use.

**Rationale**: Pydantic is the de facto standard for typed, validated
Python configuration and is already a natural fit alongside Dash/Flask;
splitting "operational" settings (env-driven, could hold secrets in future
features) from "content" config (checked into source, human-edited, no
secrets) keeps the two concerns from being conflated as the app grows an
API-integration layer later.

**Alternatives considered**:
- A single flat `.env` file for everything, including the nav section list
  — rejected: env vars are a poor fit for structured/ordered list data like
  nav sections; YAML is more legible for that shape of data.
- `python-decouple` — a lighter alternative to pydantic-settings, but
  Pydantic's validation (fail-fast, typed) gives stronger guarantees for
  free and is already a common dependency in modern Python web stacks.

## Testing strategy (BDD + Dash)

**Decision**: `pytest-bdd` for Gherkin scenario execution, driving Dash's
own `dash[testing]` extra (`dash_duo` pytest fixture, Selenium-based) to
render the app in a real browser and assert on visible behaviour (header
text, sidebar width, click-to-navigate, footer content). `webdriver-manager`
handles the ChromeDriver binary automatically rather than requiring manual
installation/pinning.

**Rationale**: `dash.testing` is Dash's own maintained answer to testing
Dash apps end-to-end and is the standard recommended approach in Dash's
documentation — this satisfies the constitution's Test-First/BDD principle
(Gherkin scenarios, kept executable) while verifying real rendered
behaviour (element widths, click interactions) that a pure unit test on
Python callback functions could not catch.

**Alternatives considered**:
- Testing only Dash callback functions in isolation (no browser) —
  rejected as the sole strategy: cannot verify layout facts like "sidebar
  ≤20% width" or that clicking an item changes rendered content, both of
  which are explicit acceptance criteria in the spec.
- Playwright instead of Selenium — a fine alternative in general, but
  `dash.testing`'s official fixtures are Selenium-based; using them avoids
  building custom Dash-aware browser-automation glue that already exists.
