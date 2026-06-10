from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

PIPELINE_PATH = Path(__file__).parent.parent.parent / "pipeline.py"
JOURNAL_COLUMNS = ["date", "account", "sub_account", "action", "reference", "value", "quantity"]


def _run(input_path: Path, output_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(PIPELINE_PATH), "create_ledger", str(input_path), str(output_path)],
        capture_output=True,
        text=True,
    )


def _make_input(tmp_path: Path, rows: list[dict]) -> Path:
    df = pd.DataFrame(rows, columns=JOURNAL_COLUMNS)
    path = tmp_path / "journal.xlsx"
    df.to_excel(path, index=False, engine="openpyxl")
    return path


def _row(
    date: str = "2024-01-01",
    account: str = "ISA",
    sub_account: str = "Vanguard Fund",
    action: str = "buy",
    reference: str = "B001",
    value: float = 1000.0,
    quantity: float | None = 10.0,
) -> dict:
    return {
        "date": date,
        "account": account,
        "sub_account": sub_account,
        "action": action,
        "reference": reference,
        "value": value,
        "quantity": quantity,
    }


class TestCreateLedgerE2E:
    def test_success_exit_code(self, tmp_path: Path) -> None:
        input_path = _make_input(
            tmp_path,
            [
                _row(
                    date="2024-01-01", action="buy", value=1000.0, quantity=10.0, reference="B001"
                ),
                _row(date="2024-01-02", action="sell", value=400.0, quantity=4.0, reference="S001"),
                _row(
                    date="2024-01-03",
                    sub_account="Cash",
                    action="deposit",
                    value=500.0,
                    quantity=None,
                    reference="Deposit",
                ),
            ],
        )
        result = _run(input_path, tmp_path / "ledger.xlsx")
        assert result.returncode == 0

    def test_output_row_count_equals_input(self, tmp_path: Path) -> None:
        rows = [
            _row(date="2024-01-01", reference="B001"),
            _row(date="2024-01-02", reference="B002"),
            _row(date="2024-01-03", reference="B003"),
        ]
        input_path = _make_input(tmp_path, rows)
        output_path = tmp_path / "ledger.xlsx"
        result = _run(input_path, output_path)
        assert result.returncode == 0
        out_df = pd.read_excel(output_path, engine="openpyxl")
        assert len(out_df) == 3

    def test_cumulative_value_for_buy_sell(self, tmp_path: Path) -> None:
        input_path = _make_input(
            tmp_path,
            [
                _row(
                    date="2024-01-01", action="buy", value=1000.0, quantity=10.0, reference="B001"
                ),
                _row(date="2024-01-02", action="sell", value=400.0, quantity=4.0, reference="S001"),
            ],
        )
        output_path = tmp_path / "ledger.xlsx"
        _run(input_path, output_path)
        out_df = pd.read_excel(output_path, engine="openpyxl")
        # buy: adj_value = -1000 → cumsum = -1000
        # sell: adj_value = -400 → cumsum = -1400
        assert out_df.iloc[0]["Account Value"] == pytest.approx(-1000.0)
        assert out_df.iloc[1]["Account Value"] == pytest.approx(-1400.0)

    def test_cumulative_quantity_for_buy_sell(self, tmp_path: Path) -> None:
        input_path = _make_input(
            tmp_path,
            [
                _row(
                    date="2024-01-01", action="buy", value=1000.0, quantity=10.0, reference="B001"
                ),
                _row(date="2024-01-02", action="sell", value=400.0, quantity=4.0, reference="S001"),
            ],
        )
        output_path = tmp_path / "ledger.xlsx"
        _run(input_path, output_path)
        out_df = pd.read_excel(output_path, engine="openpyxl")
        assert out_df.iloc[0]["Account Quantity"] == pytest.approx(10.0)
        assert out_df.iloc[1]["Account Quantity"] == pytest.approx(6.0)

    def test_cash_deposit_uses_value_as_quantity(self, tmp_path: Path) -> None:
        input_path = _make_input(
            tmp_path,
            [
                _row(
                    sub_account="Cash",
                    action="deposit",
                    value=500.0,
                    quantity=None,
                    reference="Deposit",
                ),
            ],
        )
        output_path = tmp_path / "ledger.xlsx"
        _run(input_path, output_path)
        out_df = pd.read_excel(output_path, engine="openpyxl")
        assert out_df.iloc[0]["Account Value"] == pytest.approx(500.0)
        assert out_df.iloc[0]["Account Quantity"] == pytest.approx(500.0)

    def test_two_positions_independent(self, tmp_path: Path) -> None:
        input_path = _make_input(
            tmp_path,
            [
                _row(sub_account="Fund A", value=1000.0, quantity=10.0, reference="B001"),
                _row(sub_account="Fund B", value=2000.0, quantity=20.0, reference="B002"),
            ],
        )
        output_path = tmp_path / "ledger.xlsx"
        _run(input_path, output_path)
        out_df = pd.read_excel(output_path, engine="openpyxl")
        fund_a = out_df[out_df["sub_account"] == "Fund A"].iloc[0]
        fund_b = out_df[out_df["sub_account"] == "Fund B"].iloc[0]
        assert fund_a["Account Value"] == pytest.approx(-1000.0)
        assert fund_b["Account Value"] == pytest.approx(-2000.0)

    def test_missing_input_returns_exit_code_2(self, tmp_path: Path) -> None:
        output_path = tmp_path / "ledger.xlsx"
        result = _run(tmp_path / "nonexistent.xlsx", output_path)
        assert result.returncode == 2
        assert not output_path.exists()

    def test_invariant_holds_for_all_rows(self, tmp_path: Path) -> None:
        input_path = _make_input(
            tmp_path,
            [
                _row(
                    date="2024-01-01", action="buy", value=1000.0, quantity=10.0, reference="B001"
                ),
                _row(date="2024-01-02", action="buy", value=500.0, quantity=5.0, reference="B002"),
                _row(date="2024-01-03", action="sell", value=200.0, quantity=2.0, reference="S001"),
                _row(
                    date="2024-01-01",
                    sub_account="Cash",
                    action="deposit",
                    value=1000.0,
                    quantity=None,
                    reference="D001",
                ),
                _row(
                    date="2024-01-02",
                    sub_account="Cash",
                    action="trading",
                    value=500.0,
                    quantity=None,
                    reference="B001",
                ),
            ],
        )
        output_path = tmp_path / "ledger.xlsx"
        result = _run(input_path, output_path)
        assert result.returncode == 0
        out_df = pd.read_excel(output_path, engine="openpyxl")
        for (_, _), group in out_df.groupby(["account", "sub_account"], sort=False):
            prev_value = 0.0
            prev_qty = 0.0
            for _, row in group.iterrows():
                assert row["Account Value"] == pytest.approx(prev_value + row["Transaction Value"])
                assert row["Account Quantity"] == pytest.approx(
                    prev_qty + row["Transaction Quantity"]
                )
                prev_value = float(row["Account Value"])
                prev_qty = float(row["Account Quantity"])

    def test_cash_balance_coherence_deposit_buy_sell(self, tmp_path: Path) -> None:
        # SC-003: deposit +2000, buy offset -1000, sell offset +300 → Cash = +1300
        input_path = _make_input(
            tmp_path,
            [
                _row(
                    date="2024-01-01",
                    sub_account="Cash",
                    action="deposit",
                    value=2000.0,
                    quantity=None,
                    reference="Deposit",
                ),
                _row(
                    date="2024-01-02",
                    sub_account="Cash",
                    action="trading",
                    value=-1000.0,
                    quantity=None,
                    reference="B001-offset",
                ),
                _row(
                    date="2024-01-03",
                    sub_account="Cash",
                    action="trading",
                    value=300.0,
                    quantity=None,
                    reference="S001-offset",
                ),
            ],
        )
        output_path = tmp_path / "ledger.xlsx"
        result = _run(input_path, output_path)
        assert result.returncode == 0
        out_df = pd.read_excel(output_path, engine="openpyxl")
        cash_rows = (
            out_df[out_df["sub_account"] == "Cash"].sort_values("date").reset_index(drop=True)
        )
        assert cash_rows.iloc[-1]["Account Value"] == pytest.approx(1300.0)

    def test_regression_consolidate_journals_still_listed(self, tmp_path: Path) -> None:
        result = subprocess.run(
            [sys.executable, str(PIPELINE_PATH), "--help"],
            capture_output=True,
            text=True,
        )
        assert "consolidate_journals" in result.stdout
        assert "create_ledger" in result.stdout
