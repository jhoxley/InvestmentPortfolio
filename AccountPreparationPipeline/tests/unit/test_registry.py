from __future__ import annotations

import pytest

from src.modes.example.mode import ExampleMode
from src.registry import ModeRegistry


@pytest.fixture
def registry() -> ModeRegistry:
    return ModeRegistry()


@pytest.fixture
def populated_registry() -> ModeRegistry:
    reg = ModeRegistry()
    reg.register(ExampleMode())
    return reg


def test_register_adds_mode(registry: ModeRegistry) -> None:
    registry.register(ExampleMode())
    assert registry.contains("example")


def test_register_duplicate_raises(registry: ModeRegistry) -> None:
    registry.register(ExampleMode())
    with pytest.raises(ValueError, match="already registered"):
        registry.register(ExampleMode())


def test_get_returns_registered_mode(populated_registry: ModeRegistry) -> None:
    mode = populated_registry.get("example")
    assert mode.name == "example"


def test_get_unknown_raises_key_error(registry: ModeRegistry) -> None:
    with pytest.raises(KeyError):
        registry.get("nonexistent")


def test_list_all_returns_sorted(registry: ModeRegistry) -> None:
    registry.register(ExampleMode())
    modes = registry.list_all()
    assert len(modes) == 1
    assert modes[0].name == "example"


def test_list_all_empty(registry: ModeRegistry) -> None:
    assert registry.list_all() == []


def test_contains_true(populated_registry: ModeRegistry) -> None:
    assert populated_registry.contains("example") is True


def test_contains_false(registry: ModeRegistry) -> None:
    assert registry.contains("nonexistent") is False
