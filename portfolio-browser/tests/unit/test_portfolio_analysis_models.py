"""Unit tests for portfolio-analysis-service response models with no dedicated client test.

`ReturnHistogramResponse`/`HistogramStatistics`/`StdDevBand` are verified here against the
service's own OpenAPI example
(portfolio-analysis-service/specs/011-risk-return-histogram/contracts/openapi.yaml), not assumed.
"""

from __future__ import annotations

from datetime import date

from src.models.portfolio_analysis import (
    BacktestConfidenceResult,
    ConfidenceLevelEstimate,
    DateRange,
    MethodLookback,
    ReturnHistogramResponse,
    RollingExceptionPoint,
    VarBacktestResponse,
    VarMethodsResponse,
    VarSeriesEntry,
    VarSeriesResponse,
    VarStatusSummary,
)


def test_return_histogram_response_parses_example_payload() -> None:
    payload = {
        "account_name": "HL-SIPP",
        "from_date": "2024-01-02",
        "to_date": "2024-12-31",
        "histogram": [[-25, 1], [-3, 4], [0, 12], [7, 9], [65, 1]],
        "statistics": {
            "count": 27,
            "mean": 4.1,
            "median": 3.0,
            "mode": 0,
            "minimum": -25,
            "maximum": 65,
            "std_dev": 14.2,
            "std_dev_bands": [
                {"sigma": 1, "multiple": 14.2, "lower": -10.1, "upper": 18.3},
                {"sigma": 2, "multiple": 28.4, "lower": -24.3, "upper": 32.5},
                {"sigma": 3, "multiple": 42.6, "lower": -38.5, "upper": 46.7},
            ],
            "skewness": 1.8,
            "kurtosis": 6.2,
        },
        "_links": {
            "self": "/v1/accounts/HL-SIPP/risk/return-histogram?start=2024-01-02&end=2024-12-31",
            "accounts": "/v1/accounts",
        },
    }

    response = ReturnHistogramResponse.model_validate(payload)

    assert response.account_name == "HL-SIPP"
    assert response.from_date == date(2024, 1, 2)
    assert response.to_date == date(2024, 12, 31)
    assert response.histogram == [(-25, 1), (-3, 4), (0, 12), (7, 9), (65, 1)]
    assert response.statistics.count == 27
    assert response.statistics.mean == 4.1
    assert response.statistics.std_dev == 14.2
    assert len(response.statistics.std_dev_bands) == 3
    assert response.statistics.std_dev_bands[0].sigma == 1
    assert response.statistics.skewness == 1.8
    assert response.statistics.kurtosis == 6.2
    assert response.links == {
        "self": "/v1/accounts/HL-SIPP/risk/return-histogram?start=2024-01-02&end=2024-12-31",
        "accounts": "/v1/accounts",
    }


def test_return_histogram_response_parses_zero_count_payload() -> None:
    """count == 0 leaves every scalar statistic null and std_dev_bands empty."""
    payload = {
        "account_name": "EMPTY-ACCT",
        "from_date": "2026-01-05",
        "to_date": "2026-01-05",
        "histogram": [],
        "statistics": {
            "count": 0,
            "mean": None,
            "median": None,
            "mode": None,
            "minimum": None,
            "maximum": None,
            "std_dev": None,
            "std_dev_bands": [],
            "skewness": None,
            "kurtosis": None,
        },
        "_links": {},
    }

    response = ReturnHistogramResponse.model_validate(payload)

    assert response.histogram == []
    stats = response.statistics
    assert stats.count == 0
    assert stats.mean is None
    assert stats.median is None
    assert stats.mode is None
    assert stats.minimum is None
    assert stats.maximum is None
    assert stats.std_dev is None
    assert stats.std_dev_bands == []
    assert stats.skewness is None
    assert stats.kurtosis is None


# --- 026-var-risk-view: new models, verified against portfolio-analysis-service's own
# 012/013 OpenAPI examples (specs/012-var-calculation-runs,
# specs/013-var-series-backtest-api), not assumed.


def test_date_range_parses() -> None:
    rng = DateRange.model_validate({"from_date": "2026-01-02", "to_date": "2026-03-02"})
    assert rng.from_date == date(2026, 1, 2)
    assert rng.to_date == date(2026, 3, 2)


def test_var_status_summary_ignores_extra_fields_and_handles_null_computed_range() -> None:
    """A full 012 VarStatus payload validates; unused fields are silently ignored."""
    payload: dict[str, object] = {
        "account_name": "HL-SIPP",
        "ladder_range": {"from_date": "2016-04-20", "to_date": "2026-10-01"},
        "computed_range": None,
        "missing_dates": 2700,
        "stale_dates_last_run": 0,
        "pending_outcomes": 0,
        "methodology_version": "1.0.0",
        "last_run": None,
        "instruments": [],
        "warnings": [],
        "_links": {"self": "/v1/accounts/HL-SIPP/risk/var/status"},
    }
    status = VarStatusSummary.model_validate(payload)
    assert status.account_name == "HL-SIPP"
    assert status.computed_range is None
    assert status.missing_dates == 2700
    assert status.links == {"self": "/v1/accounts/HL-SIPP/risk/var/status"}


def test_var_status_summary_parses_computed_range() -> None:
    payload = {
        "account_name": "HL-SIPP",
        "computed_range": {"from_date": "2026-01-02", "to_date": "2026-09-30"},
        "missing_dates": 1,
        "_links": {},
    }
    status = VarStatusSummary.model_validate(payload)
    assert status.computed_range == DateRange(from_date=date(2026, 1, 2), to_date=date(2026, 9, 30))


def test_confidence_level_estimate_parses_and_accepts_nulls() -> None:
    full = ConfidenceLevelEstimate.model_validate(
        {
            "confidence_bp": 9500,
            "var_gbp": 100.0,
            "var_pct": 10.0,
            "es_gbp": 120.0,
            "es_pct": 12.0,
            "hypothetical_exception": False,
            "ladder_exception": False,
        }
    )
    assert full.confidence_bp == 9500
    assert full.var_gbp == 100.0

    insufficient = ConfidenceLevelEstimate.model_validate(
        {
            "confidence_bp": 9900,
            "var_gbp": None,
            "var_pct": None,
            "es_gbp": None,
            "es_pct": None,
            "hypothetical_exception": None,
            "ladder_exception": None,
        }
    )
    assert insufficient.var_gbp is None
    assert insufficient.hypothetical_exception is None


def test_var_series_response_parses_example_payload() -> None:
    payload = {
        "account_name": "HL-SIPP",
        "lookback_code": "2y",
        "lookback_days": 520,
        "from_date": "2026-03-02",
        "to_date": "2026-03-02",
        "series": [
            {
                "date": "2026-03-02",
                "outcome_date": "2026-03-03",
                "total_value_gbp": 1000.0,
                "scenario_count": 520,
                "actual_mv_pct": 100.0,
                "proxied_mv_pct": 0.0,
                "rescaled_mv_pct": 0.0,
                "quality": "ok",
                "quality_reason": None,
                "hypothetical_pnl_gbp": -50.0,
                "ladder_pnl_gbp": -50.0,
                "levels": [
                    {
                        "confidence_bp": 9500,
                        "var_gbp": 100.0,
                        "var_pct": 10.0,
                        "es_gbp": 120.0,
                        "es_pct": 12.0,
                        "hypothetical_exception": False,
                        "ladder_exception": False,
                    }
                ],
            }
        ],
        "_links": {
            "self": "/v1/accounts/HL-SIPP/risk/var",
            "status": "/v1/accounts/HL-SIPP/risk/var/status",
            "runs": "/v1/accounts/HL-SIPP/risk/var/runs",
        },
    }

    response = VarSeriesResponse.model_validate(payload)

    assert response.lookback_code == "2y"
    assert len(response.series) == 1
    entry = response.series[0]
    assert isinstance(entry, VarSeriesEntry)
    assert entry.quality == "ok"
    assert entry.levels[0].var_gbp == 100.0
    assert response.links["status"] == "/v1/accounts/HL-SIPP/risk/var/status"


def test_var_series_response_parses_empty_series() -> None:
    payload = {
        "account_name": "HL-SIPP",
        "lookback_code": "2y",
        "lookback_days": 520,
        "from_date": "2026-01-02",
        "to_date": "2026-09-30",
        "series": [],
        "_links": {"self": "s", "status": "st", "runs": "r"},
    }
    response = VarSeriesResponse.model_validate(payload)
    assert response.series == []


def test_var_backtest_response_parses_example_payload() -> None:
    payload = {
        "account_name": "HL-SIPP",
        "lookback_code": "2y",
        "lookback_days": 520,
        "from_date": "2026-01-02",
        "to_date": "2026-09-30",
        "pnl_basis": "hypothetical",
        "min_quality": "degraded",
        "levels": [
            {
                "confidence_bp": 9900,
                "observation_count": 250,
                "exception_count": 6,
                "expected_exceptions": 2.5,
                "exception_rate": 0.024,
                "kupiec_lr": 4.2,
                "kupiec_p_value": 0.04,
                "christoffersen_independence_lr": 0.5,
                "christoffersen_independence_p_value": 0.48,
                "conditional_coverage_lr": 4.7,
                "conditional_coverage_p_value": 0.09,
                "zone": "yellow",
                "exception_dates": ["2026-02-10", "2026-03-15"],
                "mean_var_gbp": 105.5,
                "var_stability": 0.021,
                "rolling_exceptions": None,
            }
        ],
        "_links": {"self": "s", "status": "st", "runs": "r"},
    }

    response = VarBacktestResponse.model_validate(payload)

    assert response.pnl_basis == "hypothetical"
    level = response.levels[0]
    assert isinstance(level, BacktestConfidenceResult)
    assert level.zone == "yellow"
    assert level.exception_dates == [date(2026, 2, 10), date(2026, 3, 15)]
    assert level.rolling_exceptions is None


def test_var_backtest_response_parses_null_zone_and_rolling_points() -> None:
    payload = {
        "account_name": "HL-SIPP",
        "lookback_code": "2y",
        "lookback_days": 520,
        "from_date": "2026-01-02",
        "to_date": "2026-01-02",
        "pnl_basis": "ladder",
        "min_quality": "ok",
        "levels": [
            {
                "confidence_bp": 9500,
                "observation_count": 0,
                "exception_count": 0,
                "expected_exceptions": None,
                "exception_rate": None,
                "kupiec_lr": None,
                "kupiec_p_value": None,
                "christoffersen_independence_lr": None,
                "christoffersen_independence_p_value": None,
                "conditional_coverage_lr": None,
                "conditional_coverage_p_value": None,
                "zone": None,
                "exception_dates": [],
                "mean_var_gbp": None,
                "var_stability": None,
                "rolling_exceptions": [{"date": "2026-03-02", "exception_count": 2}],
            }
        ],
        "_links": {"self": "s", "status": "st", "runs": "r"},
    }

    response = VarBacktestResponse.model_validate(payload)

    level = response.levels[0]
    assert level.zone is None
    assert level.rolling_exceptions is not None
    assert isinstance(level.rolling_exceptions[0], RollingExceptionPoint)
    assert level.rolling_exceptions[0].exception_count == 2


def test_var_methods_response_parses_example_payload() -> None:
    payload = {
        "method": "historical-simulation",
        "methodology_version": "1.0.0",
        "lookbacks": [
            {"code": "1y", "business_days": 260, "is_headline": False},
            {"code": "2y", "business_days": 520, "is_headline": True},
            {"code": "5y", "business_days": 1300, "is_headline": False},
        ],
        "confidence_levels_bp": [9500, 9750, 9900],
        "measures": ["var_gbp", "es_gbp"],
        "_links": {"self": "/v1/risk/var/methods"},
    }

    response = VarMethodsResponse.model_validate(payload)

    assert isinstance(response.lookbacks[1], MethodLookback)
    assert [lb.code for lb in response.lookbacks if lb.is_headline] == ["2y"]
    assert response.confidence_levels_bp == [9500, 9750, 9900]
    assert response.links["self"] == "/v1/risk/var/methods"
