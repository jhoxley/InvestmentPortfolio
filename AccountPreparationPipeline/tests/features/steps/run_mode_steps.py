from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from pytest_bdd import given, parsers, scenario, then, when

FEATURE_FILE = str(Path(__file__).parent.parent / "run_mode.feature")
PIPELINE_PATH = Path(__file__).parent.parent.parent.parent / "pipeline.py"


@scenario(FEATURE_FILE, "Valid mode with valid arguments exits successfully")
def test_valid_mode_exits_successfully() -> None:
    pass


@scenario(FEATURE_FILE, "Valid mode with missing required argument exits with error")
def test_missing_required_argument_exits_with_error() -> None:
    pass


@scenario(FEATURE_FILE, "Valid mode with unrecognised argument exits with error")
def test_unrecognised_argument_exits_with_error() -> None:
    pass


@given("the pipeline entrypoint exists", target_fixture="pipeline_path")
def pipeline_path() -> Path:
    assert PIPELINE_PATH.exists(), f"pipeline.py not found at {PIPELINE_PATH}"
    return PIPELINE_PATH


@when(parsers.parse('I invoke the pipeline with arguments "{args_str}"'), target_fixture="result")
def invoke_pipeline(pipeline_path: Path, args_str: str) -> subprocess.CompletedProcess[str]:
    args = args_str.split()
    return subprocess.run(
        [sys.executable, str(pipeline_path), *args],
        capture_output=True,
        text=True,
    )


@then("the exit code is 0")
def check_exit_zero(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, (
        f"Expected exit 0, got {result.returncode}.\nstderr: {result.stderr}"
    )


@then("the exit code is not 0")
def check_exit_nonzero(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode != 0, f"Expected non-zero exit, got 0.\nstdout: {result.stdout}"


@then("the log output contains a JSON log entry")
def check_json_log(result: subprocess.CompletedProcess[str]) -> None:
    lines = [line.strip() for line in result.stderr.splitlines() if line.strip()]
    assert lines, "No log output found on stderr"
    parsed = False
    for line in lines:
        try:
            json.loads(line)
            parsed = True
            break
        except json.JSONDecodeError:
            continue
    assert parsed, f"No valid JSON log entry found in stderr:\n{result.stderr}"


@then("the log output contains a metrics record")
def check_metrics_record(result: subprocess.CompletedProcess[str]) -> None:
    lines = [line.strip() for line in result.stderr.splitlines() if line.strip()]
    found = False
    for line in lines:
        try:
            record = json.loads(line)
            if record.get("event") == "metrics":
                found = True
                break
        except json.JSONDecodeError:
            continue
    assert found, f"No metrics record (event='metrics') found in stderr:\n{result.stderr}"


@then("the error output mentions the missing argument")
def check_error_mentions_message(result: subprocess.CompletedProcess[str]) -> None:
    combined = result.stderr + result.stdout
    assert "--message" in combined or "message" in combined.lower(), (
        f"Expected '--message' in error output.\nstderr: {result.stderr}\nstdout: {result.stdout}"
    )
