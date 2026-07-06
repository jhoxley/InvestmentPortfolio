from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from pytest_bdd import given, parsers, scenario, then, when

FEATURE_FILE = str(Path(__file__).parent.parent / "help_system.feature")
PIPELINE_PATH = Path(__file__).parent.parent.parent.parent / "pipeline.py"


@scenario(FEATURE_FILE, "Invoking with no arguments shows top-level help")
def test_no_args_shows_help() -> None:
    pass


@scenario(FEATURE_FILE, "Invoking with --help shows top-level help")
def test_help_flag_shows_help() -> None:
    pass


@scenario(FEATURE_FILE, "Top-level help lists every registered mode")
def test_help_lists_all_modes() -> None:
    pass


@scenario(FEATURE_FILE, "Invoking a mode with --help shows mode argument list")
def test_mode_help_shows_arguments() -> None:
    pass


@scenario(FEATURE_FILE, "Mode help shows required status for each argument")
def test_mode_help_shows_required() -> None:
    pass


@given("the pipeline entrypoint exists", target_fixture="pipeline_path")
def pipeline_path() -> Path:
    assert PIPELINE_PATH.exists(), f"pipeline.py not found at {PIPELINE_PATH}"
    return PIPELINE_PATH


@when("I invoke the pipeline with no arguments", target_fixture="result")
def invoke_no_args(pipeline_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(pipeline_path)],
        capture_output=True,
        text=True,
    )


@when(parsers.parse('I invoke the pipeline with arguments "{args_str}"'), target_fixture="result")
def invoke_with_args(pipeline_path: Path, args_str: str) -> subprocess.CompletedProcess[str]:
    args = args_str.split()
    return subprocess.run(
        [sys.executable, str(pipeline_path), *args],
        capture_output=True,
        text=True,
    )


@then("the exit code is 0")
def exit_code_zero(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, (
        f"Expected exit 0, got {result.returncode}.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


@then(parsers.parse('the output contains the word "{word}"'))
def output_contains_word(result: subprocess.CompletedProcess[str], word: str) -> None:
    combined = result.stdout + result.stderr
    assert word in combined, f"Expected '{word}' in output:\n{combined}"


@then("the output contains a mode description")
def output_contains_description(result: subprocess.CompletedProcess[str]) -> None:
    combined = result.stdout + result.stderr
    assert "Placeholder" in combined or "validation" in combined or "framework" in combined, (
        f"Expected a mode description in output:\n{combined}"
    )


@then(parsers.parse('the output contains the argument name "{arg_name}"'))
def output_contains_arg(result: subprocess.CompletedProcess[str], arg_name: str) -> None:
    combined = result.stdout + result.stderr
    assert arg_name in combined, f"Expected '{arg_name}' in output:\n{combined}"


@then("the output contains a description for the argument")
def output_contains_arg_description(result: subprocess.CompletedProcess[str]) -> None:
    combined = result.stdout + result.stderr
    assert "Validates" in combined or "message" in combined.lower(), (
        f"Expected argument description in output:\n{combined}"
    )
