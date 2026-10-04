"""Unit tests for VarStatusService: coverage/freshness reporting without reading the ladder."""

from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from app.models.var import VarRun
from app.repositories.capital_repository import CapitalRepository
from app.repositories.ladder_repository import AccountMeta, LadderRepository
from app.repositories.var_repository import VarMeta, VarRepository
from app.services.accounts_service import AccountsService
from app.services.var.var_status_service import VarStatusService


def _write_ladder(repo: LadderRepository, account: str, from_date: date, to_date: date) -> None:
    days = pd.bdate_range(start=from_date, end=to_date)
    df = pd.DataFrame(
        [
            {
                "date": d.date(),
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
            for d in days
        ]
    )
    meta = AccountMeta(
        account_name=account,
        checksum="x",
        row_count=len(df),
        from_date=from_date,
        to_date=to_date,
        sub_accounts=["Equity A"],
        ingested_at=datetime.now(UTC),
    )
    repo.write(account, df, meta)


@pytest.fixture()
def repos(tmp_path: Path) -> tuple[LadderRepository, CapitalRepository, VarRepository]:
    """Return fresh ladder/capital/var repositories over the same temp data directory."""
    return (
        LadderRepository(data_dir=tmp_path),
        CapitalRepository(data_dir=tmp_path),
        VarRepository(data_dir=tmp_path),
    )


def _service(
    repos: tuple[LadderRepository, CapitalRepository, VarRepository],
) -> VarStatusService:
    ladder_repo, capital_repo, var_repo = repos
    return VarStatusService(
        ladder_repo=ladder_repo,
        accounts_service=AccountsService(ladder_repo=ladder_repo, capital_repo=capital_repo),
        var_repo=var_repo,
    )


class TestStatusBeforeAnyRun:
    """status() for an account with a ladder but no VaR data at all."""

    def test_reports_no_computed_range_and_every_date_missing(
        self, repos: tuple[LadderRepository, CapitalRepository, VarRepository]
    ) -> None:
        """computed_range is null; missing_dates equals the ladder's business-day count."""
        ladder_repo, _, _ = repos
        _write_ladder(ladder_repo, "acct", date(2026, 3, 2), date(2026, 3, 6))
        service = _service(repos)

        status = service.get_status("acct")

        assert status.computed_range is None
        assert status.missing_dates == 5
        assert status.last_run is None
        assert status.instruments == []
        assert status.ladder_range.from_date == date(2026, 3, 2)
        assert status.ladder_range.to_date == date(2026, 3, 6)

    def test_never_reads_the_ladder_xlsx(
        self, repos: tuple[LadderRepository, CapitalRepository, VarRepository]
    ) -> None:
        """status() uses only meta.json -- never LadderRepository.read_full_df()."""
        ladder_repo, _, _ = repos
        _write_ladder(ladder_repo, "acct", date(2026, 3, 2), date(2026, 3, 6))
        service = _service(repos)

        with patch.object(
            LadderRepository, "read_full_df", side_effect=AssertionError("must not be called")
        ):
            service.get_status("acct")


class TestStatusAfterARun:
    """status() after estimates/outcomes/instruments/meta have been committed."""

    def test_reports_computed_range_and_counts(
        self, repos: tuple[LadderRepository, CapitalRepository, VarRepository]
    ) -> None:
        """computed_range, missing_dates and pending_outcomes reflect outcomes.csv."""
        ladder_repo, _, var_repo = repos
        _write_ladder(ladder_repo, "acct", date(2026, 3, 2), date(2026, 3, 6))
        outcomes = pd.DataFrame(
            [
                {
                    "date": date(2026, 3, 2),
                    "outcome_date": date(2026, 3, 3),
                    "outcome_status": "realised",
                    "total_value_gbp": 1000.0,
                    "risky_value_gbp": 1000.0,
                    "hypothetical_pnl_gbp": 0.0,
                    "ladder_pnl_gbp": 0.0,
                    "row_fingerprint": "fp",
                    "run_id": "run-1",
                    "computed_at": datetime(2026, 3, 2, 10, 0, 0),
                },
                {
                    "date": date(2026, 3, 3),
                    "outcome_date": date(2026, 3, 4),
                    "outcome_status": "pending",
                    "total_value_gbp": 1000.0,
                    "risky_value_gbp": 1000.0,
                    "hypothetical_pnl_gbp": None,
                    "ladder_pnl_gbp": None,
                    "row_fingerprint": "fp",
                    "run_id": "run-1",
                    "computed_at": datetime(2026, 3, 2, 10, 0, 0),
                },
            ]
        )
        var_repo.commit(
            "acct",
            estimates=pd.DataFrame(),
            outcomes=outcomes,
            instruments=pd.DataFrame(),
            meta=VarMeta(
                account_name="acct",
                methodology_version="1.0.0",
                config_fingerprint="cfg1",
                last_successful_run_id="run-1",
                updated_at=datetime(2026, 3, 2, 10, 0, 0),
            ),
        )
        var_repo.write_run(
            "acct",
            VarRun(
                run_id="run-1",
                account_name="acct",
                mode="full",
                status="succeeded",
                correlation_id="c1",
                requested_at=datetime(2026, 3, 2, 10, 0, 0),
                dates_stale=3,
                _links={"self": "/x"},
            ),
        )
        service = _service(repos)

        status = service.get_status("acct")

        assert status.computed_range is not None
        assert status.computed_range.from_date == date(2026, 3, 2)
        assert status.computed_range.to_date == date(2026, 3, 3)
        assert status.missing_dates == 3  # 5 ladder business days - 2 computed
        assert status.pending_outcomes == 1
        assert status.stale_dates_last_run == 3
        assert status.last_run is not None
        assert status.last_run.run_id == "run-1"
        assert status.methodology_version == "1.0.0"

    def test_reports_instrument_treatment_from_instruments_csv(
        self, repos: tuple[LadderRepository, CapitalRepository, VarRepository]
    ) -> None:
        """Instruments are reported with their treatment_by_lookback and proxy settings."""
        ladder_repo, _, var_repo = repos
        _write_ladder(ladder_repo, "acct", date(2026, 3, 2), date(2026, 3, 2))
        instruments = pd.DataFrame(
            [
                {
                    "identifier": "EQB",
                    "sub_accounts": "Equity B",
                    "first_observed_date": date(2024, 1, 2),
                    "last_observed_date": date(2026, 3, 2),
                    "proxy": "EQBPROXY",
                    "proxy_mode": "fill_gaps",
                    "proxy_scale": 1.0,
                    "outlier_count": 1,
                    "treatment_1y": "actual",
                    "treatment_5y": "proxied",
                }
            ]
        )
        var_repo.commit(
            "acct",
            estimates=pd.DataFrame(),
            outcomes=pd.DataFrame(),
            instruments=instruments,
            meta=VarMeta(
                account_name="acct",
                methodology_version="1.0.0",
                config_fingerprint="cfg1",
                last_successful_run_id="run-1",
                updated_at=datetime(2026, 3, 2, 10, 0, 0),
            ),
        )
        service = _service(repos)

        status = service.get_status("acct")

        assert len(status.instruments) == 1
        instrument = status.instruments[0]
        assert instrument.identifier == "EQB"
        assert instrument.sub_accounts == ["Equity B"]
        assert instrument.proxy == "EQBPROXY"
        assert instrument.outlier_count == 1
        assert instrument.treatment_by_lookback == {"1y": "actual", "5y": "proxied"}

    def test_warnings_come_from_the_last_successful_run(
        self, repos: tuple[LadderRepository, CapitalRepository, VarRepository]
    ) -> None:
        """Status surfaces the last successful run's warnings."""
        from app.models.var import RunWarning

        ladder_repo, _, var_repo = repos
        _write_ladder(ladder_repo, "acct", date(2026, 3, 2), date(2026, 3, 2))
        var_repo.write_run(
            "acct",
            VarRun(
                run_id="run-1",
                account_name="acct",
                mode="full",
                status="succeeded",
                correlation_id="c1",
                requested_at=datetime(2026, 3, 2, 10, 0, 0),
                warnings=[RunWarning(kind="outlier", identifier="EQA", message="too large")],
                _links={"self": "/x"},
            ),
        )
        service = _service(repos)

        status = service.get_status("acct")

        assert len(status.warnings) == 1
        assert status.warnings[0].kind == "outlier"
