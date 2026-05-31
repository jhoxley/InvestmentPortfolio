from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PIPELINE = Path(__file__).parent.parent.parent / "pipeline.py"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(PIPELINE), *args],
        capture_output=True,
        text=True,
    )


class TestUS1RunMode:
    def test_valid_mode_exits_zero(self) -> None:
        result = run("example", "--message", "hello")
        assert result.returncode == 0

    def test_valid_mode_produces_json_logs(self) -> None:
        result = run("example", "--message", "hello")
        lines = [ln for ln in result.stderr.splitlines() if ln.strip()]
        assert any(self._is_json(ln) for ln in lines), f"No JSON logs:\n{result.stderr}"

    def test_valid_mode_produces_metrics_record(self) -> None:
        result = run("example", "--message", "hello")
        lines = [ln for ln in result.stderr.splitlines() if ln.strip()]
        assert any(
            self._is_json(ln) and json.loads(ln).get("event") == "metrics" for ln in lines
        ), f"No metrics record:\n{result.stderr}"

    def test_metrics_record_has_required_fields(self) -> None:
        result = run("example", "--message", "hello")
        metrics = next(
            (
                json.loads(ln)
                for ln in result.stderr.splitlines()
                if ln.strip() and self._is_json(ln) and json.loads(ln).get("event") == "metrics"
            ),
            None,
        )
        assert metrics is not None
        for field in ("correlation_id", "mode_name", "duration_seconds", "exit_status"):
            assert field in metrics, f"Missing '{field}' in metrics: {metrics}"

    def test_missing_required_arg_exits_nonzero(self) -> None:
        result = run("example")
        assert result.returncode != 0

    def test_unrecognised_arg_exits_nonzero(self) -> None:
        result = run("example", "--message", "hi", "--bogus")
        assert result.returncode != 0

    @staticmethod
    def _is_json(s: str) -> bool:
        try:
            json.loads(s)
            return True
        except json.JSONDecodeError:
            return False


class TestUS2DiscoverModes:
    def test_no_args_exits_zero(self) -> None:
        result = run()
        assert result.returncode == 0

    def test_no_args_lists_example_mode(self) -> None:
        result = run()
        assert "example" in result.stdout + result.stderr

    def test_help_flag_exits_zero(self) -> None:
        result = run("--help")
        assert result.returncode == 0

    def test_help_flag_lists_example_mode(self) -> None:
        result = run("--help")
        assert "example" in result.stdout + result.stderr


class TestUS3ModeHelp:
    def test_mode_help_exits_zero(self) -> None:
        result = run("example", "--help")
        assert result.returncode == 0

    def test_mode_help_shows_message_arg(self) -> None:
        result = run("example", "--help")
        assert "--message" in result.stdout + result.stderr

    def test_mode_help_shows_description(self) -> None:
        result = run("example", "--help")
        combined = result.stdout + result.stderr
        assert "message" in combined.lower()


class TestUS4ErrorHandling:
    def test_unknown_mode_exits_nonzero(self) -> None:
        result = run("nosuchmode")
        assert result.returncode != 0

    def test_unknown_mode_exit_code_is_1(self) -> None:
        result = run("nosuchmode")
        assert result.returncode == 1

    def test_unknown_mode_no_traceback(self) -> None:
        result = run("nosuchmode")
        assert "Traceback" not in result.stderr
        assert "Traceback" not in result.stdout

    def test_unknown_mode_mentions_valid_modes(self) -> None:
        result = run("nosuchmode")
        assert "example" in result.stderr

    def test_unknown_mode_mentions_the_bad_name(self) -> None:
        result = run("nosuchmode")
        assert "nosuchmode" in result.stderr
