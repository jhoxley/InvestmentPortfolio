"""Unit tests for IdentifierMappingRepository.entries()."""

import json
from pathlib import Path

import pytest

from app.repositories.identifier_mapping_repository import IdentifierMappingRepository


@pytest.fixture()
def mapping_file(tmp_path: Path) -> Path:
    """Write a two-entry mapping file and return its path."""
    path = tmp_path / "mapping.json"
    path.write_text(
        json.dumps(
            [
                {"name": "Equity A", "ticker": "EQA.L"},
                {
                    "name": "Scottish Widows Pension",
                    "isin": "SWPENSION",
                    "var_proxy": "GB00B08HD927",
                    "var_proxy_mode": "always",
                    "var_proxy_scale": 1.5,
                },
            ]
        ),
        encoding="utf-8",
    )
    return path


class TestEntries:
    """entries() returns every configured mapping entry, loading lazily."""

    def test_returns_all_entries(self, mapping_file: Path) -> None:
        """entries() returns every name configured in the file."""
        repo = IdentifierMappingRepository(mapping_file)
        entries = repo.entries()
        assert {e.name for e in entries} == {"Equity A", "Scottish Widows Pension"}

    def test_returns_entries_with_proxy_fields(self, mapping_file: Path) -> None:
        """An entry with var_proxy fields round-trips them."""
        repo = IdentifierMappingRepository(mapping_file)
        entries = {e.name: e for e in repo.entries()}
        sw = entries["Scottish Widows Pension"]
        assert sw.var_proxy == "GB00B08HD927"
        assert sw.var_proxy_mode == "always"
        assert sw.var_proxy_scale == pytest.approx(1.5)

    def test_entry_without_proxy_fields_has_defaults(self, mapping_file: Path) -> None:
        """An entry without var_proxy fields gets the documented defaults."""
        repo = IdentifierMappingRepository(mapping_file)
        entries = {e.name: e for e in repo.entries()}
        eq_a = entries["Equity A"]
        assert eq_a.var_proxy is None
        assert eq_a.var_proxy_mode == "fill_gaps"
        assert eq_a.var_proxy_scale == pytest.approx(1.0)

    def test_raises_when_not_configured(self) -> None:
        """entries() raises the same ValueError as lookup() when unconfigured."""
        repo = IdentifierMappingRepository(None)
        with pytest.raises(ValueError, match="is unset"):
            repo.entries()

    def test_lazy_load_cached_across_calls(self, mapping_file: Path) -> None:
        """The file is read once; a later on-disk change is not picked up."""
        repo = IdentifierMappingRepository(mapping_file)
        first = repo.entries()
        mapping_file.write_text(json.dumps([]), encoding="utf-8")
        second = repo.entries()
        assert len(first) == len(second) == 2
