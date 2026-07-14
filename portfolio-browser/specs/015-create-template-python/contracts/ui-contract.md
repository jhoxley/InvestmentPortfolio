# UI Contract: Dash Application Shell

This project has no network API in this feature. The "interface" exposed
here is the page-routing contract (URL paths Dash registers) and the stable
DOM element identifiers that BDD step definitions and future features rely
on. Treat changes to either as a breaking change to this feature.

## Page routes (Dash Pages)

| Path | Nav label | Default | Module |
|---|---|---|---|
| `/` (alias of `/overview`) | Overview | Yes (Clarification 1) | `src/pages/overview.py` |
| `/positions` | Positions | No | `src/pages/positions.py` |
| `/performance` | Performance | No | `src/pages/performance.py` |
| `/income` | Income | No | `src/pages/income.py` |

Each route is registered via `dash.register_page(__name__, path=..., name=...)`.
The nav label, path segment, and default flag are driven from
`NavigationSection` config entries (see `data-model.md`) — the table above
must stay in sync with `config/content.yaml`.

## Stable component element IDs

BDD steps and any future feature that needs to locate shell chrome MUST use
these IDs rather than CSS class names or text content (text is a11y/i18n
surface, not a stable test hook):

| Element ID | Component | Purpose |
|---|---|---|
| `app-header` | `src/components/header.py` | Root header container; contains the app name text |
| `app-footer` | `src/components/footer.py` | Root footer container; contains version + published date |
| `app-sidebar` | `src/components/sidebar.py` | Root sidebar/nav container |
| `app-sidebar-nav-{key}` | `src/components/sidebar.py` | One nav link per `NavigationSection.key`, e.g. `app-sidebar-nav-overview` |
| `app-content-frame` | `src/layout/shell.py` | Container wrapping the parameters bar + the routed page content |
| `app-parameters-bar` | `src/layout/shell.py` | Persistent parameters/controls placeholder, rendered above page content on every route |
| `app-parameters-account` | `src/layout/shell.py` | Illustrative, disabled account-selector placeholder control inside the parameters bar |
| `app-parameters-daterange` | `src/layout/shell.py` | Illustrative, disabled date-range placeholder control inside the parameters bar |
| `app-page-content` | `src/layout/shell.py` (via `dash.page_container`) | Where the currently routed page's placeholder content renders |

## Contract guarantees

- The header, footer, sidebar, and parameters bar (`app-header`,
  `app-footer`, `app-sidebar`, `app-parameters-bar`) are rendered exactly
  once per session and are NOT re-mounted when navigating between pages
  (FR-008) — BDD scenarios assert on DOM node identity/persistence, not
  just presence, to catch an accidental full remount.
- `app-page-content` is the only region whose contents change on
  navigation.
- Every `app-sidebar-nav-{key}` element renders as a real anchor (`<a>`)
  element (via `dbc.NavLink`'s `dcc.Link`-style client-side routing), so it
  is keyboard-focusable and activatable via Enter per standard link
  semantics (FR-010 baseline accessibility). Space-to-activate is a
  `<button>`/`role="button"` convention per the WAI-ARIA APG, not a
  requirement for links, so it intentionally does not apply here.
