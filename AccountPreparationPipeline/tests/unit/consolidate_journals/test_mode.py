from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.modes.consolidate_journals.mode import ConsolidateJournalsMode
from src.modes.consolidate_journals.schema import ConsolidationSummary


class TestModeAttributes:
    def test_name(self) -> None:
        assert ConsolidateJournalsMode.name == "consolidate_journals"

    def test_description_nonempty(self) -> None:
        assert ConsolidateJournalsMode.description
        assert len(ConsolidateJournalsMode.description) > 0


class TestRegisterArguments:
    def _parser_with_mode(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser()
        ConsolidateJournalsMode().register_arguments(parser)
        return parser

    def test_journal_path_argument_declared(self) -> None:
        parser = self._parser_with_mode()
        help_text = parser.format_help()
        assert "journal_path" in help_text or "journal" in help_text.lower()

    def test_fragments_dir_argument_declared(self) -> None:
        parser = self._parser_with_mode()
        help_text = parser.format_help()
        assert "fragments_dir" in help_text or "fragment" in help_text.lower()

    def test_method_argument_declared(self) -> None:
        parser = self._parser_with_mode()
        help_text = parser.format_help()
        assert "method" in help_text.lower()

    def test_account_argument_declared(self) -> None:
        parser = self._parser_with_mode()
        help_text = parser.format_help()
        assert "account" in help_text.lower()

    def test_missing_all_args_exits_nonzero(self) -> None:
        parser = self._parser_with_mode()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args([])
        assert exc_info.value.code != 0


class TestExecute:
    def _build_args(
        self,
        tmp_path: Path,
        method: str = "HL",
        account: str = "My ISA",
    ) -> argparse.Namespace:
        frags_dir = tmp_path / "frags"
        frags_dir.mkdir()
        return argparse.Namespace(
            journal_path=str(tmp_path / "journal.xlsx"),
            fragments_dir=str(frags_dir),
            method=method,
            account=account,
        )

    def _make_context(self) -> MagicMock:
        ctx = MagicMock()
        ctx.correlation_id = "test-corr-id"
        return ctx

    def test_invalid_method_returns_exit_code_2(self, tmp_path: Path) -> None:
        mode = ConsolidateJournalsMode()
        args = self._build_args(tmp_path, method="UNKNOWN")
        result = mode.execute(self._make_context(), args)
        assert result == 2

    def test_nonexistent_fragments_dir_returns_exit_code_2(self, tmp_path: Path) -> None:
        mode = ConsolidateJournalsMode()
        args = self._build_args(tmp_path)
        args.fragments_dir = str(tmp_path / "does_not_exist")
        result = mode.execute(self._make_context(), args)
        assert result == 2

    def test_valid_args_returns_exit_code_0(self, tmp_path: Path) -> None:
        mode = ConsolidateJournalsMode()
        args = self._build_args(tmp_path)
        summary = ConsolidationSummary(
            files_processed=0,
            events_inserted=0,
            events_merged=0,
            events_removed=0,
            errors=[],
        )
        with patch("src.modes.consolidate_journals.mode.ConsolidationEngine") as mock_engine_cls:
            mock_engine_cls.return_value.run.return_value = summary
            result = mode.execute(self._make_context(), args)
        assert result == 0


class TestRenderSummary:
    def test_no_errors_renders_none(self) -> None:
        from src.modes.consolidate_journals.mode import render_summary

        summary = ConsolidationSummary(
            files_processed=3,
            events_inserted=10,
            events_merged=2,
            events_removed=0,
            errors=[],
        )
        output = render_summary(summary)
        assert "ERRORS" in output
        assert "None" in output

    def test_errors_listed_with_file_and_line(self) -> None:
        from pathlib import Path

        from src.modes.consolidate_journals.mode import render_summary
        from src.modes.consolidate_journals.schema import ParseError

        err = ParseError(file_path=Path("bad_file.csv"), line_number=7, message="bad value")
        summary = ConsolidationSummary(
            files_processed=1,
            events_inserted=0,
            events_merged=0,
            events_removed=0,
            errors=[err],
        )
        output = render_summary(summary)
        assert "bad_file.csv" in output
        assert "7" in output
        assert "bad value" in output

    def test_file_level_error_no_line_number(self) -> None:
        from pathlib import Path

        from src.modes.consolidate_journals.mode import render_summary
        from src.modes.consolidate_journals.schema import ParseError

        err = ParseError(file_path=Path("no_header.csv"), line_number=None, message="no header")
        summary = ConsolidationSummary(
            files_processed=1,
            events_inserted=0,
            events_merged=0,
            events_removed=0,
            errors=[err],
        )
        output = render_summary(summary)
        assert "no_header.csv" in output
        assert "no header" in output

    def test_success_counts_shown(self) -> None:
        from src.modes.consolidate_journals.mode import render_summary

        summary = ConsolidationSummary(
            files_processed=5,
            events_inserted=42,
            events_merged=3,
            events_removed=0,
            errors=[],
        )
        output = render_summary(summary)
        assert "42" in output
        assert "5" in output
