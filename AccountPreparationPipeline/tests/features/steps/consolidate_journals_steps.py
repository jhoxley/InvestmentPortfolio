from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd
from pytest_bdd import given, parsers, scenario, then, when

FEATURE_FILE = str(Path(__file__).parent.parent / "consolidate_journals.feature")
PIPELINE_PATH = Path(__file__).parent.parent.parent.parent / "pipeline.py"
DATA_DIR = Path(__file__).parent.parent.parent / "data" / "consolidate_journals"


def _run(
    journal_path: Path, frags_dir: Path, method: str, account: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(PIPELINE_PATH),
            "consolidate_journals",
            str(journal_path),
            str(frags_dir),
            method,
            account,
        ],
        capture_output=True,
        text=True,
    )


# ── Scenario bindings ────────────────────────────────────────────────────────


@scenario(FEATURE_FILE, "Creates a new journal from valid HL CSV exports")
def test_creates_new_journal() -> None:
    pass


@scenario(FEATURE_FILE, "Skips preamble rows before HL CSV header")
def test_skips_preamble() -> None:
    pass


@scenario(FEATURE_FILE, "Maps B-reference to buy action")
def test_maps_buy() -> None:
    pass


@scenario(FEATURE_FILE, "Maps S-reference to sell action")
def test_maps_sell() -> None:
    pass


@scenario(FEATURE_FILE, "Maps Deposit and BACS references to contrib action")
def test_maps_contrib() -> None:
    pass


@scenario(FEATURE_FILE, "Strips unit cost and quantity suffix from description")
def test_strips_description() -> None:
    pass


@scenario(FEATURE_FILE, "Re-running with same inputs inserts zero events")
def test_idempotent() -> None:
    pass


@scenario(FEATURE_FILE, "Incremental run adds only new events")
def test_incremental() -> None:
    pass


@scenario(FEATURE_FILE, "Valid file processes despite co-located invalid file")
def test_mixed_files() -> None:
    pass


@scenario(FEATURE_FILE, "No-header file is reported in errors section")
def test_no_header_error() -> None:
    pass


@scenario(FEATURE_FILE, "Bad-value row reported with line number, surrounding rows still processed")
def test_bad_value_row() -> None:
    pass


# ── Given steps ──────────────────────────────────────────────────────────────


@given("a directory of valid HL CSV files", target_fixture="state")
def state_valid_dir(tmp_path: Path) -> dict:
    frags_dir = tmp_path / "frags"
    frags_dir.mkdir()
    shutil.copy(DATA_DIR / "valid_hl_simple.csv", frags_dir / "valid_hl_simple.csv")
    return {"tmp_path": tmp_path, "frags_dir": frags_dir}


@given("an HL CSV file with metadata preamble rows before the header", target_fixture="state")
def state_preamble_dir(tmp_path: Path) -> dict:
    frags_dir = tmp_path / "frags"
    frags_dir.mkdir()
    shutil.copy(DATA_DIR / "valid_hl_with_preamble.csv", frags_dir / "valid_hl_with_preamble.csv")
    return {"tmp_path": tmp_path, "frags_dir": frags_dir}


@given("a valid HL CSV file with a buy transaction reference", target_fixture="state")
def state_buy_dir(tmp_path: Path) -> dict:
    frags_dir = tmp_path / "frags"
    frags_dir.mkdir()
    shutil.copy(DATA_DIR / "valid_hl_simple.csv", frags_dir / "valid_hl_simple.csv")
    return {"tmp_path": tmp_path, "frags_dir": frags_dir}


@given("a valid HL CSV file with a sell transaction reference", target_fixture="state")
def state_sell_dir(tmp_path: Path) -> dict:
    frags_dir = tmp_path / "frags"
    frags_dir.mkdir()
    shutil.copy(DATA_DIR / "valid_hl_simple.csv", frags_dir / "valid_hl_simple.csv")
    return {"tmp_path": tmp_path, "frags_dir": frags_dir}


@given("a valid HL CSV file with Deposit and BACS rows", target_fixture="state")
def state_contrib_dir(tmp_path: Path) -> dict:
    frags_dir = tmp_path / "frags"
    frags_dir.mkdir()
    shutil.copy(DATA_DIR / "valid_hl_contrib.csv", frags_dir / "valid_hl_contrib.csv")
    return {"tmp_path": tmp_path, "frags_dir": frags_dir}


@given("no existing consolidated journal")
def no_existing_journal(state: dict) -> None:
    state["journal_path"] = state["tmp_path"] / "journal.xlsx"


@given("I have already run consolidate_journals once")
def run_once(state: dict) -> None:
    result = _run(state["journal_path"], state["frags_dir"], "HL", "Test ISA")
    assert result.returncode == 0, f"First run failed:\n{result.stderr}"
    state["first_result"] = result


@given("an existing consolidated journal with 3 events", target_fixture="state")
def state_existing_journal(tmp_path: Path) -> dict:
    frags_dir = tmp_path / "frags_initial"
    frags_dir.mkdir()
    shutil.copy(DATA_DIR / "valid_hl_simple.csv", frags_dir / "valid_hl_simple.csv")
    journal_path = tmp_path / "journal.xlsx"
    result = _run(journal_path, frags_dir, "HL", "Test ISA")
    assert result.returncode == 0
    return {"tmp_path": tmp_path, "journal_path": journal_path}


@given("a directory containing a new HL CSV file with 2 different events")
def new_fragments_dir(state: dict) -> None:
    new_dir = state["tmp_path"] / "frags_new"
    new_dir.mkdir()
    shutil.copy(DATA_DIR / "valid_hl_contrib.csv", new_dir / "valid_hl_contrib.csv")
    state["frags_dir"] = new_dir


@given("a directory containing one valid and one invalid HL CSV file", target_fixture="state")
def state_mixed_dir(tmp_path: Path) -> dict:
    frags_dir = tmp_path / "frags"
    frags_dir.mkdir()
    shutil.copy(DATA_DIR / "valid_hl_simple.csv", frags_dir / "valid_hl_simple.csv")
    shutil.copy(DATA_DIR / "invalid_no_header.csv", frags_dir / "invalid_no_header.csv")
    return {
        "tmp_path": tmp_path,
        "frags_dir": frags_dir,
        "journal_path": tmp_path / "journal.xlsx",
    }


@given(
    "a directory containing only an HL CSV file with no recognisable header",
    target_fixture="state",
)
def state_no_header_dir(tmp_path: Path) -> dict:
    frags_dir = tmp_path / "frags"
    frags_dir.mkdir()
    shutil.copy(DATA_DIR / "invalid_no_header.csv", frags_dir / "invalid_no_header.csv")
    return {
        "tmp_path": tmp_path,
        "frags_dir": frags_dir,
        "journal_path": tmp_path / "journal.xlsx",
    }


@given("a directory containing an HL CSV file with one bad-value row", target_fixture="state")
def state_bad_value_dir(tmp_path: Path) -> dict:
    frags_dir = tmp_path / "frags"
    frags_dir.mkdir()
    shutil.copy(DATA_DIR / "invalid_bad_value.csv", frags_dir / "invalid_bad_value.csv")
    return {
        "tmp_path": tmp_path,
        "frags_dir": frags_dir,
        "journal_path": tmp_path / "journal.xlsx",
    }


# ── When steps ───────────────────────────────────────────────────────────────


@when(
    parsers.parse('I run consolidate_journals with method {method} and account "{account}"'),
    target_fixture="result",
)
def run_mode(state: dict, method: str, account: str) -> subprocess.CompletedProcess[str]:
    return _run(state["journal_path"], state["frags_dir"], method, account)


@when("I run consolidate_journals again with the same inputs", target_fixture="result")
def run_again(state: dict) -> subprocess.CompletedProcess[str]:
    return _run(state["journal_path"], state["frags_dir"], "HL", "Test ISA")


# ── Then steps ───────────────────────────────────────────────────────────────


@then("the exit code is 0")
def check_exit_zero(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, (
        f"Expected exit 0, got {result.returncode}."
        f"\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )


@then(parsers.parse("the journal contains {count:d} events"))
def check_event_count(state: dict, count: int) -> None:
    df = pd.read_excel(state["journal_path"], engine="openpyxl")
    assert len(df) == count, f"Expected {count} events, got {len(df)}"


@then(parsers.parse("the journal contains {count:d} events total"))
def check_event_count_total(state: dict, count: int) -> None:
    df = pd.read_excel(state["journal_path"], engine="openpyxl")
    assert len(df) == count, f"Expected {count} total events, got {len(df)}"


@then("the consolidated journal XLSX is created")
def check_journal_exists(state: dict) -> None:
    assert state["journal_path"].exists(), "Journal XLSX was not created"


@then("the journal contains the correct columns")
def check_columns(state: dict) -> None:
    from src.modes.consolidate_journals.constants import JOURNAL_COLUMNS

    df = pd.read_excel(state["journal_path"], engine="openpyxl")
    assert list(df.columns) == JOURNAL_COLUMNS


@then(parsers.parse('the journal contains a row with action "{action}"'))
def check_action_present(state: dict, action: str) -> None:
    df = pd.read_excel(state["journal_path"], engine="openpyxl")
    assert action in df["action"].values, f"Action '{action}' not found in journal"


@then(parsers.parse('the journal contains {count:d} rows with action "{action}"'))
def check_action_count(state: dict, count: int, action: str) -> None:
    df = pd.read_excel(state["journal_path"], engine="openpyxl")
    actual = (df["action"] == action).sum()
    assert actual == count, f"Expected {count} rows with action '{action}', got {actual}"


@then('the journal sub_account does not contain "@"')
def check_no_at_in_sub_account(state: dict) -> None:
    df = pd.read_excel(state["journal_path"], engine="openpyxl")
    for val in df["sub_account"].dropna():
        assert "@" not in str(val), f"sub_account contains '@': {val!r}"


@then(parsers.parse("the stdout summary shows {count:d} events inserted"))
def check_inserted_count(result: subprocess.CompletedProcess[str], count: int) -> None:
    assert f"Events inserted:  {count}" in result.stdout, (
        f"Expected 'Events inserted:  {count}' in stdout:\n{result.stdout}"
    )


@then("the stdout summary contains an ERRORS section")
def check_errors_section(result: subprocess.CompletedProcess[str]) -> None:
    assert "ERRORS" in result.stdout, f"No ERRORS section in stdout:\n{result.stdout}"


@then("the stdout summary mentions the invalid file name")
def check_invalid_file_mentioned(result: subprocess.CompletedProcess[str]) -> None:
    assert "invalid_no_header" in result.stdout, (
        f"Expected invalid file name in stdout:\n{result.stdout}"
    )


@then("the journal contains events from the valid file only")
def check_only_valid_events(state: dict) -> None:
    df = pd.read_excel(state["journal_path"], engine="openpyxl")
    assert len(df) == 3, f"Expected 3 valid events, got {len(df)}"


@then(parsers.parse("the journal contains {count:d} event from the valid row"))
def check_one_valid_event(state: dict, count: int) -> None:
    df = pd.read_excel(state["journal_path"], engine="openpyxl")
    assert len(df) == count, f"Expected {count} event(s), got {len(df)}"
