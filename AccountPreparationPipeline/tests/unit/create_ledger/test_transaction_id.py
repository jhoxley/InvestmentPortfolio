from __future__ import annotations

import re

import pandas as pd

from src.modes.create_ledger.transaction_id import TransactionIDAssigner

JOURNAL_COLUMNS = ["date", "account", "sub_account", "action", "reference", "value", "quantity"]


def _make_df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=JOURNAL_COLUMNS)


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


class TestFirstTimeAssignment:
    def test_three_rows_get_sequential_ids(self) -> None:
        df = (
            _make_df(
                [
                    _row(date="2024-01-01", reference="B001"),
                    _row(date="2024-01-02", reference="B002"),
                    _row(date="2024-01-03", reference="B003"),
                ]
            )
            .sort_values(["date", "account", "sub_account", "reference"])
            .reset_index(drop=True)
        )
        result = TransactionIDAssigner().assign(df, {})
        assert list(result) == ["00001-001", "00002-001", "00003-001"]

    def test_single_row_gets_00001_001(self) -> None:
        df = _make_df([_row()])
        result = TransactionIDAssigner().assign(df, {})
        assert result.iloc[0] == "00001-001"

    def test_100_rows_all_have_001_suffix(self) -> None:
        rows = [_row(reference=f"B{i + 1:03d}") for i in range(100)]
        df = (
            _make_df(rows)
            .sort_values(["date", "account", "sub_account", "reference"])
            .reset_index(drop=True)
        )
        result = TransactionIDAssigner().assign(df, {})
        assert all(re.match(r"^\d{5}-001$", v) for v in result)
        assert result.iloc[-1] == "00100-001"

    def test_empty_df_returns_empty_series(self) -> None:
        df = pd.DataFrame(columns=JOURNAL_COLUMNS)
        result = TransactionIDAssigner().assign(df, {})
        assert len(result) == 0


class TestReRunAssignment:
    def _prior_ids(self, refs: list[tuple[str, str]]) -> dict[tuple[str, str, str, str], str]:
        """Build prior_ids from (reference, tid) pairs using default account/sub_account."""
        return {("2024-01-01", "ISA", "Vanguard Fund", ref): tid for ref, tid in refs}

    def test_known_row_keeps_its_prior_id(self) -> None:
        prior_ids = {("2024-01-01", "ISA", "Vanguard Fund", "B001"): "00001-001"}
        df = (
            _make_df([_row()])
            .sort_values(["date", "account", "sub_account", "reference"])
            .reset_index(drop=True)
        )
        result = TransactionIDAssigner().assign(df, prior_ids)
        assert list(result) == ["00001-001"]

    def test_new_row_between_existing_gets_suffix_002(self) -> None:
        prior_ids = {
            ("2024-01-01", "ISA", "Vanguard Fund", "B001"): "00001-001",
            ("2024-01-02", "ISA", "Vanguard Fund", "B002"): "00002-001",
            ("2024-01-03", "ISA", "Vanguard Fund", "B003"): "00003-001",
        }
        df = (
            _make_df(
                [
                    _row(date="2024-01-01", reference="B001"),
                    _row(date="2024-01-01", reference="B001a"),
                    _row(date="2024-01-02", reference="B002"),
                    _row(date="2024-01-03", reference="B003"),
                ]
            )
            .sort_values(["date", "account", "sub_account", "reference"])
            .reset_index(drop=True)
        )
        result = TransactionIDAssigner().assign(df, prior_ids)
        assert list(result) == ["00001-001", "00001-002", "00002-001", "00003-001"]

    def test_second_insertion_gets_suffix_003(self) -> None:
        prior_ids = {
            ("2024-01-01", "ISA", "Vanguard Fund", "B001"): "00001-001",
            ("2024-01-01", "ISA", "Vanguard Fund", "B001a"): "00001-002",
            ("2024-01-02", "ISA", "Vanguard Fund", "B002"): "00002-001",
        }
        df = (
            _make_df(
                [
                    _row(date="2024-01-01", reference="B001"),
                    _row(date="2024-01-01", reference="B001a"),
                    _row(date="2024-01-01", reference="B001b"),
                    _row(date="2024-01-02", reference="B002"),
                ]
            )
            .sort_values(["date", "account", "sub_account", "reference"])
            .reset_index(drop=True)
        )
        result = TransactionIDAssigner().assign(df, prior_ids)
        assert list(result) == ["00001-001", "00001-002", "00001-003", "00002-001"]

    def test_new_row_after_all_existing_gets_next_prefix(self) -> None:
        prior_ids = {
            ("2024-01-01", "ISA", "Vanguard Fund", "B001"): "00001-001",
            ("2024-01-02", "ISA", "Vanguard Fund", "B002"): "00002-001",
            ("2024-01-03", "ISA", "Vanguard Fund", "B003"): "00003-001",
        }
        df = (
            _make_df(
                [
                    _row(date="2024-01-01", reference="B001"),
                    _row(date="2024-01-02", reference="B002"),
                    _row(date="2024-01-03", reference="B003"),
                    _row(date="2024-01-04", reference="B004"),
                ]
            )
            .sort_values(["date", "account", "sub_account", "reference"])
            .reset_index(drop=True)
        )
        result = TransactionIDAssigner().assign(df, prior_ids)
        assert list(result) == ["00001-001", "00002-001", "00003-001", "00004-001"]

    def test_absent_key_in_prior_ids_has_no_effect(self) -> None:
        # prior_ids has a key that does not appear in the df — should not raise or corrupt IDs
        prior_ids = {("2024-01-01", "ISA", "Vanguard Fund", "B001-absent"): "00001-002"}
        df = (
            _make_df([_row()])
            .sort_values(["date", "account", "sub_account", "reference"])
            .reset_index(drop=True)
        )
        result = TransactionIDAssigner().assign(df, prior_ids)
        # No crash; B001 is not in prior_ids so it gets a first-time ID
        assert list(result) == ["00001-001"]
