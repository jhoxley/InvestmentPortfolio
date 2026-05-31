from __future__ import annotations

import argparse

import pytest

from src.modes.example.mode import ExampleMode
from src.registry import ModeRegistry


def _build_parser_for_test(registry: ModeRegistry) -> argparse.ArgumentParser:
    from pipeline import _build_parser

    return _build_parser(registry)


@pytest.fixture
def populated_registry() -> ModeRegistry:
    reg = ModeRegistry()
    reg.register(ExampleMode())
    return reg


def test_parser_includes_all_mode_names(populated_registry: ModeRegistry) -> None:
    parser = _build_parser_for_test(populated_registry)
    help_text = parser.format_help()
    assert "example" in help_text


def test_parser_includes_mode_description(populated_registry: ModeRegistry) -> None:
    parser = _build_parser_for_test(populated_registry)
    help_text = parser.format_help()
    assert ExampleMode().description in help_text or "Placeholder" in help_text


def test_parser_includes_log_level_option(populated_registry: ModeRegistry) -> None:
    parser = _build_parser_for_test(populated_registry)
    help_text = parser.format_help()
    assert "--log-level" in help_text
