from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.modes.consolidate_journals.constants import JOURNAL_COLUMNS
from src.modes.create_ledger.mode import CreateLedgerMode


def _empty_journal_df() -> pd.DataFrame:
    return pd.DataFrame(columns=JOURNAL_COLUMNS)


def _make_context(correlation_id: str = "test-id") -> MagicMock:
    ctx = MagicMock()
    ctx.correlation_id = correlation_id
    return ctx


class TestModeAttributes:
    def test_name(self) -> None:
        assert CreateLedgerMode.name == "create_ledger"

    def test_description_nonempty(self) -> None:
        assert CreateLedgerMode.description
        assert len(CreateLedgerMode.description) > 0


class TestRegisterArguments:
    def _parser(self) -> argparse.ArgumentParser:
        p = argparse.ArgumentParser()
        CreateLedgerMode().register_arguments(p)
        return p

    def test_input_path_declared(self) -> None:
        help_text = self._parser().format_help()
        assert "input_path" in help_text.lower() or "INPUT_PATH" in help_text

    def test_output_path_declared(self) -> None:
        help_text = self._parser().format_help()
        assert "output_path" in help_text.lower() or "OUTPUT_PATH" in help_text

    def test_missing_args_exits_nonzero(self) -> None:
        with pytest.raises(SystemExit) as exc:
            self._parser().parse_args([])
        assert exc.value.code != 0


class TestExecute:
    def _args(self, tmp_path: Path, input_exists: bool = True) -> argparse.Namespace:
        if input_exists:
            input_path = tmp_path / "input.xlsx"
            _empty_journal_df().to_excel(input_path, index=False, engine="openpyxl")
        else:
            input_path = tmp_path / "does_not_exist.xlsx"
        return argparse.Namespace(
            input_path=str(input_path),
            output_path=str(tmp_path / "output.xlsx"),
        )

    def test_missing_input_returns_exit_code_2(self, tmp_path: Path) -> None:
        mode = CreateLedgerMode()
        args = self._args(tmp_path, input_exists=False)
        result = mode.execute(_make_context(), args)
        assert result == 2

    def test_invalid_schema_returns_exit_code_2(self, tmp_path: Path) -> None:
        bad_input = tmp_path / "bad.xlsx"
        pd.DataFrame({"col1": [1]}).to_excel(bad_input, index=False, engine="openpyxl")
        args = argparse.Namespace(
            input_path=str(bad_input),
            output_path=str(tmp_path / "out.xlsx"),
        )
        result = CreateLedgerMode().execute(_make_context(), args)
        assert result == 2

    def test_valid_input_returns_exit_code_0(self, tmp_path: Path) -> None:
        mode = CreateLedgerMode()
        args = self._args(tmp_path, input_exists=True)
        result = mode.execute(_make_context(), args)
        assert result == 0

    def test_valid_input_creates_output_file(self, tmp_path: Path) -> None:
        mode = CreateLedgerMode()
        args = self._args(tmp_path, input_exists=True)
        mode.execute(_make_context(), args)
        assert Path(args.output_path).exists()
