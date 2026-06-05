from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest
from pytest_bdd import given, scenario, then, when

FEATURE_FILE = str(Path(__file__).parent.parent / "create_ledger.feature")
PIPELINE_PATH = Path(__file__).parent.parent.parent.parent / "pipeline.py"
JOURNAL_COLUMNS = ["date", "account", "sub_account", "action", "reference", "value", "quantity"]


def _make_input(tmp_path: Path, rows: list[dict]) -> dict:
    df = pd.DataFrame(rows, columns=JOURNAL_COLUMNS)
    input_path = tmp_path / "input.xlsx"
    df.to_excel(input_path, index=False, engine="openpyxl")
    return {
        "tmp_path": tmp_path,
        "input_path": input_path,
        "output_path": tmp_path / "output.xlsx",
        "input_df": df,
    }


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


# ── Scenario bindings ────────────────────────────────────────────────────────


SCENARIO_BUY = "Buy events produce negated cumulative value and positive cumulative quantity"


@scenario(FEATURE_FILE, SCENARIO_BUY)
def test_buy_events() -> None:
    pass


@scenario(FEATURE_FILE, "Sell events negate both value and quantity in cumulation")
def test_sell_events() -> None:
    pass


@scenario(FEATURE_FILE, "Cash rows with blank quantity use value as quantity for cumulation")
def test_cash_rows() -> None:
    pass


@scenario(FEATURE_FILE, "Running totals are independent per position")
def test_position_isolation() -> None:
    pass


@scenario(FEATURE_FILE, "Output row count equals input row count")
def test_row_count() -> None:
    pass


@scenario(FEATURE_FILE, "Action and reference columns are unchanged in output")
def test_unchanged_columns() -> None:
    pass


@scenario(FEATURE_FILE, "Missing input file returns exit code 2")
def test_missing_input() -> None:
    pass


# ── Given steps ──────────────────────────────────────────────────────────────


@given(
    "a consolidated journal with two buy events for the same position",
    target_fixture="state",
)
def state_two_buys(tmp_path: Path) -> dict:
    return _make_input(
        tmp_path,
        [
            _row(date="2024-01-01", value=1000.0, quantity=10.0, reference="B001"),
            _row(date="2024-01-02", value=500.0, quantity=5.0, reference="B002"),
        ],
    )


@given(
    "a consolidated journal with a buy followed by a sell for the same position",
    target_fixture="state",
)
def state_buy_then_sell(tmp_path: Path) -> dict:
    return _make_input(
        tmp_path,
        [
            _row(date="2024-01-01", action="buy", value=1000.0, quantity=10.0, reference="B001"),
            _row(date="2024-01-02", action="sell", value=300.0, quantity=3.0, reference="S001"),
        ],
    )


@given(
    "a consolidated journal with two Cash deposit events with blank quantity",
    target_fixture="state",
)
def state_cash_deposits(tmp_path: Path) -> dict:
    return _make_input(
        tmp_path,
        [
            _row(
                date="2024-01-01",
                sub_account="Cash",
                action="deposit",
                value=1000.0,
                quantity=None,
                reference="Deposit",
            ),
            _row(
                date="2024-01-02",
                sub_account="Cash",
                action="deposit",
                value=500.0,
                quantity=None,
                reference="Deposit",
            ),
        ],
    )


@given(
    "a consolidated journal with events for two different positions",
    target_fixture="state",
)
def state_two_positions(tmp_path: Path) -> dict:
    return _make_input(
        tmp_path,
        [
            _row(sub_account="Fund A", value=1000.0, quantity=10.0, reference="B001"),
            _row(sub_account="Fund B", value=2000.0, quantity=20.0, reference="B002"),
        ],
    )


@given("a consolidated journal with 5 events", target_fixture="state")
def state_five_events(tmp_path: Path) -> dict:
    return _make_input(
        tmp_path, [_row(date=f"2024-01-0{i + 1}", reference=f"B00{i}") for i in range(5)]
    )


@given("a consolidated journal with buy and sell events", target_fixture="state")
def state_buy_and_sell(tmp_path: Path) -> dict:
    return _make_input(
        tmp_path,
        [
            _row(date="2024-01-01", action="buy", reference="B001"),
            _row(date="2024-01-02", action="sell", reference="S001"),
        ],
    )


@given("the input file does not exist", target_fixture="state")
def state_missing_input(tmp_path: Path) -> dict:
    return {
        "tmp_path": tmp_path,
        "input_path": tmp_path / "does_not_exist.xlsx",
        "output_path": tmp_path / "output.xlsx",
        "input_df": None,
    }


# ── When steps ───────────────────────────────────────────────────────────────


@when("I run create_ledger", target_fixture="result")
def run_create_ledger(state: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(PIPELINE_PATH),
            "create_ledger",
            str(state["input_path"]),
            str(state["output_path"]),
        ],
        capture_output=True,
        text=True,
    )


# ── Then steps ───────────────────────────────────────────────────────────────


@then("the exit code is 0")
def check_exit_zero(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, (
        f"Expected exit 0, got {result.returncode}."
        f"\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


@then("the exit code is 2")
def check_exit_two(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 2, (
        f"Expected exit 2, got {result.returncode}."
        f"\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


@then("the first output row value equals the negated first buy value")
def check_first_buy_value(state: dict) -> None:
    df = pd.read_excel(state["output_path"], engine="openpyxl")
    assert df.iloc[0]["value"] == pytest.approx(-1000.0)


@then("the second output row value equals the negated sum of both buy values")
def check_second_buy_value(state: dict) -> None:
    df = pd.read_excel(state["output_path"], engine="openpyxl")
    assert df.iloc[1]["value"] == pytest.approx(-1500.0)


@then("the second output row quantity equals the sum of both buy quantities")
def check_second_buy_quantity(state: dict) -> None:
    df = pd.read_excel(state["output_path"], engine="openpyxl")
    assert df.iloc[1]["quantity"] == pytest.approx(15.0)


@then("the final output row quantity equals the buy quantity minus the sell quantity")
def check_final_sell_quantity(state: dict) -> None:
    df = pd.read_excel(state["output_path"], engine="openpyxl")
    assert df.iloc[-1]["quantity"] == pytest.approx(7.0)


@then("the final output row value equals the negated buy value minus the negated sell value")
def check_final_sell_value(state: dict) -> None:
    df = pd.read_excel(state["output_path"], engine="openpyxl")
    assert df.iloc[-1]["value"] == pytest.approx(-1300.0)


@then("the final Cash row value equals the sum of both deposit values")
def check_final_cash_value(state: dict) -> None:
    df = pd.read_excel(state["output_path"], engine="openpyxl")
    cash_rows = df[df["sub_account"] == "Cash"]
    assert cash_rows.iloc[-1]["value"] == pytest.approx(1500.0)


@then("the final Cash row quantity equals the sum of both deposit values")
def check_final_cash_quantity(state: dict) -> None:
    df = pd.read_excel(state["output_path"], engine="openpyxl")
    cash_rows = df[df["sub_account"] == "Cash"]
    assert cash_rows.iloc[-1]["quantity"] == pytest.approx(1500.0)


@then("each position accumulates independently")
def check_position_isolation(state: dict) -> None:
    df = pd.read_excel(state["output_path"], engine="openpyxl")
    fund_a = df[df["sub_account"] == "Fund A"].iloc[0]
    fund_b = df[df["sub_account"] == "Fund B"].iloc[0]
    assert fund_a["value"] == pytest.approx(-1000.0)
    assert fund_b["value"] == pytest.approx(-2000.0)


@then("the output has exactly 5 rows")
def check_five_rows(state: dict) -> None:
    df = pd.read_excel(state["output_path"], engine="openpyxl")
    assert len(df) == 5


@then("the action column values in the output match the input")
def check_action_unchanged(state: dict) -> None:
    out_df = pd.read_excel(state["output_path"], engine="openpyxl")
    inp_sorted = (
        state["input_df"]
        .sort_values(["account", "sub_account", "date"], kind="stable")
        .reset_index(drop=True)
    )
    assert list(out_df["action"]) == list(inp_sorted["action"])


@then("the reference column values in the output match the input")
def check_reference_unchanged(state: dict) -> None:
    out_df = pd.read_excel(state["output_path"], engine="openpyxl")
    inp_sorted = (
        state["input_df"]
        .sort_values(["account", "sub_account", "date"], kind="stable")
        .reset_index(drop=True)
    )
    assert list(out_df["reference"]) == list(inp_sorted["reference"])
