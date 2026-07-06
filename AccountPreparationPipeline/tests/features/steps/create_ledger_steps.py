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
LEDGER_COLUMNS = [
    "Transaction ID",
    "date",
    "account",
    "sub_account",
    "action",
    "reference",
    "Account Value",
    "Account Quantity",
    "Transaction Value",
    "Transaction Quantity",
]


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


SCENARIO_BUY = (
    "Buy events produce negated cumulative Account Value and positive cumulative Account Quantity"
)


@scenario(FEATURE_FILE, SCENARIO_BUY)
def test_buy_events() -> None:
    pass


@scenario(FEATURE_FILE, "Sell events negate both Account Value and Account Quantity in cumulation")
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


@scenario(FEATURE_FILE, "Single buy produces Transaction Value equal to Account Value")
def test_single_buy_transaction() -> None:
    pass


@scenario(FEATURE_FILE, "Second buy produces Transaction Value equal to the row delta")
def test_second_buy_transaction() -> None:
    pass


@scenario(FEATURE_FILE, "Sell row Transaction Value reflects the sell contribution")
def test_sell_transaction() -> None:
    pass


@scenario(FEATURE_FILE, "Transaction columns are independent per position")
def test_transaction_position_isolation() -> None:
    pass


@scenario(FEATURE_FILE, "Output contains exactly ten columns in defined order")
def test_ten_column_schema() -> None:
    pass


@scenario(FEATURE_FILE, "First-time run produces Transaction ID column with sequential IDs")
def test_first_time_transaction_ids() -> None:
    pass


@scenario(FEATURE_FILE, "Transaction IDs are sequential with 001 suffix on first run")
def test_sequential_transaction_ids() -> None:
    pass


@scenario(
    FEATURE_FILE,
    "Same-date Cash offsets are ordered by reference to preserve per-position invariant",
)
def test_same_date_cash_offsets_invariant() -> None:
    pass


@scenario(
    FEATURE_FILE,
    "Re-running with a new row between existing rows assigns suffix-incremented ID",
)
def test_rerun_inserts_between() -> None:
    pass


@scenario(FEATURE_FILE, "Idempotent re-run produces identical Transaction IDs")
def test_idempotent_rerun_bdd() -> None:
    pass


@scenario(FEATURE_FILE, "New row after all existing rows gets next sequential prefix")
def test_rerun_appends_sequential() -> None:
    pass


# ── Given steps ──────────────────────────────────────────────────────────────


@given("a consolidated journal with a single buy event", target_fixture="state")
def state_single_buy(tmp_path: Path) -> dict:
    return _make_input(tmp_path, [_row(value=1000.0, quantity=10.0, reference="B001")])


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


@given("a consolidated journal with 3 events on different dates", target_fixture="state")
def state_three_events(tmp_path: Path) -> dict:
    return _make_input(
        tmp_path,
        [
            _row(date="2024-01-01", reference="B001"),
            _row(date="2024-01-02", reference="B002"),
            _row(date="2024-01-03", reference="B003"),
        ],
    )


@given("a journal with two same-date buys and their Cash offsets", target_fixture="state")
def state_same_date_cash_offsets(tmp_path: Path) -> dict:
    # Rows deliberately NOT in canonical order to verify engine sorts correctly
    return _make_input(
        tmp_path,
        [
            _row(
                date="2024-03-15",
                sub_account="Cash",
                action="trading",
                reference="B002-offset",
                value=-500.0,
                quantity=None,
            ),
            _row(
                date="2024-03-15",
                sub_account="Vanguard Fund",
                action="buy",
                reference="B001",
                value=1000.0,
                quantity=10.0,
            ),
            _row(
                date="2024-03-15",
                sub_account="Cash",
                action="trading",
                reference="B001-offset",
                value=-1000.0,
                quantity=None,
            ),
            _row(
                date="2024-03-15",
                sub_account="Vanguard Fund",
                action="buy",
                reference="B002",
                value=500.0,
                quantity=5.0,
            ),
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


@then("the first output row Account Value equals the negated first buy value")
def check_first_buy_value(state: dict) -> None:
    df = pd.read_excel(state["output_path"], engine="openpyxl")
    assert df.iloc[0]["Account Value"] == pytest.approx(-1000.0)


@then("the second output row Account Value equals the negated sum of both buy values")
def check_second_buy_value(state: dict) -> None:
    df = pd.read_excel(state["output_path"], engine="openpyxl")
    assert df.iloc[1]["Account Value"] == pytest.approx(-1500.0)


@then("the second output row Account Quantity equals the sum of both buy quantities")
def check_second_buy_quantity(state: dict) -> None:
    df = pd.read_excel(state["output_path"], engine="openpyxl")
    assert df.iloc[1]["Account Quantity"] == pytest.approx(15.0)


@then("the final output row Account Quantity equals the buy quantity minus the sell quantity")
def check_final_sell_quantity(state: dict) -> None:
    df = pd.read_excel(state["output_path"], engine="openpyxl")
    assert df.iloc[-1]["Account Quantity"] == pytest.approx(7.0)


@then(
    "the final output row Account Value equals the negated buy value minus the negated sell value"
)
def check_final_sell_value(state: dict) -> None:
    df = pd.read_excel(state["output_path"], engine="openpyxl")
    assert df.iloc[-1]["Account Value"] == pytest.approx(-1300.0)


@then("the final Cash row Account Value equals the sum of both deposit values")
def check_final_cash_value(state: dict) -> None:
    df = pd.read_excel(state["output_path"], engine="openpyxl")
    cash_rows = df[df["sub_account"] == "Cash"]
    assert cash_rows.iloc[-1]["Account Value"] == pytest.approx(1500.0)


@then("the final Cash row Account Quantity equals the sum of both deposit values")
def check_final_cash_quantity(state: dict) -> None:
    df = pd.read_excel(state["output_path"], engine="openpyxl")
    cash_rows = df[df["sub_account"] == "Cash"]
    assert cash_rows.iloc[-1]["Account Quantity"] == pytest.approx(1500.0)


@then("each position accumulates independently")
def check_position_isolation(state: dict) -> None:
    df = pd.read_excel(state["output_path"], engine="openpyxl")
    fund_a = df[df["sub_account"] == "Fund A"].iloc[0]
    fund_b = df[df["sub_account"] == "Fund B"].iloc[0]
    assert fund_a["Account Value"] == pytest.approx(-1000.0)
    assert fund_b["Account Value"] == pytest.approx(-2000.0)


@then("the output has exactly 5 rows")
def check_five_rows(state: dict) -> None:
    df = pd.read_excel(state["output_path"], engine="openpyxl")
    assert len(df) == 5


@then("the action column values in the output match the input")
def check_action_unchanged(state: dict) -> None:
    out_df = pd.read_excel(state["output_path"], engine="openpyxl")
    inp_sorted = (
        state["input_df"]
        .sort_values(["date", "account", "sub_account", "reference"], kind="stable")
        .reset_index(drop=True)
    )
    assert list(out_df["action"]) == list(inp_sorted["action"])


@then("the reference column values in the output match the input")
def check_reference_unchanged(state: dict) -> None:
    out_df = pd.read_excel(state["output_path"], engine="openpyxl")
    inp_sorted = (
        state["input_df"]
        .sort_values(["date", "account", "sub_account", "reference"], kind="stable")
        .reset_index(drop=True)
    )
    assert list(out_df["reference"]) == list(inp_sorted["reference"])


@then("the first row Transaction Value equals the first row Account Value")
def check_first_row_transaction_equals_account(state: dict) -> None:
    df = pd.read_excel(state["output_path"], engine="openpyxl")
    assert df.iloc[0]["Transaction Value"] == pytest.approx(df.iloc[0]["Account Value"])


@then("the second row Transaction Value equals the negated second buy value")
def check_second_row_transaction_value(state: dict) -> None:
    df = pd.read_excel(state["output_path"], engine="openpyxl")
    assert df.iloc[1]["Transaction Value"] == pytest.approx(-500.0)


@then("the second row Account Value equals the negated sum of both buy values")
def check_second_row_account_value(state: dict) -> None:
    df = pd.read_excel(state["output_path"], engine="openpyxl")
    assert df.iloc[1]["Account Value"] == pytest.approx(-1500.0)


@then("the sell row Transaction Value equals the negated sell value")
def check_sell_transaction_value(state: dict) -> None:
    df = pd.read_excel(state["output_path"], engine="openpyxl")
    assert df.iloc[-1]["Transaction Value"] == pytest.approx(-300.0)


@then("the sell row Account Value satisfies the invariant")
def check_sell_invariant(state: dict) -> None:
    df = pd.read_excel(state["output_path"], engine="openpyxl")
    prev_account_value = df.iloc[-2]["Account Value"]
    assert df.iloc[-1]["Account Value"] == pytest.approx(
        prev_account_value + df.iloc[-1]["Transaction Value"]
    )


@then("each position Transaction Value equals its Account Value")
def check_position_transaction_equals_account(state: dict) -> None:
    df = pd.read_excel(state["output_path"], engine="openpyxl")
    fund_a = df[df["sub_account"] == "Fund A"].iloc[0]
    fund_b = df[df["sub_account"] == "Fund B"].iloc[0]
    assert fund_a["Transaction Value"] == pytest.approx(fund_a["Account Value"])
    assert fund_b["Transaction Value"] == pytest.approx(fund_b["Account Value"])


@then("the output has exactly ten columns in the defined order")
def check_ten_column_schema(state: dict) -> None:
    df = pd.read_excel(state["output_path"], engine="openpyxl")
    assert list(df.columns) == LEDGER_COLUMNS


@then("the Transaction ID column exists and first row value is 00001-001")
def check_transaction_id_first_row(state: dict) -> None:
    df = pd.read_excel(state["output_path"], engine="openpyxl")
    assert "Transaction ID" in df.columns
    assert df["Transaction ID"].iloc[0] == "00001-001"


@then("the Transaction IDs are 00001-001 00002-001 00003-001 in ascending row order")
def check_sequential_transaction_ids(state: dict) -> None:
    df = pd.read_excel(state["output_path"], engine="openpyxl")
    assert list(df["Transaction ID"]) == ["00001-001", "00002-001", "00003-001"]


@then("the Cash rows in Transaction ID order satisfy the per-position invariant")
def check_cash_invariant_by_transaction_id(state: dict) -> None:
    df = pd.read_excel(state["output_path"], engine="openpyxl")
    cash_rows = df[df["sub_account"] == "Cash"].sort_values("Transaction ID").reset_index(drop=True)
    assert cash_rows.iloc[1]["Account Value"] == pytest.approx(
        cash_rows.iloc[0]["Account Value"] + cash_rows.iloc[1]["Transaction Value"]
    )


# ── Re-run Given steps ────────────────────────────────────────────────────────


@given("an existing ledger produced from a 3-row journal", target_fixture="state")
def state_existing_ledger(tmp_path: Path) -> dict:
    rows = [
        _row(date="2024-01-01", reference="B001"),
        _row(date="2024-01-02", reference="B002"),
        _row(date="2024-01-03", reference="B003"),
    ]
    state = _make_input(tmp_path, rows)
    subprocess.run(
        [
            sys.executable,
            str(PIPELINE_PATH),
            "create_ledger",
            str(state["input_path"]),
            str(state["output_path"]),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    prior_df = pd.read_excel(state["output_path"], engine="openpyxl")
    state["prior_ids"] = list(prior_df["Transaction ID"])
    return state


@given("a new journal event inserted between the first and second existing rows")
def insert_between_rows(state: dict) -> None:
    new_row = _row(date="2024-01-01", reference="B001a")
    updated = pd.concat(
        [state["input_df"], pd.DataFrame([new_row], columns=JOURNAL_COLUMNS)],
        ignore_index=True,
    )
    state["input_df"] = updated
    updated.to_excel(state["input_path"], index=False, engine="openpyxl")


@given("a new journal event appended after all existing rows")
def append_after_rows(state: dict) -> None:
    new_row = _row(date="2024-01-04", reference="B004")
    updated = pd.concat(
        [state["input_df"], pd.DataFrame([new_row], columns=JOURNAL_COLUMNS)],
        ignore_index=True,
    )
    state["input_df"] = updated
    updated.to_excel(state["input_path"], index=False, engine="openpyxl")


# ── Re-run Then steps ─────────────────────────────────────────────────────────


@then("the original three IDs are unchanged and the new row gets 00001-002")
def check_insertion_ids(state: dict) -> None:
    df = pd.read_excel(state["output_path"], engine="openpyxl")
    df_sorted = df.sort_values(["date", "account", "sub_account", "reference"]).reset_index(
        drop=True
    )
    assert df_sorted.loc[df_sorted["reference"] == "B001", "Transaction ID"].iloc[0] == "00001-001"
    assert df_sorted.loc[df_sorted["reference"] == "B001a", "Transaction ID"].iloc[0] == "00001-002"
    assert df_sorted.loc[df_sorted["reference"] == "B002", "Transaction ID"].iloc[0] == "00002-001"
    assert df_sorted.loc[df_sorted["reference"] == "B003", "Transaction ID"].iloc[0] == "00003-001"


@then("all Transaction IDs are identical to the prior run")
def check_idempotent_ids(state: dict) -> None:
    df = pd.read_excel(state["output_path"], engine="openpyxl")
    assert list(df["Transaction ID"]) == state["prior_ids"]


@then("the new row gets Transaction ID 00004-001")
def check_appended_id(state: dict) -> None:
    df = pd.read_excel(state["output_path"], engine="openpyxl")
    new_row = df.loc[df["reference"] == "B004"]
    assert new_row["Transaction ID"].iloc[0] == "00004-001"
