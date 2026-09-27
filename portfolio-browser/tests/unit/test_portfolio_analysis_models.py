"""Unit tests for portfolio-analysis-service response models with no dedicated client test.

`ReturnHistogramResponse`/`HistogramStatistics`/`StdDevBand` are verified here against the
service's own OpenAPI example
(portfolio-analysis-service/specs/011-risk-return-histogram/contracts/openapi.yaml), not assumed.
"""

from __future__ import annotations

from datetime import date

from src.models.portfolio_analysis import ReturnHistogramResponse


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
