"""013-var-series-backtest-api SC-004: series/backtest read-endpoint timing.

Mirrors test_performance.py's TestVarPerformance seeding pattern, but seeds the VaR
store directly via VarRepository.commit() (no calculation run), since these endpoints
never trigger one.
"""

import time
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd

from app.config import VarSettings
from app.repositories.capital_repository import CapitalRepository
from app.repositories.ladder_repository import AccountMeta, LadderRepository
from app.repositories.var_repository import VarMeta, VarRepository
from app.services.accounts_service import AccountsService
from app.services.var.var_backtest_service import VarBacktestService
from app.services.var.var_series_service import VarSeriesService

_DATES = 2700


def _seed(
    tmp_path: Path, account: str
) -> tuple[LadderRepository, CapitalRepository, VarRepository]:
    """Seed a ladder plus _DATES days of estimates/outcomes across all configured look-backs."""
    ladder_repo = LadderRepository(data_dir=tmp_path)
    capital_repo = CapitalRepository(data_dir=tmp_path)
    var_repo = VarRepository(data_dir=tmp_path)

    days = pd.bdate_range(end=date.today() - pd.offsets.BDay(2), periods=_DATES)
    ladder_df = pd.DataFrame(
        [
            {
                "date": days[0].date(),
                "sub_account": "Equity A",
                "book_cost": 0.0,
                "quantity": 10.0,
                "total_income": 0.0,
                "price": 100.0,
                "market_value": 1000.0,
                "portfolio_weight": 1.0,
                "position_return": 0.0,
                "weighted_position_return": 0.0,
            }
        ]
    )
    ladder_repo.write(
        account,
        ladder_df,
        AccountMeta(
            account_name=account,
            checksum="perf-var-series",
            row_count=1,
            from_date=days[0].date(),
            to_date=days[-1].date(),
            sub_accounts=["Equity A"],
            ingested_at=datetime.now(UTC),
        ),
    )

    settings = VarSettings()
    estimate_rows = [
        {
            "date": d.date(),
            "method": "historical-simulation",
            "lookback_code": code,
            "lookback_days": lookback_days,
            "scenario_count": lookback_days,
            "excluded_scenarios": 0,
            "actual_mv_pct": 100.0,
            "proxied_mv_pct": 0.0,
            "rescaled_mv_pct": 0.0,
            "quality": "ok",
            "quality_reason": None,
            "var_9500_gbp": 100.0,
            "var_9750_gbp": 125.0,
            "var_9900_gbp": 150.0,
            "es_9500_gbp": 120.0,
            "es_9750_gbp": 150.0,
            "es_9900_gbp": 180.0,
            "row_fingerprint": "fp-perf",
            "methodology_version": "1.0.0",
            "run_id": "run-perf",
            "computed_at": datetime.now(UTC),
        }
        for d in days
        for code, lookback_days in settings.lookbacks.items()
    ]
    outcome_rows = [
        {
            "date": d.date(),
            "outcome_date": (d + pd.offsets.BDay(1)).date(),
            "outcome_status": "realised",
            "total_value_gbp": 1000.0,
            "risky_value_gbp": 1000.0,
            "hypothetical_pnl_gbp": -10.0,
            "ladder_pnl_gbp": -10.0,
            "row_fingerprint": "fp-perf",
            "run_id": "run-perf",
            "computed_at": datetime.now(UTC),
        }
        for d in days
    ]
    var_repo.commit(
        account,
        estimates=pd.DataFrame(estimate_rows),
        outcomes=pd.DataFrame(outcome_rows),
        instruments=pd.DataFrame(),
        meta=VarMeta(
            account_name=account,
            methodology_version="1.0.0",
            config_fingerprint="fp-cfg-perf",
            last_successful_run_id="run-perf",
            updated_at=datetime.now(UTC),
        ),
    )
    return ladder_repo, capital_repo, var_repo


class TestVarSeriesBacktestPerformance:
    """SC-004: series/backtest over ~2,700 days return in under 2 seconds."""

    def test_series_returns_within_2_seconds(self, tmp_path: Path) -> None:
        """VarSeriesService.get_series() over the full seeded range completes in <2s."""
        ladder_repo, capital_repo, var_repo = _seed(tmp_path, "perf-var-series")
        service = VarSeriesService(
            accounts_service=AccountsService(ladder_repo=ladder_repo, capital_repo=capital_repo),
            var_repo=var_repo,
            settings=VarSettings(),
        )

        start = time.perf_counter()
        response = service.get_series(
            account_name="perf-var-series",
            start=None,
            end=None,
            lookback="2y",
            confidence_levels_bp=None,
            today=date.today(),
        )
        elapsed = time.perf_counter() - start

        assert len(response.series) == _DATES
        assert elapsed <= 2.0, f"SC-004 violated: series took {elapsed:.2f}s (limit 2s)"

    def test_backtest_with_rolling_returns_within_2_seconds(self, tmp_path: Path) -> None:
        """VarBacktestService.get_backtest(rolling=True) over the full range completes in <2s."""
        ladder_repo, capital_repo, var_repo = _seed(tmp_path, "perf-var-backtest")
        service = VarBacktestService(
            accounts_service=AccountsService(ladder_repo=ladder_repo, capital_repo=capital_repo),
            var_repo=var_repo,
            settings=VarSettings(),
        )

        start = time.perf_counter()
        response = service.get_backtest(
            account_name="perf-var-backtest",
            start=None,
            end=None,
            lookback="2y",
            confidence_levels_bp=None,
            pnl_basis="hypothetical",
            min_quality="degraded",
            rolling=True,
            today=date.today(),
        )
        elapsed = time.perf_counter() - start

        assert response.levels[0].observation_count == _DATES
        assert elapsed <= 2.0, f"SC-004 violated: backtest took {elapsed:.2f}s (limit 2s)"
