import json
from pathlib import Path

import structlog

from app.exceptions import ProviderUnavailableError
from app.models.fallback import FallbackEntry

logger = structlog.get_logger(__name__)


class FallbackConfigRepository:
    def __init__(self, config_path: Path | None) -> None:
        self._config_path = config_path

    def lookup(self, identifier: str) -> FallbackEntry | None:
        if self._config_path is None:
            return None

        try:
            raw = json.loads(self._config_path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ProviderUnavailableError(
                f"Fallback config file not found: {self._config_path}"
            ) from exc

        normalised = identifier.upper()
        raw_entry = {k.upper(): v for k, v in raw.items()}.get(normalised)
        if raw_entry is None:
            logger.debug("fallback_config_miss", identifier=normalised)
            return None

        entry = FallbackEntry.model_validate(raw_entry)
        logger.debug(
            "fallback_config_hit",
            identifier=normalised,
            csv_path=str(entry.csv_path),
            use_local_only=entry.use_local_only,
        )
        return entry
