from __future__ import annotations

import datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd

from src.modes.consolidate_journals.constants import JOURNAL_COLUMNS
from src.modes.consolidate_journals.journal_store import JournalStore
from src.modes.consolidate_journals.schema import ActionType, JournalEvent


def make_event(
    reference: str = "B12345",
    date: datetime.date = datetime.date(2024, 1, 17),
    action: ActionType = ActionType.BUY,
    sub_account: str = "Vanguard Fund",
    value: Decimal = Decimal("1000.00"),
    quantity: Decimal | None = Decimal("5.00"),
) -> JournalEvent:
    return JournalEvent(
        date=date,
        account="Test ISA",
        sub_account=sub_account,
        action=action,
        reference=reference,
        value=value,
        quantity=quantity,
    )


class TestLoad:
    def test_load_nonexistent_path_returns_empty_store(self, tmp_path: Path) -> None:
        store = JournalStore.load(tmp_path / "nonexistent.xlsx")
        assert store.row_count == 0

    def test_load_existing_xlsx_reads_data(self, tmp_path: Path) -> None:
        path = tmp_path / "journal.xlsx"
        df = pd.DataFrame(
            [
                {
                    "date": datetime.date(2024, 1, 1),
                    "account": "ISA",
                    "sub_account": "Fund A",
                    "action": "buy",
                    "reference": "B1",
                    "value": 100.0,
                    "quantity": 1.0,
                }
            ]
        )
        df.to_excel(path, index=False, engine="openpyxl")
        store = JournalStore.load(path)
        assert store.row_count == 1


class TestSave:
    def test_save_creates_xlsx_with_correct_columns(self, tmp_path: Path) -> None:
        path = tmp_path / "journal.xlsx"
        store = JournalStore.load(path)
        store.save(path)
        assert path.exists()
        df = pd.read_excel(path, engine="openpyxl")
        assert list(df.columns) == JOURNAL_COLUMNS

    def test_save_preserves_row_data(self, tmp_path: Path) -> None:
        path = tmp_path / "journal.xlsx"
        store = JournalStore.load(path)
        event = make_event()
        store.merge([event])
        store.save(path)
        df = pd.read_excel(path, engine="openpyxl")
        assert len(df) == 1
        assert df.iloc[0]["reference"] == "B12345"


class TestMerge:
    def test_new_events_all_inserted(self, tmp_path: Path) -> None:
        store = JournalStore.load(tmp_path / "j.xlsx")
        events = [make_event("B1"), make_event("B2"), make_event("B3")]
        inserted, merged = store.merge(events)
        assert inserted == 3
        assert merged == 0
        assert store.row_count == 3

    def test_duplicate_events_skipped(self, tmp_path: Path) -> None:
        path = tmp_path / "j.xlsx"
        store = JournalStore.load(path)
        event = make_event("B12345")
        store.merge([event])
        store.save(path)
        store2 = JournalStore.load(path)
        inserted, merged = store2.merge([event])
        assert inserted == 0
        assert merged == 1
        assert store2.row_count == 1

    def test_mix_of_new_and_duplicate(self, tmp_path: Path) -> None:
        path = tmp_path / "j.xlsx"
        store = JournalStore.load(path)
        store.merge([make_event("B1")])
        store.save(path)
        store2 = JournalStore.load(path)
        inserted, merged = store2.merge([make_event("B1"), make_event("B2")])
        assert inserted == 1
        assert merged == 1
        assert store2.row_count == 2

    def test_deposit_fallback_key_date_action_value(self, tmp_path: Path) -> None:
        path = tmp_path / "j.xlsx"
        store = JournalStore.load(path)
        deposit = make_event(
            reference="Deposit",
            action=ActionType.DEPOSIT,
            quantity=None,
            value=Decimal("1000.00"),
        )
        store.merge([deposit])
        store.save(path)
        store2 = JournalStore.load(path)
        inserted, merged = store2.merge([deposit])
        assert inserted == 0
        assert merged == 1


class TestRectifyOffsets:
    def _store_with_buy_and_wrong_offset(self) -> JournalStore:
        buy = make_event(reference="B12345", action=ActionType.BUY, value=Decimal("-1000.00"))
        wrong_offset = make_event(
            reference="B12345-offset",
            action=ActionType.TRADING,
            sub_account="Cash",
            value=Decimal("1000.00"),
            quantity=Decimal("1000.00"),
        )
        store = JournalStore(
            pd.DataFrame(
                [
                    {
                        "date": str(buy.date),
                        "account": buy.account,
                        "sub_account": buy.sub_account,
                        "action": str(buy.action),
                        "reference": buy.reference,
                        "value": float(buy.value),
                        "quantity": float(buy.quantity),  # type: ignore[arg-type]
                    },
                    {
                        "date": str(wrong_offset.date),
                        "account": wrong_offset.account,
                        "sub_account": wrong_offset.sub_account,
                        "action": str(wrong_offset.action),
                        "reference": wrong_offset.reference,
                        "value": float(wrong_offset.value),
                        "quantity": float(wrong_offset.quantity),  # type: ignore[arg-type]
                    },
                ]
            )
        )
        return store

    def test_rectify_offsets_corrects_wrong_sign_buy(self) -> None:
        store = self._store_with_buy_and_wrong_offset()
        corrected = store.rectify_offsets()
        assert corrected == 1
        df = store._df
        offset_row = df[df["reference"] == "B12345-offset"].iloc[0]
        assert float(offset_row["value"]) == -1000.0

    def test_rectify_offsets_corrects_wrong_sign_sell(self) -> None:
        sell = make_event(reference="S67890", action=ActionType.SELL, value=Decimal("500.00"))
        wrong_offset = make_event(
            reference="S67890-offset",
            action=ActionType.TRADING,
            sub_account="Cash",
            value=Decimal("-500.00"),
            quantity=Decimal("-500.00"),
        )
        store = JournalStore(
            pd.DataFrame(
                [
                    {
                        "date": str(sell.date),
                        "account": sell.account,
                        "sub_account": sell.sub_account,
                        "action": str(sell.action),
                        "reference": sell.reference,
                        "value": float(sell.value),
                        "quantity": float(sell.quantity),  # type: ignore[arg-type]
                    },
                    {
                        "date": str(wrong_offset.date),
                        "account": wrong_offset.account,
                        "sub_account": wrong_offset.sub_account,
                        "action": str(wrong_offset.action),
                        "reference": wrong_offset.reference,
                        "value": float(wrong_offset.value),
                        "quantity": float(wrong_offset.quantity),  # type: ignore[arg-type]
                    },
                ]
            )
        )
        corrected = store.rectify_offsets()
        assert corrected == 1
        offset_row = store._df[store._df["reference"] == "S67890-offset"].iloc[0]
        assert float(offset_row["value"]) == 500.0

    def test_rectify_offsets_no_change_when_correct(self) -> None:
        buy = make_event(reference="B11111", action=ActionType.BUY, value=Decimal("-750.00"))
        correct_offset = make_event(
            reference="B11111-offset",
            action=ActionType.TRADING,
            sub_account="Cash",
            value=Decimal("-750.00"),
            quantity=Decimal("-750.00"),
        )
        store = JournalStore(
            pd.DataFrame(
                [
                    {
                        "date": str(buy.date),
                        "account": buy.account,
                        "sub_account": buy.sub_account,
                        "action": str(buy.action),
                        "reference": buy.reference,
                        "value": float(buy.value),
                        "quantity": float(buy.quantity),  # type: ignore[arg-type]
                    },
                    {
                        "date": str(correct_offset.date),
                        "account": correct_offset.account,
                        "sub_account": correct_offset.sub_account,
                        "action": str(correct_offset.action),
                        "reference": correct_offset.reference,
                        "value": float(correct_offset.value),
                        "quantity": float(correct_offset.quantity),  # type: ignore[arg-type]
                    },
                ]
            )
        )
        corrected = store.rectify_offsets()
        assert corrected == 0
        offset_row = store._df[store._df["reference"] == "B11111-offset"].iloc[0]
        assert float(offset_row["value"]) == -750.0

    def test_rectify_offsets_does_not_touch_non_offset_rows(self) -> None:
        store = self._store_with_buy_and_wrong_offset()
        deposit = make_event(
            reference="Deposit",
            action=ActionType.DEPOSIT,
            value=Decimal("2000.00"),
            quantity=None,
        )
        store.merge([deposit])
        original_deposit_value = store._df[store._df["reference"] == "Deposit"].iloc[0]["value"]
        original_buy_value = store._df[store._df["reference"] == "B12345"].iloc[0]["value"]

        store.rectify_offsets()

        assert float(store._df[store._df["reference"] == "Deposit"].iloc[0]["value"]) == float(
            original_deposit_value
        )
        assert float(store._df[store._df["reference"] == "B12345"].iloc[0]["value"]) == float(
            original_buy_value
        )
