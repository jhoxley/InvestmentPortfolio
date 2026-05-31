from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from pytest_bdd import given, parsers, scenario, then, when

FEATURE_FILE = str(Path(__file__).parent.parent / "error_handling.feature")
PIPELINE_PATH = Path(__file__).parent.parent.parent.parent / "pipeline.py"


@scenario(FEATURE_FILE, "Unrecognised mode exits with error and lists valid modes")
def test_unrecognised_mode_error() -> None:
    pass


@scenario(FEATURE_FILE, "Unrecognised mode exit code is 1")
def test_unrecognised_mode_exit_code() -> None:
    pass


@given("the pipeline entrypoint exists", target_fixture="pipeline_path")
def pipeline_path() -> Path:
    assert PIPELINE_PATH.exists()
    return PIPELINE_PATH


@when(parsers.parse('I invoke the pipeline with arguments "{args_str}"'), target_fixture="result")
def invoke_pipeline(pipeline_path: Path, args_str: str) -> subprocess.CompletedProcess[str]:
    args = args_str.split()
    return subprocess.run(
        [sys.executable, str(pipeline_path), *args],
        capture_output=True,
        text=True,
    )


@then("the exit code is not 0")
def exit_nonzero(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode != 0, f"Expected non-zero exit, got 0.\nstdout: {result.stdout}"


@then("the exit code is 1")
def exit_code_one(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 1, (
        f"Expected exit code 1, got {result.returncode}.\nstderr: {result.stderr}"
    )


@then("the error output mentions the unknown mode name")
def error_mentions_mode(result: subprocess.CompletedProcess[str]) -> None:
    assert "nonexistentmode" in result.stderr, (
        f"Expected unknown mode name in stderr:\n{result.stderr}"
    )


@then("the error output lists the valid modes")
def error_lists_valid_modes(result: subprocess.CompletedProcess[str]) -> None:
    assert "example" in result.stderr, (
        f"Expected valid mode 'example' listed in stderr:\n{result.stderr}"
    )


@then("the error output contains no traceback")
def error_has_no_traceback(result: subprocess.CompletedProcess[str]) -> None:
    assert "Traceback" not in result.stderr, f"Unexpected traceback in stderr:\n{result.stderr}"
    assert "Traceback" not in result.stdout, f"Unexpected traceback in stdout:\n{result.stdout}"
