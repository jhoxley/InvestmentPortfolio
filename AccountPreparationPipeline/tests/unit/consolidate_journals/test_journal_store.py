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

    def test_contrib_fallback_key_date_action_value(self, tmp_path: Path) -> None:
        path = tmp_path / "j.xlsx"
        store = JournalStore.load(path)
        contrib = make_event(
            reference="Deposit",
            action=ActionType.CONTRIB,
            quantity=None,
            value=Decimal("1000.00"),
        )
        store.merge([contrib])
        store.save(path)
        store2 = JournalStore.load(path)
        inserted, merged = store2.merge([contrib])
        assert inserted == 0
        assert merged == 1
