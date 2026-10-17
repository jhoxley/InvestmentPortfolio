"""Unit tests for the shared Periodicity control builder (021).

Browser-free: the builder returns plain Dash component objects, so its
structure, its per-page ids and its active-state rendering are all assertable
without a running app.
"""

from __future__ import annotations

from typing import Any

import pytest

from config.content import PeriodicityConfig
from src.components.periodicity_controls import (
    build_periodicity_control,
    periodicity_button_states,
    periodicity_component_id,
)

_CONFIG = PeriodicityConfig.model_validate(
    {
        "label": "Periodicity",
        "options": [
            {"key": "day", "label": "day", "value": "day"},
            {"key": "week", "label": "week", "value": "week"},
            {"key": "month", "label": "month", "value": "month"},
            {"key": "quarter", "label": "quarter", "value": "quarter"},
            {"key": "year", "label": "year", "value": "annual"},
        ],
        "thresholds": {
            "day_max_years": 1,
            "month_max_years": 3,
            "quarter_max_years": 5,
        },
    }
)


def _flatten(node: Any, out: list[Any]) -> None:
    """Collect every Dash component instance in a built control tree."""
    out.append(node)
    children = getattr(node, "children", None)
    if isinstance(children, list):
        for child in children:
            _flatten(child, out)
    elif children is not None and hasattr(children, "children"):
        _flatten(children, out)


def _buttons(page_prefix: str) -> list[Any]:
    """Return the built control's buttons, in built order."""
    nodes: list[Any] = []
    for col in build_periodicity_control(page_prefix, _CONFIG):
        _flatten(col, nodes)
    return [
        n
        for n in nodes
        if isinstance(getattr(n, "id", None), str)
        and n.id.startswith(f"{page_prefix}-parameters-periodicity-")
        and n.id
        not in (
            f"{page_prefix}-parameters-periodicity-group",
            f"{page_prefix}-parameters-periodicity-label",
        )
    ]


class TestControlStructure:
    """The control must present the configured label and exactly five options."""

    def test_label_comes_from_config(self) -> None:
        nodes: list[Any] = []
        for col in build_periodicity_control("overview", _CONFIG):
            _flatten(col, nodes)
        label = next(
            n for n in nodes if getattr(n, "id", None) == "overview-parameters-periodicity-label"
        )
        assert label.children == "Periodicity"

    def test_exactly_five_buttons_in_config_order(self) -> None:
        buttons = _buttons("overview")
        assert len(buttons) == 5
        assert [b.children for b in buttons] == ["day", "week", "month", "quarter", "year"]


class TestPerPageIds:
    """Ids must be page-scoped so two pages' callbacks can never collide (020's lesson)."""

    def test_same_call_yields_distinct_ids_per_page(self) -> None:
        overview = {b.id for b in _buttons("overview")}
        positions = {b.id for b in _buttons("positions")}

        assert "overview-parameters-periodicity-month" in overview
        assert "positions-parameters-periodicity-month" in positions
        assert overview.isdisjoint(positions)

    def test_no_id_uses_the_shared_app_parameters_namespace(self) -> None:
        """A shared `app-parameters-*` id is what caused feature 020's collision."""
        for page_prefix in ("overview", "positions"):
            nodes: list[Any] = []
            for col in build_periodicity_control(page_prefix, _CONFIG):
                _flatten(col, nodes)
            for node in nodes:
                node_id = getattr(node, "id", None)
                if isinstance(node_id, str):
                    assert not node_id.startswith("app-parameters-"), node_id

    def test_component_id_helper_matches_built_ids(self) -> None:
        assert (
            periodicity_component_id("positions", "quarter")
            == "positions-parameters-periodicity-quarter"
        )


class TestActiveState:
    """Exactly one button is highlighted, and it is the effective interval (FR-011)."""

    @pytest.mark.parametrize("effective_key", ["day", "week", "month", "quarter", "year"])
    def test_exactly_one_button_is_active(self, effective_key: str) -> None:
        states = periodicity_button_states(effective_key, _CONFIG)

        assert [s["active"] for s in states].count(True) == 1
        assert [s["outline"] for s in states].count(False) == 1
        active_index = [s["active"] for s in states].index(True)
        assert [o.key for o in _CONFIG.options][active_index] == effective_key

    def test_states_are_returned_in_config_order(self) -> None:
        states = periodicity_button_states("month", _CONFIG)
        assert len(states) == len(_CONFIG.options)
        assert states[2]["active"] is True
        assert states[2]["outline"] is False
        for index in (0, 1, 3, 4):
            assert states[index]["active"] is False
            assert states[index]["outline"] is True

    def test_accepts_a_service_side_value_as_well_as_a_key(self) -> None:
        """The store holds the service-side value (`annual`), not the UI key (`year`)."""
        by_value = periodicity_button_states("annual", _CONFIG)
        by_key = periodicity_button_states("year", _CONFIG)
        assert by_value == by_key

    def test_unknown_effective_value_highlights_nothing_rather_than_raising(self) -> None:
        states = periodicity_button_states("fortnight", _CONFIG)
        assert all(s["active"] is False for s in states)
