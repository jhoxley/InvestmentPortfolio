from __future__ import annotations

import argparse

from src.modes.example.mode import ExampleMode


def test_mode_name() -> None:
    assert ExampleMode.name == "example"


def test_mode_description_nonempty() -> None:
    assert ExampleMode.description
    assert len(ExampleMode.description) > 0


def test_register_arguments_adds_message_arg() -> None:
    parser = argparse.ArgumentParser()
    mode = ExampleMode()
    mode.register_arguments(parser)
    help_text = parser.format_help()
    assert "--message" in help_text


def test_message_argument_is_required() -> None:
    parser = argparse.ArgumentParser()
    ExampleMode().register_arguments(parser)
    try:
        parser.parse_args([])
        raise AssertionError("Should have raised SystemExit for missing --message")
    except SystemExit as exc:
        assert exc.code != 0


def test_message_argument_has_help_text() -> None:
    parser = argparse.ArgumentParser()
    ExampleMode().register_arguments(parser)
    help_text = parser.format_help()
    assert "message" in help_text.lower()
    assert len([line for line in help_text.splitlines() if "--message" in line]) > 0
