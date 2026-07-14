# Data Model: Dash Application Shell

This feature has no persisted or fetched data — both entities below are
static, validated configuration read once at startup, not domain data.

## NavigationSection

Represents one selectable entry in the left-hand menu (spec: "Navigation
Section").

| Field | Type | Validation | Notes |
|---|---|---|---|
| `key` | `str` | required, unique, URL-safe slug | Used as the Dash page path segment, e.g. `overview` → `/overview` |
| `label` | `str` | required, non-empty | Display text in the nav menu, e.g. "Overview" |
| `order` | `int` | required, unique within the list | Determines rendering order in the sidebar |
| `is_default` | `bool` | exactly one `NavigationSection` in the config MUST have this `True` | Resolves Clarification 1 ("Overview" selected by default) |

**Validation rules** (enforced by the Pydantic model at startup, fail-fast
per constitution Principle IV):
- The list MUST contain at least one entry.
- `key` values MUST be unique across the list.
- `order` values MUST be unique across the list.
- Exactly one entry MUST have `is_default = True`.

**Source**: `config/content.yaml`, loaded and validated by `config/content.py`.

**Relationships**: Each `NavigationSection` corresponds 1:1 with a
registered Dash page (`src/pages/<key>.py`) whose placeholder content is
rendered when that section is selected.

## BuildInfo

Represents the version/publish-date data shown in the persistent footer
(spec: "Build Info").

| Field | Type | Validation | Notes |
|---|---|---|---|
| `version` | `str` | required, non-empty; falls back to `"unknown"` if unset | Resolves the "missing version" edge case |
| `published_date` | `date` | required; falls back to display as `"unknown"` if unset/unparseable | Resolves the "missing publish date" edge case |

**Source**: `config/content.yaml`, loaded and validated by `config/content.py`.

**Relationships**: None — rendered directly into the footer component.

## No state transitions

Neither entity has a lifecycle within this feature: both are read once at
process startup and remain constant for the life of the running app. The
only "state" in this feature is client-side UI state (which nav section is
currently selected), which is owned by Dash's routing (URL pathname), not by
these entities.
