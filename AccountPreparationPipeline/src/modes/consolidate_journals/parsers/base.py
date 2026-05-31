from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from src.modes.consolidate_journals.schema import ParseResult


@runtime_checkable
class FragmentParser(Protocol):
    def parse(self, file_path: Path, account: str) -> ParseResult: ...
