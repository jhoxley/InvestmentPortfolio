# Data Model: Periodicity Control for the Projection Page

No persisted data and no new API models. One client-side state object, identical in shape to the
one Overview and Positions already keep.

## Periodicity Selection (`projection-periodicity-store`)

| Field | Type | Meaning |
|-------|------|---------|
| `value` | string or null | Service-side interval in effect (`day`, `week`, `month`, `quarter`, `annual`); null only when the account's earliest date cannot be determined, in which case the service default applies and no button is highlighted |
| `explicit` | bool | True only after the user clicks an interval button |

Initial value: `null` (store empty until a target is chosen).

### State transitions

| Event | Result |
|-------|--------|
| Button click | `{value: clicked, explicit: true}` |
| Target changes / account changes / accounts load, `explicit` false | `{value: derived(span), explicit: false}` |
| Same events, `explicit` true | Store rewritten unchanged (triggers exactly one chart render) |
| Account switch | Target and returns reset; store untouched |
| Page revisit | Store recreated empty (per-page, per-visit) |

## Plotted Span

`target_date − earliest recorded date of the selected account` (its `position_ladder.from_date`).
Mapped by the shared thresholds: ≤1y → day, ≤3y → month, ≤5y → quarter, otherwise year; never week.

## Existing entities used unchanged

`PeriodicityConfig` / `PeriodicityThresholds` (config/content.py), the projection response entries
(`get_projection(..., periodicity=...)`).
