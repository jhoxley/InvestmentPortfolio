"""Unit tests for the Projection page's pure periodicity store transitions (023)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest

from config.content import get_content_config
from src.components.periodicity_controls import periodicity_component_id
from src.pages._projection_periodicity import (
    explicit_state_for_click,
    next_periodicity_state,
)

_CONFIG = get_content_config().periodicity
_EARLIEST = date(2016, 4, 20)
_ACCOUNTS: list[dict[str, Any]] = [
    {
        "account_name": "AAA-ISA",
        "position_ladder": {"from_date": _EARLIEST.isoformat(), "to_date": "2026-09-22"},
    },
    {"account_name": "NO-LADDER", "position_ladder": None},
]


def _years_after(start: date, years: int) -> date:
    return start.replace(year=start.year + years)


def _state(store, target: date, account: str = "AAA-ISA"):
    return next_periodicity_state(store, _ACCOUNTS, account, target, _CONFIG)


def test_derives_year_for_long_span() -> None:
    assert _state(None, date(2027, 4, 20)) == {"value": "annual", "explicit": False}


@pytest.mark.parametrize(
    ("years", "expected_key"),
    [(1, "day"), (3, "month"), (5, "quarter")],
)
def test_boundary_spans_take_the_finer_interval(years: int, expected_key: str) -> None:
    target = _years_after(_EARLIEST, years)
    assert _state(None, target)["value"] == _CONFIG.value_for_key(expected_key)


def test_just_over_five_years_is_annual() -> None:
    target = _years_after(_EARLIEST, 5) + timedelta(days=1)
    assert _state(None, target)["value"] == _CONFIG.value_for_key("year")


def test_explicit_state_is_returned_unchanged() -> None:
    explicit = {"value": "month", "explicit": True}
    assert _state(explicit, date(2046, 4, 20)) == explicit


def test_missing_account_or_ladder_yields_no_value() -> None:
    expected = {"value": None, "explicit": False}
    assert _state(None, date(2030, 1, 1), account="NO-LADDER") == expected
    assert _state(None, date(2030, 1, 1), account="UNKNOWN") == expected


def test_missing_account_keeps_an_explicit_state() -> None:
    explicit = {"value": "quarter", "explicit": True}
    assert _state(explicit, date(2030, 1, 1), account="UNKNOWN") == explicit


def test_week_is_never_derived() -> None:
    week = _CONFIG.value_for_key("week")
    for days in (1, 7, 30, 365, 366, 1095, 1826, 3650, 14600):
        assert _state(None, _EARLIEST + timedelta(days=days))["value"] != week


def test_derived_state_is_never_explicit() -> None:
    for store in (None, {"value": "day", "explicit": False}):
        assert _state(store, date(2036, 4, 20))["explicit"] is False


def test_derive_after_explicit_click_leaves_state_unchanged() -> None:
    clicked = explicit_state_for_click("month", _CONFIG)
    assert _state(clicked, date(2046, 4, 20)) == clicked
    assert _state(clicked, date(2017, 1, 1)) == clicked


def test_new_span_replaces_a_derived_value() -> None:
    first = _state(None, date(2046, 4, 20))
    second = _state(first, date(2016, 10, 20))
    assert first["value"] == "annual"
    assert second == {"value": "day", "explicit": False}


def test_click_maps_key_to_service_value() -> None:
    assert explicit_state_for_click("month", _CONFIG) == {"value": "month", "explicit": True}
    assert explicit_state_for_click("year", _CONFIG) == {"value": "annual", "explicit": True}


def test_click_with_unknown_key_raises() -> None:
    with pytest.raises(KeyError):
        explicit_state_for_click("fortnight", _CONFIG)


def test_projection_button_ids_are_page_scoped_and_complete() -> None:
    projection_ids = {periodicity_component_id("projection", o.key) for o in _CONFIG.options}
    other_ids = {
        periodicity_component_id(page, o.key)
        for page in ("overview", "positions")
        for o in _CONFIG.options
    }
    assert len(projection_ids) == len(_CONFIG.options)
    assert projection_ids.isdisjoint(other_ids)
