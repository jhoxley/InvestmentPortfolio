"""Shared Account/From/To/shortcut-button controls (Overview + Positions).

Extracted from `src/layout/shell.py` and `src/pages/_overview_chart.py`
(both Overview-only originally) so both the Overview and Positions pages
present and behave identically for these controls (spec Assumptions;
research.md #1 in specs/018-positions-page). Only one route's parameters
bar is ever mounted in the DOM at a time (`shell.py`'s own
`_render_parameters_bar()` swap-by-pathname), so both pages reusing the
same component IDs is safe.

Note: this module owns the *shortcut/clamp* computation only. Each page's
own *default range on account selection/switch* differs (Overview uses the
account's full recorded history; Positions always uses "YtD" — see
specs/018-positions-page/research.md #1a) and is NOT unified here.
"""

from __future__ import annotations

from datetime import date, timedelta

import dash_bootstrap_components as dbc
from dash import dcc, html

from src.models.portfolio_analysis import AccountSummary

_WEEKDAY_SATURDAY = 5
_WEEKDAY_SUNDAY = 6

# Reporting Period Shortcut codes (017; data-model.md's "Reporting Period
# Shortcut" entity). Fixed, spec-defined set — not user-configurable.
SHORTCUT_YTD = "ytd"
SHORTCUT_1Y = "1y"
SHORTCUT_3Y = "3y"
SHORTCUT_5Y = "5y"
SHORTCUT_ALL = "all"
_SHORTCUT_YEAR_OFFSETS = {SHORTCUT_1Y: 1, SHORTCUT_3Y: 3, SHORTCUT_5Y: 5}

_SHORTCUT_BUTTONS = [
    ("overview-shortcut-ytd", "YtD"),
    ("overview-shortcut-1y", "1Y"),
    ("overview-shortcut-3y", "3Y"),
    ("overview-shortcut-5y", "5Y"),
    ("overview-shortcut-all", "All"),
]


def _last_business_day(today: date) -> date:
    """Return the most recently completed business day before `today` (FR-004).

    Standard Monday-Friday definition, no public-holiday calendar (spec
    Assumptions).

    Args:
        today: The reference "today" date.

    Returns:
        The most recent weekday strictly before `today`.
    """
    candidate = today - timedelta(days=1)
    while candidate.weekday() in (_WEEKDAY_SATURDAY, _WEEKDAY_SUNDAY):
        candidate -= timedelta(days=1)
    return candidate


def _earliest_from_date(account: AccountSummary) -> date:
    """Return the earliest `from_date` across an account's ingested resources (FR-003).

    Args:
        account: The selected account summary.

    Returns:
        The minimum `from_date` of whichever of `capital_ledger`/`position_ladder`
        is present (never both `None` per the API's own contract).
    """
    candidates = [
        r.from_date for r in (account.capital_ledger, account.position_ladder) if r is not None
    ]
    return min(candidates)


def _years_before(today: date, years: int) -> date:
    """Return the exact calendar-date offset `years` before `today`.

    Args:
        today: The reference date.
        years: Number of years to subtract.

    Returns:
        `today` with `years` subtracted from the year, falling back to 28
        February when `today` is a leap day (29 Feb) and the target year
        is not itself a leap year.
    """
    try:
        return today.replace(year=today.year - years)
    except ValueError:
        return today.replace(year=today.year - years, day=28)


def _shortcut_from_date(code: str, account: AccountSummary, today: date) -> date:
    """Compute (and clamp) a Reporting Period Shortcut's "from" date (FR-002-FR-006, FR-008).

    Args:
        code: One of `SHORTCUT_YTD`, `SHORTCUT_1Y`, `SHORTCUT_3Y`, `SHORTCUT_5Y`,
            `SHORTCUT_ALL`.
        account: The currently selected account (for the clamp floor and
            `SHORTCUT_ALL`'s own value).
        today: The reference "today" date.

    Returns:
        The computed date, never earlier than `account`'s own
        `_earliest_from_date` (FR-008) — a no-op clamp for `SHORTCUT_ALL`,
        since that *is* the earliest date already.

    Raises:
        ValueError: `code` is not one of the five known shortcut codes.
    """
    earliest = _earliest_from_date(account)
    if code == SHORTCUT_ALL:
        return earliest
    if code == SHORTCUT_YTD:
        computed = date(today.year, 1, 1)
    elif code in _SHORTCUT_YEAR_OFFSETS:
        computed = _years_before(today, _SHORTCUT_YEAR_OFFSETS[code])
    else:
        raise ValueError(f"Unknown shortcut code: {code!r}")
    return max(computed, earliest)


def _build_shortcut_buttons() -> dbc.Col:
    """Five Reporting Period Shortcut buttons (017; FR-001).

    Click handling (which date range each computes, and disabling them
    during a refresh) lives in each page's own module — this only builds
    the buttons themselves.
    """
    buttons = [
        dbc.Button(label, id=button_id, size="sm", color="secondary", outline=True)
        for button_id, label in _SHORTCUT_BUTTONS
    ]
    return dbc.Col(dbc.ButtonGroup(buttons), width="auto")


def build_account_date_controls() -> list:
    """Real Account selector + From/To date pickers + shortcut buttons (016/017/018).

    Shared by both Overview's and Positions's parameters bars
    (`src/layout/shell.py`) — options/values are populated by each page's
    own callbacks once it has fetched `/v1/accounts`; this only builds the
    empty controls.

    Returns:
        A list of `dbc.Col` elements ready to splice into a `dbc.Row`.
    """
    account_selector = dbc.Select(id="app-parameters-account", options=[], value=None)
    from_date = dcc.DatePickerSingle(id="app-parameters-from-date", placeholder="From")
    # max_date_allowed=today is static (today doesn't change within a session);
    # the "from" picker's max is kept in sync with the *current* "to" value
    # dynamically instead, via a callback (FR-015).
    to_date = dcc.DatePickerSingle(
        id="app-parameters-to-date", placeholder="To", max_date_allowed=date.today().isoformat()
    )
    return [
        dbc.Col(
            html.Label("Account", htmlFor="app-parameters-account"),
            width="auto",
        ),
        dbc.Col(account_selector, width=3),
        dbc.Col(
            html.Label("From", htmlFor="app-parameters-from-date"),
            width="auto",
        ),
        dbc.Col(from_date, width="auto"),
        dbc.Col(
            html.Label("To", htmlFor="app-parameters-to-date"),
            width="auto",
        ),
        dbc.Col(to_date, width="auto"),
        _build_shortcut_buttons(),
    ]
