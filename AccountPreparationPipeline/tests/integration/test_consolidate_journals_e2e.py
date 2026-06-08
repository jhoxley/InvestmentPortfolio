from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from src.modes.consolidate_journals.constants import JOURNAL_COLUMNS

PIPELINE = Path(__file__).parent.parent.parent / "pipeline.py"
DATA_DIR = Path(__file__).parent.parent / "data" / "consolidate_journals"


def run_consolidate(
    journal_path: Path,
    frags_dir: Path,
    method: str = "HL",
    account: str = "Test ISA",
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(PIPELINE),
            "consolidate_journals",
            str(journal_path),
            str(frags_dir),
            method,
            account,
        ],
        capture_output=True,
        text=True,
    )


class TestUS1FirstTimeConsolidation:
    def test_creates_xlsx_from_valid_hl_csv(self, tmp_path: Path) -> None:
        result = run_consolidate(tmp_path / "journal.xlsx", DATA_DIR)
        assert result.returncode == 0, result.stderr
        assert (tmp_path / "journal.xlsx").exists()

    def test_output_has_correct_columns(self, tmp_path: Path) -> None:
        journal_path = tmp_path / "journal.xlsx"
        run_consolidate(journal_path, DATA_DIR)
        df = pd.read_excel(journal_path, engine="openpyxl")
        assert list(df.columns) == JOURNAL_COLUMNS

    def test_account_column_populated_from_argument(self, tmp_path: Path) -> None:
        journal_path = tmp_path / "journal.xlsx"
        run_consolidate(journal_path, DATA_DIR, account="My Special ISA")
        df = pd.read_excel(journal_path, engine="openpyxl")
        valid_rows = df[df["account"] == "My Special ISA"]
        assert len(valid_rows) > 0

    def test_stdout_contains_success_section(self, tmp_path: Path) -> None:
        result = run_consolidate(tmp_path / "journal.xlsx", DATA_DIR)
        assert "SUCCESS" in result.stdout

    def test_stdout_contains_errors_section(self, tmp_path: Path) -> None:
        result = run_consolidate(tmp_path / "journal.xlsx", DATA_DIR)
        assert "ERRORS" in result.stdout

    def test_mode_listed_in_help(self) -> None:
        result = subprocess.run(
            [sys.executable, str(PIPELINE), "--help"],
            capture_output=True,
            text=True,
        )
        assert "consolidate_journals" in result.stdout + result.stderr

    def test_unrecognised_method_exits_2(self, tmp_path: Path) -> None:
        frags_dir = tmp_path / "frags"
        frags_dir.mkdir()
        result = run_consolidate(tmp_path / "j.xlsx", frags_dir, method="BADMETHOD")
        assert result.returncode == 2

    def test_nonexistent_frags_dir_exits_2(self, tmp_path: Path) -> None:
        result = run_consolidate(tmp_path / "j.xlsx", tmp_path / "nope")
        assert result.returncode == 2


class TestUS2IncrementalUpdate:
    def test_second_run_inserts_zero(self, tmp_path: Path) -> None:
        frags_dir = tmp_path / "frags"
        frags_dir.mkdir()
        shutil.copy(DATA_DIR / "valid_hl_simple.csv", frags_dir / "valid_hl_simple.csv")
        journal_path = tmp_path / "journal.xlsx"
        run_consolidate(journal_path, frags_dir)
        result2 = run_consolidate(journal_path, frags_dir)
        assert result2.returncode == 0
        assert "Events inserted:  0" in result2.stdout

    def test_new_csv_adds_events(self, tmp_path: Path) -> None:
        frags_dir1 = tmp_path / "frags1"
        frags_dir1.mkdir()
        shutil.copy(DATA_DIR / "valid_hl_simple.csv", frags_dir1 / "valid_hl_simple.csv")
        journal_path = tmp_path / "journal.xlsx"
        run_consolidate(journal_path, frags_dir1)

        frags_dir2 = tmp_path / "frags2"
        frags_dir2.mkdir()
        shutil.copy(DATA_DIR / "valid_hl_contrib.csv", frags_dir2 / "valid_hl_contrib.csv")
        result2 = run_consolidate(journal_path, frags_dir2)
        assert result2.returncode == 0
        df = pd.read_excel(journal_path, engine="openpyxl")
        assert len(df) == 8


class TestUS3ErrorHandling:
    def test_mixed_valid_invalid_exits_0(self, tmp_path: Path) -> None:
        frags_dir = tmp_path / "frags"
        frags_dir.mkdir()
        shutil.copy(DATA_DIR / "valid_hl_simple.csv", frags_dir / "valid_hl_simple.csv")
        shutil.copy(DATA_DIR / "invalid_no_header.csv", frags_dir / "invalid_no_header.csv")
        result = run_consolidate(tmp_path / "journal.xlsx", frags_dir)
        assert result.returncode == 0

    def test_invalid_file_named_in_errors_section(self, tmp_path: Path) -> None:
        frags_dir = tmp_path / "frags"
        frags_dir.mkdir()
        shutil.copy(DATA_DIR / "invalid_no_header.csv", frags_dir / "invalid_no_header.csv")
        result = run_consolidate(tmp_path / "journal.xlsx", frags_dir)
        assert "invalid_no_header" in result.stdout

    def test_valid_events_present_despite_invalid_file(self, tmp_path: Path) -> None:
        frags_dir = tmp_path / "frags"
        frags_dir.mkdir()
        shutil.copy(DATA_DIR / "valid_hl_simple.csv", frags_dir / "valid_hl_simple.csv")
        shutil.copy(DATA_DIR / "invalid_no_header.csv", frags_dir / "invalid_no_header.csv")
        journal_path = tmp_path / "journal.xlsx"
        run_consolidate(journal_path, frags_dir)
        df = pd.read_excel(journal_path, engine="openpyxl")
        assert len(df) == 6


class TestUSOffsets:
    def test_buy_generates_offset_row(self, tmp_path: Path) -> None:
        frags_dir = tmp_path / "frags"
        frags_dir.mkdir()
        shutil.copy(DATA_DIR / "valid_hl_simple.csv", frags_dir / "valid_hl_simple.csv")
        journal_path = tmp_path / "journal.xlsx"
        result = run_consolidate(journal_path, frags_dir)
        assert result.returncode == 0
        df = pd.read_excel(journal_path, engine="openpyxl")
        offset_rows = df[df["action"] == "trading"]
        assert len(offset_rows) == 3
        buy_offset = offset_rows[offset_rows["reference"] == "B12345-offset"]
        assert len(buy_offset) == 1
        assert buy_offset.iloc[0]["sub_account"] == "Cash"
        assert buy_offset.iloc[0]["value"] == pytest.approx(-2000.0)
        assert buy_offset.iloc[0]["quantity"] == pytest.approx(-2000.0)

    def test_sell_generates_offset_with_positive_value(self, tmp_path: Path) -> None:
        frags_dir = tmp_path / "frags"
        frags_dir.mkdir()
        shutil.copy(DATA_DIR / "valid_hl_simple.csv", frags_dir / "valid_hl_simple.csv")
        journal_path = tmp_path / "journal.xlsx"
        run_consolidate(journal_path, frags_dir)
        df = pd.read_excel(journal_path, engine="openpyxl")
        sell_offset = df[df["reference"] == "S67890-offset"]
        assert len(sell_offset) == 1
        assert sell_offset.iloc[0]["value"] == pytest.approx(75.0)
        assert sell_offset.iloc[0]["quantity"] == pytest.approx(75.0)

    def test_deposit_generates_no_offset(self, tmp_path: Path) -> None:
        frags_dir = tmp_path / "frags"
        frags_dir.mkdir()
        shutil.copy(DATA_DIR / "valid_hl_contrib.csv", frags_dir / "valid_hl_contrib.csv")
        journal_path = tmp_path / "journal.xlsx"
        run_consolidate(journal_path, frags_dir)
        df = pd.read_excel(journal_path, engine="openpyxl")
        assert len(df[df["action"] == "trading"]) == 0

    def test_backfill_existing_trade(self, tmp_path: Path) -> None:
        journal_path = tmp_path / "journal.xlsx"
        pd.DataFrame(
            [
                {
                    "date": "2024-01-15",
                    "account": "Test ISA",
                    "sub_account": "Vanguard Fund",
                    "action": "buy",
                    "reference": "B12345",
                    "value": 2000.0,
                    "quantity": 10.0,
                }
            ],
            columns=JOURNAL_COLUMNS,
        ).to_excel(journal_path, index=False, engine="openpyxl")
        frags_dir = tmp_path / "frags"
        frags_dir.mkdir()
        result = run_consolidate(journal_path, frags_dir)
        assert result.returncode == 0
        df = pd.read_excel(journal_path, engine="openpyxl")
        assert len(df[df["action"] == "trading"]) == 1
        assert df[df["action"] == "trading"].iloc[0]["reference"] == "B12345-offset"

    def test_rerun_does_not_duplicate_offsets(self, tmp_path: Path) -> None:
        frags_dir = tmp_path / "frags"
        frags_dir.mkdir()
        shutil.copy(DATA_DIR / "valid_hl_simple.csv", frags_dir / "valid_hl_simple.csv")
        journal_path = tmp_path / "journal.xlsx"
        run_consolidate(journal_path, frags_dir)
        run_consolidate(journal_path, frags_dir)
        df = pd.read_excel(journal_path, engine="openpyxl")
        assert len(df) == 6
        assert len(df[df["action"] == "trading"]) == 3

    def test_incremental_run_adds_only_new_offsets(self, tmp_path: Path) -> None:
        frags_dir1 = tmp_path / "frags1"
        frags_dir1.mkdir()
        shutil.copy(DATA_DIR / "valid_hl_simple.csv", frags_dir1 / "valid_hl_simple.csv")
        journal_path = tmp_path / "journal.xlsx"
        run_consolidate(journal_path, frags_dir1)

        frags_dir2 = tmp_path / "frags2"
        frags_dir2.mkdir()
        shutil.copy(DATA_DIR / "valid_hl_contrib.csv", frags_dir2 / "valid_hl_contrib.csv")
        run_consolidate(journal_path, frags_dir2)

        df = pd.read_excel(journal_path, engine="openpyxl")
        assert len(df) == 8
        assert len(df[df["action"] == "trading"]) == 3

    def test_summary_includes_offset_count(self, tmp_path: Path) -> None:
        frags_dir = tmp_path / "frags"
        frags_dir.mkdir()
        shutil.copy(DATA_DIR / "valid_hl_simple.csv", frags_dir / "valid_hl_simple.csv")
        journal_path = tmp_path / "journal.xlsx"
        result = run_consolidate(journal_path, frags_dir)
        assert "Events inserted:  6" in result.stdout
