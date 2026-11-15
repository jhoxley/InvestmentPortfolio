"""Unit tests for IdentifierMappingEntry's optional `theme` field (015-var-contributions)."""

from app.models.market_data import IdentifierMappingEntry


class TestIdentifierMappingEntryTheme:
    """`theme` is additive: old entries still validate, new entries round-trip."""

    def test_entry_without_theme_defaults_to_none(self) -> None:
        """An entry with no `theme` key still validates, with `theme is None`."""
        entry = IdentifierMappingEntry(name="Equity A", ticker="EQA.L")
        assert entry.theme is None

    def test_entry_with_theme_round_trips(self) -> None:
        """An entry with a `theme` key round-trips through model_dump()/validation."""
        entry = IdentifierMappingEntry(name="Equity A", ticker="EQA.L", theme="Global Equity")
        assert entry.theme == "Global Equity"
        reloaded = IdentifierMappingEntry.model_validate(entry.model_dump())
        assert reloaded.theme == "Global Equity"
