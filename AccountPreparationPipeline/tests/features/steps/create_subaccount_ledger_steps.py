from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest
from pytest_bdd import given, parsers, scenario, then, when

FEATURE_FILE = str(Path(__file__).parent.parent / "create_subaccount_ledger.feature")
PIPELINE_PATH = Path(__file__).parent.parent.parent.parent / "pipeline.py"
DATA_DIR = Path(__file__).parent.parent.parent / "data" / "create_subaccount_ledger"


# ── Scenario bindings ────────────────────────────────────────────────────────


@scenario(
    FEATURE_FILE,
    "Equity positions accumulate book_cost and quantity from single capital ledger",
)
def test_equity_accumulate_single_capital() -> None:
    pass


@scenario(FEATURE_FILE, "Two capital ledgers merge equity sub-accounts by name")
def test_two_capital_ledgers_merge() -> None:
    pass


@scenario(FEATURE_FILE, "Dividend income accumulates in total_income from income ledger")
def test_dividend_income_accumulates() -> None:
    pass


@scenario(FEATURE_FILE, "Cash rows from income ledger are excluded")
def test_cash_income_excluded() -> None:
    pass


@scenario(FEATURE_FILE, "Cash sub-account has quantity equal to book_cost and zero total_income")
def test_cash_qty_equals_book_cost() -> None:
    pass


@scenario(FEATURE_FILE, "Mode exits non-zero when a capital ledger file does not exist")
def test_missing_capital_file_error() -> None:
    pass


@scenario(FEATURE_FILE, "Output XLSX has exactly the required columns in order")
def test_output_columns_correct_order() -> None:
    pass


# ── Shared state fixture ─────────────────────────────────────────────────────


@pytest.fixture
def state(tmp_path: Path) -> dict:
    return {
        "capital_paths": [],
        "income_paths": [],
        "output_path": tmp_path / "subaccount_ledger.xlsx",
        "returncode": None,
        "stdout": "",
        "stderr": "",
        "bad_capital_path": None,
    }


# ── Given steps ──────────────────────────────────────────────────────────────


@given(parsers.parse('a capital ledger fixture "{filename}"'))
def add_capital_fixture(filename: str, state: dict, tmp_path: Path) -> None:
    src = DATA_DIR / filename
    dst = tmp_path / filename
    shutil.copy(src, dst)
    state["capital_paths"].append(dst)


@given(parsers.parse('an income ledger fixture "{filename}"'))
def add_income_fixture(filename: str, state: dict, tmp_path: Path) -> None:
    src = DATA_DIR / filename
    dst = tmp_path / filename
    shutil.copy(src, dst)
    state["income_paths"].append(dst)


@given("a path to a non-existent capital ledger file")
def add_nonexistent_capital(state: dict, tmp_path: Path) -> None:
    state["bad_capital_path"] = tmp_path / "does_not_exist.xlsx"
    state["capital_paths"].append(state["bad_capital_path"])


# ── When steps ───────────────────────────────────────────────────────────────


def _run_pipeline(state: dict) -> None:
    cmd = [
        sys.executable,
        str(PIPELINE_PATH),
        "create_subaccount_ledger",
        str(state["output_path"]),
        "--capital",
        *[str(p) for p in state["capital_paths"]],
    ]
    if state["income_paths"]:
        cmd.extend(["--income", *[str(p) for p in state["income_paths"]]])
    result = subprocess.run(cmd, capture_output=True, text=True)
    state["returncode"] = result.returncode
    state["stdout"] = result.stdout
    state["stderr"] = result.stderr


@when(parsers.parse("I run create_subaccount_ledger with capital ledgers {filenames}"))
def run_with_capital_ledgers(filenames: str, state: dict) -> None:
    _run_pipeline(state)


@when(
    parsers.parse(
        "I run create_subaccount_ledger with capital ledgers {cap_files}"
        " and income ledgers {inc_files}"
    )
)
def run_with_capital_and_income_ledgers(cap_files: str, inc_files: str, state: dict) -> None:
    _run_pipeline(state)


@when("I run create_subaccount_ledger with that non-existent capital path")
def run_with_nonexistent_path(state: dict) -> None:
    _run_pipeline(state)


# ── Then steps ───────────────────────────────────────────────────────────────


@then(parsers.parse("the exit code is {code:d}"))
def check_exit_code(code: int, state: dict) -> None:
    assert state["returncode"] == code, (
        f"Expected exit {code}, got {state['returncode']}."
        f"\nstdout: {state['stdout']}\nstderr: {state['stderr']}"
    )


@then("the exit code is non-zero")
def check_exit_nonzero(state: dict) -> None:
    assert state["returncode"] != 0, f"Expected non-zero exit, got 0.\nstdout: {state['stdout']}"


_BOOK_COST_QTY_STEP = (
    'the output has a row for "{sub_account}" on "{date}"'
    " with book_cost {book_cost:f} and quantity {quantity:f}"
)


@then(parsers.parse(_BOOK_COST_QTY_STEP))
def check_book_cost_and_quantity(
    sub_account: str, date: str, book_cost: float, quantity: float, state: dict
) -> None:
    df = pd.read_excel(state["output_path"], engine="openpyxl")
    df["date"] = df["date"].astype(str)
    row = df[(df["sub_account"] == sub_account) & (df["date"] == date)]
    assert len(row) == 1, (
        f"Expected exactly 1 row for ({sub_account}, {date}), found {len(row)}.\n{df.to_string()}"
    )
    assert float(row.iloc[0]["book_cost"]) == pytest.approx(book_cost), (
        f"Expected book_cost={book_cost}, got {row.iloc[0]['book_cost']}"
    )
    assert float(row.iloc[0]["quantity"]) == pytest.approx(quantity), (
        f"Expected quantity={quantity}, got {row.iloc[0]['quantity']}"
    )


@then(
    parsers.parse(
        'the output has a row for "{sub_account}" on "{date}" with total_income {expected:f}'
    )
)
def check_total_income(sub_account: str, date: str, expected: float, state: dict) -> None:
    df = pd.read_excel(state["output_path"], engine="openpyxl")
    df["date"] = df["date"].astype(str)
    row = df[(df["sub_account"] == sub_account) & (df["date"] == date)]
    assert len(row) == 1, (
        f"Expected exactly 1 row for ({sub_account}, {date}), found {len(row)}.\n{df.to_string()}"
    )
    assert float(row.iloc[0]["total_income"]) == pytest.approx(expected), (
        f"Expected total_income={expected}, got {row.iloc[0]['total_income']}"
    )


@then(parsers.parse('there is no Cash row with date "{date}" in the output'))
def check_no_cash_row_on_date(date: str, state: dict) -> None:
    df = pd.read_excel(state["output_path"], engine="openpyxl")
    df["date"] = df["date"].astype(str)
    cash_on_date = df[(df["sub_account"] == "Cash") & (df["date"] == date)]
    assert len(cash_on_date) == 0, (
        f"Expected no Cash row on {date}, found:\n{cash_on_date.to_string()}"
    )


@then(parsers.parse('the Cash row on "{date}" has quantity equal to book_cost'))
def check_cash_qty_equals_book_cost(date: str, state: dict) -> None:
    df = pd.read_excel(state["output_path"], engine="openpyxl")
    df["date"] = df["date"].astype(str)
    row = df[(df["sub_account"] == "Cash") & (df["date"] == date)]
    assert len(row) == 1, f"Expected exactly 1 Cash row on {date}, found {len(row)}"
    assert float(row.iloc[0]["quantity"]) == pytest.approx(float(row.iloc[0]["book_cost"])), (
        f"quantity={row.iloc[0]['quantity']} != book_cost={row.iloc[0]['book_cost']}"
    )


@then(parsers.parse('the Cash row on "{date}" has total_income {expected:f}'))
def check_cash_total_income(date: str, expected: float, state: dict) -> None:
    df = pd.read_excel(state["output_path"], engine="openpyxl")
    df["date"] = df["date"].astype(str)
    row = df[(df["sub_account"] == "Cash") & (df["date"] == date)]
    assert len(row) == 1, f"Expected exactly 1 Cash row on {date}, found {len(row)}"
    assert float(row.iloc[0]["total_income"]) == pytest.approx(expected), (
        f"Expected total_income={expected}, got {row.iloc[0]['total_income']}"
    )


@then("the error output mentions the missing file path")
def check_error_mentions_path(state: dict) -> None:
    bad_path = state.get("bad_capital_path")
    combined = (state["stdout"] or "") + (state["stderr"] or "")
    assert bad_path is not None
    assert str(bad_path.name) in combined or str(bad_path) in combined, (
        f"Expected '{bad_path}' in output.\nstdout: {state['stdout']}\nstderr: {state['stderr']}"
    )


_COLUMNS_STEP = (
    "the output XLSX has exactly the columns"
    " date, sub_account, book_cost, quantity, total_income in that order"
)


@then(_COLUMNS_STEP)
def check_output_columns_order(state: dict) -> None:
    df = pd.read_excel(state["output_path"], engine="openpyxl")
    assert list(df.columns) == ["date", "sub_account", "book_cost", "quantity", "total_income"], (
        f"Got columns: {list(df.columns)}"
    )
