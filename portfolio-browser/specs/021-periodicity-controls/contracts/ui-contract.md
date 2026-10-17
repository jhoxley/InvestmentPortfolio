# UI Contract: Periodicity Control

**Feature**: `021-periodicity-controls` | **Date**: 2026-09-22

Component ids, callback graph and config schema for the shared Periodicity control. Both pages
build it from one shared function but own **separate component ids** — see "Why per-page ids"
below before changing that.

---

## 1. Component ids

`build_periodicity_control(page_prefix)` emits, for `page_prefix` ∈ {`overview`, `positions`}:

| Component | Id | Notes |
|---|---|---|
| Label | `{page_prefix}-parameters-periodicity-label` | Text from `content.yaml`'s `periodicity.label` |
| Button group | `{page_prefix}-parameters-periodicity-group` | `dbc.ButtonGroup` wrapper |
| Interval button | `{page_prefix}-parameters-periodicity-{key}` | One per option `key`: `day`, `week`, `month`, `quarter`, `year` |
| Effective-interval store | `{page_prefix}-periodicity-store` | Declared in the **page's own layout**, not the parameters bar |

So Overview owns `overview-parameters-periodicity-month` etc., and Positions owns
`positions-parameters-periodicity-month` etc. — ten buttons in total across the app, never shared.

**Placement**: appended to the existing parameters-bar row for Overview and Positions only, after
the date-range shortcut `ButtonGroup`. The Performance bar
(`_build_performance_parameters_bar`) and the static placeholder bar
(`_build_static_parameters_bar`) are **not** changed.

**Active-state rendering**: the button whose `key` matches the store's effective interval is
rendered `active=True, outline=False`; the other four `active=False, outline=True` — the same
visual idiom as the existing shortcut buttons.

### Why per-page ids (do not "simplify" this)

The other shared controls (`app-parameters-account`, `app-parameters-from-date`, …) use one id
across three routes. That is safe for the DOM but **not** for Dash's callback registry: Dash
derives an `allow_duplicate` Output's callback id by hashing the callback's *Inputs* alone, so two
pages declaring the same Output from the same Inputs collapse into a single registration and the
page imported last silently wins. This caused feature 020's defect, where 7 of 20 registrations
were dropped and Performance's "ITD" shortcut ran Positions' year-to-date mapping.

Per-page ids make that impossible here by construction. `tests/unit/test_callback_registration.py`
asserts no registration is ever overwritten and needs no browser, so a regression fails the unit
suite immediately.

---

## 2. Callback graph (per page — identical shape on both)

```text
                            ┌─────────────────────────────────────────┐
 five interval buttons ────▶│ _apply_periodicity_click                │
   (n_clicks)               │  writes {value, explicit: true}         │──┐
                            └─────────────────────────────────────────┘  │
                                                                         ▼
 app-parameters-from-date ─┐ ┌─────────────────────────────────────────┐ ┌──────────────────────┐
 app-parameters-to-date  ──┼▶│ _derive_periodicity_from_range          │▶│ {page}-periodicity-  │
 (page-scope Input)      ──┘ │  PreventUpdate if store.explicit        │ │ store  (data)        │
                             │  else writes {value, explicit: false}   │ └──────────────────────┘
                             └─────────────────────────────────────────┘        │        │
                                                                                │        │
                             ┌──────────────────────────────────────────────────┘        │
                             ▼                                                           ▼
              ┌──────────────────────────────┐                        ┌──────────────────────────────┐
              │ _style_periodicity_buttons   │                        │ _render_chart  (EXISTING —    │
              │  active/outline per button   │                        │  gains the store as an Input) │
              └──────────────────────────────┘                        └──────────────────────────────┘
```

| Callback | Inputs | State | Outputs |
|---|---|---|---|
| `_apply_periodicity_click` | the five buttons' `n_clicks` | — | store `data` |
| `_derive_periodicity_from_range` | `app-parameters-from-date.date`, `app-parameters-to-date.date`, page-scope | store `data` | store `data` (allow_duplicate) |
| `_style_periodicity_buttons` | store `data` | — | each button's `active` + `outline` |
| `_render_chart` *(existing)* | + store `data` | unchanged | unchanged |

**Rules**:

- `_apply_periodicity_click` uses `ctx.triggered_id` to identify the clicked interval and
  `PreventUpdate`s when no button has actually been clicked (guards the mount-time fire).
- `_derive_periodicity_from_range` is the **only** writer of a derived value and never sets
  `explicit`, so a derived write can never latch.
- Both store-writing callbacks carry the page's own mount-trigger as a page-local scoping Input,
  consistent with the pattern established when closing 020 — belt and braces alongside the
  per-page ids.
- `_render_chart` gains the store as an Input and passes `store["value"]` to the client. It must
  `PreventUpdate` while the store is empty, so no request is made before an interval is known.
- The store is added to the **page's** layout (like the existing `{page}-accounts-store`), so it
  is absent on other routes and the callbacks cannot fire off-page.
- The Periodicity buttons are added to each page's existing `running=[…]` disabled-during-refresh
  list (FR-016).

---

## 3. Config schema (`config/content.yaml`)

```yaml
periodicity:
  label: "Periodicity"
  options:
    - { key: day,     label: day,     value: day }
    - { key: week,    label: week,    value: week }
    - { key: month,   label: month,   value: month }
    - { key: quarter, label: quarter, value: quarter }
    - { key: year,    label: year,    value: annual }
  thresholds:
    day_max_years: 1
    month_max_years: 3
    quarter_max_years: 5
```

Validated fail-fast by `ContentConfig` (see data-model.md §2): exactly five options; unique `key`,
`label` and `value`; strictly ascending positive thresholds; every derivable interval present in
`options`.

---

## 4. Behavioural contract (what a test may rely on)

| # | Guarantee |
|---|---|
| 1 | Both pages render a label and exactly five buttons, in config order |
| 2 | Exactly one button is `active` at any time, and it matches the store's effective interval |
| 3 | Clicking a button re-renders the chart at that interval and changes nothing else on the page |
| 4 | With no click yet, the effective interval follows the range: ≤1y → day, ≤3y → month, ≤5y → quarter, longer → year |
| 5 | `week` is never the effective interval unless its button was clicked |
| 6 | After any click, the effective interval survives every subsequent date, shortcut and account change |
| 7 | The value sent to the service is the option's `value` (so `year` sends `annual`) |
| 8 | Omitting the interval is never necessary — the store always holds one before a request is made |
| 9 | The control is disabled while a chart refresh is in flight |
| 10 | Neither the Performance nor the Income page gains the control |
