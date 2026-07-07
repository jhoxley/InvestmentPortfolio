"""Repository for loading the sub-account-to-identifier mapping file."""

import json
from pathlib import Path

import structlog

from app.models.market_data import IdentifierMappingEntry

logger = structlog.get_logger(__name__)


class IdentifierMappingRepository:
    """Loads and looks up the configured sub-account-to-identifier mapping JSON file.

    The mapping file is a JSON array of objects keyed by a `name` field, each providing
    an `isin` and/or `ticker` field. It is loaded lazily on first `lookup()` call and
    cached in memory for the lifetime of this instance.
    """

    def __init__(self, mapping_path: Path | None) -> None:
        """Initialise with the configured mapping file path.

        Args:
            mapping_path: Path to the identifier mapping JSON file, or None if unconfigured.
        """
        self._mapping_path = mapping_path
        self._entries: dict[str, IdentifierMappingEntry] | None = None

    def _load(self) -> dict[str, IdentifierMappingEntry]:
        """Load and cache the mapping file contents.

        Returns:
            Mapping of sub-account name to IdentifierMappingEntry.

        Raises:
            ValueError: If no mapping path is configured, the file does not exist, or it is
                not valid JSON.
        """
        if self._mapping_path is None:
            logger.error("identifier_mapping_load_error", reason="not_configured")
            raise ValueError(
                "No identifier mapping file is configured (identifier_mapping.path is unset)."
            )
        if not self._mapping_path.exists():
            logger.error(
                "identifier_mapping_load_error",
                reason="file_not_found",
                path=str(self._mapping_path),
            )
            raise ValueError(f"Identifier mapping file not found: {self._mapping_path}")
        try:
            raw = json.loads(self._mapping_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            logger.error(
                "identifier_mapping_load_error",
                reason="invalid_json",
                path=str(self._mapping_path),
            )
            raise ValueError(
                f"Identifier mapping file is not valid JSON: {self._mapping_path}"
            ) from exc

        entries = {
            item["name"]: IdentifierMappingEntry.model_validate(item)
            for item in raw
            if "name" in item
        }
        logger.info(
            "identifier_mapping_loaded",
            path=str(self._mapping_path),
            entry_count=len(entries),
        )
        return entries

    def lookup(self, sub_account: str) -> IdentifierMappingEntry | None:
        """Return the mapping entry for a sub-account, or None if not found.

        Args:
            sub_account: The sub-account name to look up (exact, case-sensitive match).

        Returns:
            The matching IdentifierMappingEntry, or None if no entry exists.
        """
        if self._entries is None:
            self._entries = self._load()
        entry = self._entries.get(sub_account)
        if entry is None:
            logger.debug("identifier_mapping_miss", sub_account=sub_account)
        return entry
