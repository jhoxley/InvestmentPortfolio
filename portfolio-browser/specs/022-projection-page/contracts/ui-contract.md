# Contract: Projection Page UI — component IDs, callback graph, config schema

Mirrors the format of `specs/021-periodicity-controls/contracts/ui-contract.md`.

## Navigation (FR-001, FR-002)

- `config/content.yaml`'s `nav_sections` entry `{key: income, label: Income, order: 4}` is
  **replaced in place** by `{key: projection, label: Projection, order: 4}` — same `order`,
  so the entry occupies the exact position the spec requires ("in the position the 'Income'
  entry previously occupied").
- `src/pages/income.py` is deleted; `src/pages/projection.py` registers at `path="/projection"`
  the same way every other page self-registers via `dash.register_page`.
- Any `shell.py` reference to the income route's parameters-bar rendering is replaced with the
  projection route's.

## Page-local component IDs (all prefixed `projection-` to avoid the 020 collision class)

| ID | Component | Role |
|---|---|---|
| `projection-mount-trigger` | `dcc.Interval` (`max_intervals=1`) | page-scope Input, mirrors every other page's mount trigger |
| `projection-accounts-store` | `dcc.Store` | fetched account list |
| `projection-start-date` | `dcc.DatePickerSingle` | start date control (FR-007) |
| `projection-horizon-1y` / `-5y` / `-10y` / `-20y` | `dbc.Button` in a `dbc.ButtonGroup` | preset horizons (FR-004) |
| `projection-target-date` | `dcc.DatePickerSingle` | calendar picker (FR-005), always synced to reflect the value in `projection-target-store` (FR-006) |
| `projection-target-store` | `dcc.Store` | single source of truth for "projection date in effect" (FR-006) |
| `projection-date-validation` | `dbc.FormText` (or `dbc.Alert`) | inline rejection message (FR-014) |
| `{"type": "projection-attribute-toggle", "name": <label>}` | `dbc.Switch` (pattern-matched, via `build_attribute_toggles`) | return selection (FR-008) |
| `projection-chart` | `dcc.Graph` | the rendered figure |

`app-parameters-account` (the shared, page-scoped-per-020 account selector) is reused as-is.

## Callback graph

1. **`_fetch_accounts`** — Input: `projection-mount-trigger`. Fetches `/v1/accounts`,
   populates `projection-accounts-store` and the account dropdown options. No attribute fetch
   is needed (returns are the fixed local list, research.md #5).
2. **`_apply_default_account`** — Input: `projection-accounts-store.data`. Selects the
   alphabetically-first account, matching every other page.
3. **`_sync_start_date_to_selected_account`** — Input: `app-parameters-account.value`
   (State: `projection-accounts-store.data`). Sets `projection-start-date.date` to that
   account's `position_ladder.to_date` (FR-007, FR-015's account-switch reset).
4. **`_apply_horizon_click`** — Inputs: the four `projection-horizon-*.n_clicks` (State:
   `projection-start-date.date`). Computes `start_date + N years` and writes
   `projection-target-store.data`.
5. **`_apply_calendar_pick`** — Input: `projection-target-date.date` (only fires on a genuine
   user pick, since step 6 below writes the *store*, not this control, directly — see next
   bullet). Validates `> projection-start-date.date`; on success writes
   `projection-target-store.data` and clears `projection-date-validation`; on failure leaves
   the store untouched and sets the validation message (FR-014).
6. **`_sync_target_display`** — Input: `projection-target-store.data`. Writes
   `projection-target-date.date` so the calendar control always reflects what's in effect
   (FR-006), regardless of whether a button or the calendar itself set it.
7. **`_render_chart`** — Inputs: `app-parameters-account.value`, `projection-start-date.date`,
   `projection-target-store.data`, every `projection-attribute-toggle` switch. Calls
   `get_projection(...)`; on zero returns selected, still renders (requesting no `return`
   params — the service's own contract guarantees `"Historical"` alone comes back, FR-013);
   on `PortfolioAnalysisServiceError`, renders the same error treatment as every other page
   (FR-017).

This is one more callback than 021 needed (the calendar-vs-button dual-writer requires the
extra `_sync_target_display` indirection step), which is why `projection-target-store` exists
as an explicit intermediate rather than writing `projection-target-date.date` directly from
both step 4 and step 5 — two callbacks with `allow_duplicate=True` writing the same Output
from different Inputs is exactly the shape that caused the 020 collision when the two
callbacks additionally shared their whole Input signature; routing through one store avoids
re-creating that risk even though the Inputs here already differ enough to not collide in
practice — the indirection is cheap insurance, documented so a future page copying this
pattern keeps it.

## `config/content.yaml` additions

```yaml
nav_sections:
  # 'income' entry replaced by:
  - key: projection
    label: Projection
    order: 4

projection:
  horizons:
    - { key: 1y,  label: "1Y",  years: 1 }
    - { key: 5y,  label: "5Y",  years: 5 }
    - { key: 10y, label: "10Y", years: 10 }
    - { key: 20y, label: "20Y", years: 20 }
  returns:
    - { key: itd_ann, label: "Ann. ITD" }
    - { key: 1y,       label: "1Y" }
    - { key: 3y,       label: "3Y" }
    - { key: 5y,       label: "5Y" }
```

Loaded/validated by a new `ProjectionConfig` Pydantic model in `config/content.py`, following
the exact validation precedent set by 021's `PeriodicityConfig` (exactly 4 horizons and 4
returns; unique keys/labels; positive ascending `years`) — Principle IV (no hard-coded labels
or year offsets in `src/`).
