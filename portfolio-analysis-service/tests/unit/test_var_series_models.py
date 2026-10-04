"""Unit tests for the response models in app/models/var_series.py (013)."""

from datetime import date

from app.models.var_series import (
    BacktestConfidenceResult,
    ConfidenceLevelEstimate,
    MethodLookback,
    RollingExceptionPoint,
    VarBacktestResponse,
    VarMethodsResponse,
    VarSeriesEntry,
    VarSeriesResponse,
)


def _confidence_level(**overrides: object) -> ConfidenceLevelEstimate:
    defaults: dict[str, object] = {
        "confidence_bp": 9500,
        "var_gbp": 100.0,
        "var_pct": 10.0,
        "es_gbp": 120.0,
        "es_pct": 12.0,
        "hypothetical_exception": False,
        "ladder_exception": False,
    }
    defaults.update(overrides)
    return ConfidenceLevelEstimate.model_validate(defaults)


class TestVarSeriesResponse:
    """VarSeriesResponse.model_dump(by_alias=True) produces the HATEOAS _links key."""

    def test_links_alias_round_trips(self) -> None:
        entry = VarSeriesEntry(
            date=date(2026, 3, 2),
            outcome_date=date(2026, 3, 3),
            total_value_gbp=1000.0,
            scenario_count=520,
            actual_mv_pct=100.0,
            proxied_mv_pct=0.0,
            rescaled_mv_pct=0.0,
            quality="ok",
            quality_reason=None,
            hypothetical_pnl_gbp=-50.0,
            ladder_pnl_gbp=-50.0,
            levels=[_confidence_level()],
        )
        response = VarSeriesResponse(
            account_name="acct",
            lookback_code="2y",
            lookback_days=520,
            from_date=date(2026, 3, 2),
            to_date=date(2026, 3, 2),
            series=[entry],
            _links={"self": "/v1/accounts/acct/risk/var", "status": "s", "runs": "r"},
        )
        dumped = response.model_dump(by_alias=True, mode="json")
        assert dumped["_links"]["self"] == "/v1/accounts/acct/risk/var"
        assert "links" not in dumped

    def test_nullable_confidence_fields_accept_none(self) -> None:
        level = _confidence_level(
            var_gbp=None,
            var_pct=None,
            es_gbp=None,
            es_pct=None,
            hypothetical_exception=None,
            ladder_exception=None,
        )
        assert level.var_gbp is None
        assert level.hypothetical_exception is None


class TestVarBacktestResponse:
    """VarBacktestResponse.model_dump(by_alias=True) produces the HATEOAS _links key."""

    def test_links_alias_round_trips_and_nullable_fields_accept_none(self) -> None:
        result = BacktestConfidenceResult(
            confidence_bp=9900,
            observation_count=0,
            exception_count=0,
            expected_exceptions=None,
            exception_rate=None,
            kupiec_lr=None,
            kupiec_p_value=None,
            christoffersen_independence_lr=None,
            christoffersen_independence_p_value=None,
            conditional_coverage_lr=None,
            conditional_coverage_p_value=None,
            zone=None,
            exception_dates=[],
            mean_var_gbp=None,
            var_stability=None,
            rolling_exceptions=None,
        )
        response = VarBacktestResponse(
            account_name="acct",
            lookback_code="2y",
            lookback_days=520,
            from_date=date(2026, 3, 2),
            to_date=date(2026, 3, 2),
            pnl_basis="hypothetical",
            min_quality="degraded",
            levels=[result],
            _links={"self": "s", "status": "st", "runs": "r"},
        )
        dumped = response.model_dump(by_alias=True, mode="json")
        assert dumped["_links"]["self"] == "s"
        assert dumped["levels"][0]["zone"] is None
        assert dumped["levels"][0]["rolling_exceptions"] is None

    def test_rolling_exceptions_accepts_a_list(self) -> None:
        result = BacktestConfidenceResult(
            confidence_bp=9900,
            observation_count=300,
            exception_count=3,
            expected_exceptions=3.0,
            exception_rate=0.01,
            kupiec_lr=0.1,
            kupiec_p_value=0.9,
            christoffersen_independence_lr=0.1,
            christoffersen_independence_p_value=0.9,
            conditional_coverage_lr=0.2,
            conditional_coverage_p_value=0.95,
            zone="green",
            exception_dates=[date(2026, 1, 5)],
            mean_var_gbp=100.0,
            var_stability=0.02,
            rolling_exceptions=[RollingExceptionPoint(date=date(2026, 3, 2), exception_count=2)],
        )
        assert result.rolling_exceptions is not None
        assert result.rolling_exceptions[0].exception_count == 2


class TestVarMethodsResponse:
    """VarMethodsResponse.model_dump(by_alias=True) produces the HATEOAS _links key."""

    def test_links_alias_round_trips(self) -> None:
        response = VarMethodsResponse(
            method="historical-simulation",
            methodology_version="1.0.0",
            lookbacks=[
                MethodLookback(code="1y", business_days=260, is_headline=False),
                MethodLookback(code="2y", business_days=520, is_headline=True),
            ],
            confidence_levels_bp=[9500, 9750, 9900],
            measures=["var_gbp", "es_gbp"],
            _links={"self": "/v1/risk/var/methods"},
        )
        dumped = response.model_dump(by_alias=True, mode="json")
        assert dumped["_links"]["self"] == "/v1/risk/var/methods"
        assert dumped["lookbacks"][1]["is_headline"] is True
