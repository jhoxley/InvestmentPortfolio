from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest
from pytest_bdd import given, scenario, then, when

FEATURE_FILE = str(Path(__file__).parent.parent / "create_capital_ledger.feature")
PIPELINE_PATH = Path(__file__).parent.parent.parent.parent / "pipeline.py"
DATA_DIR = Path(__file__).parent.parent.parent / "data" / "create_capital_ledger"


def _run(input_path: Path, output_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(PIPELINE_PATH),
            "create_capital_ledger",
            str(input_path),
            str(output_path),
        ],
        capture_output=True,
        text=True,
    )


# ── Scenario bindings ────────────────────────────────────────────────────────


@scenario(FEATURE_FILE, "Deposit rows accumulate in capital column")
def test_deposit_rows_accumulate_in_capital_column() -> None:
    pass


@scenario(FEATURE_FILE, "Buy and sell rows accumulate in book_value column")
def test_buy_and_sell_rows_accumulate_in_book_value_column() -> None:
    pass


@scenario(FEATURE_FILE, "Non-qualifying action rows are excluded from all columns")
def test_non_qualifying_action_rows_are_excluded() -> None:
    pass


@scenario(FEATURE_FILE, "Output has one row per unique date in chronological order")
def test_output_has_one_row_per_unique_date() -> None:
    pass


@scenario(FEATURE_FILE, "Mode exits with non-zero code when input file does not exist")
def test_mode_exits_nonzero_for_missing_input() -> None:
    pass


@scenario(FEATURE_FILE, "Pipeline mode accepts input and output path arguments")
def test_pipeline_mode_accepts_arguments() -> None:
    pass


# ── Given steps ──────────────────────────────────────────────────────────────


@given("a simple ledger fixture with deposit, income, buy, and sell rows", target_fixture="state")
def state_simple_ledger(tmp_path: Path) -> dict:
    output_path = tmp_path / "capital_ledger.xlsx"
    return {"input_path": DATA_DIR / "simple_ledger.xlsx", "output_path": output_path}


@given("a mixed ledger fixture with additional trading and dividend rows", target_fixture="state")
def state_mixed_ledger(tmp_path: Path) -> dict:
    output_path = tmp_path / "capital_ledger.xlsx"
    return {"input_path": DATA_DIR / "mixed_actions_ledger.xlsx", "output_path": output_path}


@given("a path to a non-existent ledger file", target_fixture="state")
def state_nonexistent_file(tmp_path: Path) -> dict:
    output_path = tmp_path / "capital_ledger.xlsx"
    return {"input_path": tmp_path / "does_not_exist.xlsx", "output_path": output_path}


@given("a valid capital ledger input file", target_fixture="state")
def state_valid_input(tmp_path: Path) -> dict:
    output_path = tmp_path / "capital_ledger.xlsx"
    return {"input_path": DATA_DIR / "simple_ledger.xlsx", "output_path": output_path}


# ── When steps ───────────────────────────────────────────────────────────────


@when("I run create_capital_ledger", target_fixture="result")
def run_mode(state: dict) -> subprocess.CompletedProcess[str]:
    proc = _run(state["input_path"], state["output_path"])
    state["result"] = proc
    return proc


# ── Then steps ───────────────────────────────────────────────────────────────


@then("the exit code is 0")
def check_exit_zero(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, (
        f"Expected exit 0, got {result.returncode}."
        f"\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


@then("the exit code is non-zero")
def check_exit_nonzero(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode != 0, f"Expected non-zero exit, got 0.\nstdout: {result.stdout}"


@then("the output has 4 rows in ascending date order")
def check_four_rows_ascending(state: dict) -> None:
    df = pd.read_excel(state["output_path"], engine="openpyxl")
    assert len(df) == 4, f"Expected 4 rows, got {len(df)}"
    dates = df["date"].astype(str).tolist()
    assert dates == sorted(dates), f"Rows not in ascending date order: {dates}"


@then("the capital column carries forward to all dates from the deposit date")
def check_capital_carry_forward(state: dict) -> None:
    df = pd.read_excel(state["output_path"], engine="openpyxl")
    for capital in df["capital"].tolist():
        assert float(capital) == pytest.approx(5000.0), (
            f"Expected capital=5000.0 on all rows, got {capital}"
        )


@then("the income column shows 120.00 from the income date onwards")
def check_income_from_date(state: dict) -> None:
    df = pd.read_excel(state["output_path"], engine="openpyxl")
    df["date"] = df["date"].astype(str)
    for _, row in df[df["date"] >= "2024-02-15"].iterrows():
        assert float(row["income"]) == pytest.approx(120.0), (
            f"Expected income=120.0 from 2024-02-15, got {row['income']} on {row['date']}"
        )


@then("the book_value column is 0.00 before any buy or sell")
def check_book_value_zero_before_buys(state: dict) -> None:
    df = pd.read_excel(state["output_path"], engine="openpyxl")
    df["date"] = df["date"].astype(str)
    before_buy = df[df["date"] < "2024-03-20"]
    for _, row in before_buy.iterrows():
        assert float(row["book_value"]) == pytest.approx(0.0), (
            f"Expected book_value=0.0 before buys, got {row['book_value']} on {row['date']}"
        )


@then("the book_value on 2024-03-20 is -3000.00")
def check_book_value_2024_03_20(state: dict) -> None:
    df = pd.read_excel(state["output_path"], engine="openpyxl")
    df["date"] = df["date"].astype(str)
    row = df[df["date"] == "2024-03-20"].iloc[0]
    assert float(row["book_value"]) == pytest.approx(-3000.0), (
        f"Expected book_value=-3000.0 on 2024-03-20, got {row['book_value']}"
    )


@then("the book_value on 2024-04-10 is -2200.00")
def check_book_value_2024_04_10(state: dict) -> None:
    df = pd.read_excel(state["output_path"], engine="openpyxl")
    df["date"] = df["date"].astype(str)
    row = df[df["date"] == "2024-04-10"].iloc[0]
    assert float(row["book_value"]) == pytest.approx(-2200.0), (
        f"Expected book_value=-2200.0 on 2024-04-10, got {row['book_value']}"
    )


@then("the output row count is 4")
def check_row_count_four(state: dict) -> None:
    df = pd.read_excel(state["output_path"], engine="openpyxl")
    assert len(df) == 4, f"Expected 4 rows, got {len(df)}"


@then("no column value reflects the excluded transaction amounts")
def check_no_excluded_amounts(state: dict) -> None:
    df = pd.read_excel(state["output_path"], engine="openpyxl")
    for col in ["capital", "income", "book_value"]:
        for val in df[col].tolist():
            assert float(val) not in {999.0, 50.0, 1000.0}, (
                f"Column {col} contains excluded amount {val}"
            )


@then("the output XLSX is created with the correct columns")
def check_output_xlsx_columns(state: dict) -> None:
    assert state["output_path"].exists(), "Output XLSX was not created"
    df = pd.read_excel(state["output_path"], engine="openpyxl")
    assert list(df.columns) == ["date", "capital", "income", "book_value"]
