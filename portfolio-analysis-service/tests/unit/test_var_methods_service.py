"""Unit tests for build_methods_response() -- the methods-discovery endpoint's logic."""

from app.config import VarSettings
from app.services.var.var_methods_service import build_methods_response


class TestBuildMethodsResponse:
    """build_methods_response() is a pure function of VarSettings, no I/O."""

    def test_lists_every_configured_lookback_with_business_days(self) -> None:
        """Every configured look-back appears with its business-day length."""
        settings = VarSettings()
        response = build_methods_response(settings)

        by_code = {lb.code: lb for lb in response.lookbacks}
        assert by_code["1y"].business_days == 260
        assert by_code["2y"].business_days == 520
        assert by_code["5y"].business_days == 1300

    def test_marks_exactly_the_headline_lookback(self) -> None:
        """Only the configured headline_lookback has is_headline=True."""
        settings = VarSettings(headline_lookback="1y")
        response = build_methods_response(settings)

        headline = [lb for lb in response.lookbacks if lb.is_headline]
        assert [lb.code for lb in headline] == ["1y"]

    def test_lists_configured_confidence_levels(self) -> None:
        """confidence_levels_bp matches the configured settings exactly."""
        settings = VarSettings()
        response = build_methods_response(settings)

        assert response.confidence_levels_bp == [9500, 9750, 9900]

    def test_measures_list_is_non_empty(self) -> None:
        """The static measures list is never empty."""
        response = build_methods_response(VarSettings())
        assert len(response.measures) > 0

    def test_links_self_is_set(self) -> None:
        """_links.self points at the methods endpoint's own path."""
        response = build_methods_response(VarSettings())
        assert response.links["self"] == "/v1/risk/var/methods"

    def test_method_and_methodology_version(self) -> None:
        """Method is fixed and methodology_version echoes settings."""
        settings = VarSettings(methodology_version="1.2.3")
        response = build_methods_response(settings)
        assert response.method == "historical-simulation"
        assert response.methodology_version == "1.2.3"
