from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from src.context import ExecutionContext
from src.modes.example.mode import ExampleMode
from src.registry import ModeRegistry

PIPELINE_PATH = Path(__file__).parent.parent / "pipeline.py"


@pytest.fixture
def example_registry() -> ModeRegistry:
    registry = ModeRegistry()
    registry.register(ExampleMode())
    return registry


@pytest.fixture
def base_context() -> ExecutionContext:
    return ExecutionContext.create(mode_name="example", raw_args=["example", "--message", "test"])


RunPipelineFn = Callable[..., subprocess.CompletedProcess[str]]


@pytest.fixture
def run_pipeline() -> RunPipelineFn:
    def _run(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(PIPELINE_PATH), *args],
            capture_output=True,
            text=True,
        )

    return _run
