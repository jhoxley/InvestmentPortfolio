import structlog

from app.models.pricing import TickerResolutionResponse
from app.providers.identifier_provider import IdentifierProvider
from app.validators.identifier import detect_identifier_type, validate_identifier_format

logger = structlog.get_logger(__name__)


class IdentifierService:
    def __init__(self, provider: IdentifierProvider) -> None:
        self._provider = provider

    def resolve(self, identifier: str, type_hint: str | None) -> TickerResolutionResponse:
        normalised = identifier.upper()

        if type_hint is not None:
            validate_identifier_format(normalised, type_hint)
            identifier_type = type_hint.upper()
        else:
            identifier_type = detect_identifier_type(normalised)

        logger.info(
            "identifier_lookup",
            identifier=normalised,
            identifier_type=identifier_type,
            type_hint=type_hint,
        )

        result = self._provider.lookup_ticker(normalised, identifier_type)

        logger.info(
            "identifier_resolved",
            identifier=normalised,
            ticker=result["ticker"],
            exchange=result["exchange"],
        )

        return TickerResolutionResponse(
            identifier=normalised,
            identifier_type=identifier_type,
            ticker=str(result["ticker"]),
            security_name=str(result["security_name"]),
            exchange=str(result["exchange"]),
        )
