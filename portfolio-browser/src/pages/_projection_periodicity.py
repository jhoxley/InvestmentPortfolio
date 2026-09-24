"""Pure store transitions for the Projection page's Periodicity control (023).

Kept out of `projection.py` because that module registers a Dash page at import
time and so cannot be imported in a plain unit test. Everything here is free of
Dash and I/O: the callbacks in `projection.py` are thin wrappers around it.

The store holds `{"value": <service-side interval or None>, "explicit": bool}`.
Only `explicit_state_for_click` ever sets `explicit` to True, which is what makes
a user's choice survive every later target or account change.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from config.content import PeriodicityConfig
from src.components.periodicity_controls import derive_periodicity

PeriodicityState = dict[str, Any]


def explicit_state_for_click(option_key: str, config: PeriodicityConfig) -> PeriodicityState:
    """Return the store state for a user's own interval choice.

    Args:
        option_key: The clicked option's key, e.g. "year".
        config: The validated periodicity configuration.

    Returns:
        `{"value": <service-side value>, "explicit": True}`.

    Raises:
        KeyError: If `option_key` is not a configured option.
    """
    return {"value": config.value_for_key(option_key), "explicit": True}


def next_periodicity_state(
    store_data: PeriodicityState | None,
    accounts_data: list[dict[str, Any]] | None,
    account_name: str,
    target_date: date,
    config: PeriodicityConfig,
) -> PeriodicityState:
    """Return the store state after the target date or account changes.

    An explicit choice is returned unchanged (never overridden). Otherwise the
    interval is derived from the full plotted span — the account's earliest
    recorded date through the projection target — with the same thresholds used
    on Overview and Positions.

    Args:
        store_data: The current store contents, or None if empty.
        accounts_data: The fetched accounts store's data.
        account_name: The currently selected account.
        target_date: The current projection target date.
        config: The validated periodicity configuration.

    Returns:
        The new store state; `value` is None only when the account's earliest
        date cannot be determined (the service then applies its own default).
    """
    if store_data and store_data.get("explicit"):
        return store_data
    earliest = _earliest_recorded_date(accounts_data, account_name)
    if earliest is None:
        return {"value": None, "explicit": False}
    key = derive_periodicity(earliest, target_date, config.thresholds)
    return {"value": config.value_for_key(key), "explicit": False}


def _earliest_recorded_date(
    accounts_data: list[dict[str, Any]] | None, account_name: str
) -> date | None:
    """Return the account's earliest position-ladder date, or None if unknown."""
    if not accounts_data:
        return None
    account = next((a for a in accounts_data if a["account_name"] == account_name), None)
    if account is None:
        return None
    resource = account.get("position_ladder")
    if resource is None:
        return None
    return date.fromisoformat(resource["from_date"])
