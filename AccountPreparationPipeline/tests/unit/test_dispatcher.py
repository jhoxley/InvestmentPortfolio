from __future__ import annotations

from argparse import Namespace
from unittest.mock import MagicMock

import pytest

from src.constants import EXIT_EXECUTION_FAILURE, EXIT_SUCCESS, EXIT_UNKNOWN_MODE
from src.context import ExecutionContext
from src.dispatcher import dispatch
from src.modes.example.mode import ExampleMode
from src.registry import ModeRegistry


@pytest.fixture
def registry() -> ModeRegistry:
    reg = ModeRegistry()
    reg.register(ExampleMode())
    return reg


@pytest.fixture
def context() -> ExecutionContext:
    return ExecutionContext.create(mode_name="example", raw_args=["example", "--message", "hi"])


def test_dispatch_valid_mode_returns_exit_code(
    registry: ModeRegistry, context: ExecutionContext
) -> None:
    args = Namespace(mode="example", message="hi")
    result = dispatch(registry, context, args)
    assert result == EXIT_SUCCESS


def test_dispatch_unknown_mode_returns_unknown_code(registry: ModeRegistry) -> None:
    ctx = ExecutionContext.create(mode_name="nonexistent", raw_args=["nonexistent"])
    result = dispatch(registry, ctx, Namespace(mode="nonexistent"))
    assert result == EXIT_UNKNOWN_MODE


def test_dispatch_unknown_mode_writes_to_stderr(
    registry: ModeRegistry, capsys: pytest.CaptureFixture[str]
) -> None:
    ctx = ExecutionContext.create(mode_name="nonexistent", raw_args=["nonexistent"])
    dispatch(registry, ctx, Namespace(mode="nonexistent"))
    captured = capsys.readouterr()
    assert "nonexistent" in captured.err
    assert "example" in captured.err


def test_dispatch_exception_in_execute_returns_failure(
    registry: ModeRegistry, context: ExecutionContext
) -> None:
    failing_mode = MagicMock()
    failing_mode.name = "failing"
    failing_mode.description = "A mode that always fails"
    failing_mode.execute.side_effect = RuntimeError("boom")

    failing_registry = ModeRegistry()
    failing_registry.register(failing_mode)
    failing_context = ExecutionContext.create(mode_name="failing", raw_args=["failing"])

    result = dispatch(failing_registry, failing_context, Namespace(mode="failing"))
    assert result == EXIT_EXECUTION_FAILURE


def test_dispatch_exception_does_not_propagate(
    registry: ModeRegistry,
) -> None:
    exploding = MagicMock()
    exploding.name = "exploding"
    exploding.description = "Explodes"
    exploding.execute.side_effect = ValueError("unexpected")

    reg = ModeRegistry()
    reg.register(exploding)
    ctx = ExecutionContext.create(mode_name="exploding", raw_args=["exploding"])

    try:
        dispatch(reg, ctx, Namespace(mode="exploding"))
    except Exception:
        pytest.fail("dispatch() should not propagate exceptions from mode.execute()")
