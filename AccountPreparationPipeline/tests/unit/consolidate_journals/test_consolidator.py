from __future__ import annotations

import datetime
from decimal import Decimal
from pathlib import Path

from src.modes.consolidate_journals.schema import (
    ActionType,
    ConsolidationSummary,
    JournalEvent,
)

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "consolidate_journals"


def _make_event(ref: str = "B1") -> JournalEvent:
    return JournalEvent(
        date=datetime.date(2024, 1, 17),
        account="Test ISA",
        sub_account="Vanguard Fund",
        action=ActionType.BUY,
        reference=ref,
        value=Decimal("1000.00"),
        quantity=Decimal("5.00"),
    )


class TestConsolidationEngineRun:
    def test_valid_dir_produces_correct_summary(self, tmp_path: Path) -> None:
        from src.modes.consolidate_journals.consolidator import ConsolidationEngine
        from src.modes.consolidate_journals.schema import ConsolidationMethod

        journal_path = tmp_path / "journal.xlsx"
        engine = ConsolidationEngine()
        summary = engine.run(
            journal_path=journal_path,
            fragments_dir=DATA_DIR,
            method=ConsolidationMethod.HL,
            account="Test ISA",
        )
        assert isinstance(summary, ConsolidationSummary)
        assert summary.files_processed > 0
        assert summary.events_inserted >= 0

    def test_empty_dir_produces_zero_events(self, tmp_path: Path) -> None:
        from src.modes.consolidate_journals.consolidator import ConsolidationEngine
        from src.modes.consolidate_journals.schema import ConsolidationMethod

        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        journal_path = tmp_path / "journal.xlsx"
        engine = ConsolidationEngine()
        summary = engine.run(
            journal_path=journal_path,
            fragments_dir=empty_dir,
            method=ConsolidationMethod.HL,
            account="Test ISA",
        )
        assert summary.events_inserted == 0
        assert summary.files_processed == 0

    def test_errors_from_invalid_file_included_in_summary(self, tmp_path: Path) -> None:
        from src.modes.consolidate_journals.consolidator import ConsolidationEngine
        from src.modes.consolidate_journals.schema import ConsolidationMethod

        frag_dir = tmp_path / "frags"
        frag_dir.mkdir()
        (frag_dir / "bad.csv").write_text("no,header,here\nrow1,row2,row3\n", encoding="utf-8")
        journal_path = tmp_path / "journal.xlsx"
        engine = ConsolidationEngine()
        summary = engine.run(
            journal_path=journal_path,
            fragments_dir=frag_dir,
            method=ConsolidationMethod.HL,
            account="Test ISA",
        )
        assert len(summary.errors) == 1
        assert summary.events_inserted == 0

    def test_engine_continues_after_file_error(self, tmp_path: Path) -> None:
        from src.modes.consolidate_journals.consolidator import ConsolidationEngine
        from src.modes.consolidate_journals.schema import ConsolidationMethod

        frag_dir = tmp_path / "frags"
        frag_dir.mkdir()
        (frag_dir / "bad.csv").write_text("garbage,data\n", encoding="utf-8")
        import shutil

        shutil.copy(DATA_DIR / "valid_hl_simple.csv", frag_dir / "valid.csv")
        journal_path = tmp_path / "journal.xlsx"
        engine = ConsolidationEngine()
        summary = engine.run(
            journal_path=journal_path,
            fragments_dir=frag_dir,
            method=ConsolidationMethod.HL,
            account="Test ISA",
        )
        assert summary.events_inserted == 3
        assert len(summary.errors) >= 1
