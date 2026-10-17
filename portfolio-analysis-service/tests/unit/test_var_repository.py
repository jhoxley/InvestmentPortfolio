"""Unit tests for VarRepository: estimates/outcomes/instruments CSV, meta, and runs."""

from datetime import date, datetime
from pathlib import Path

import pandas as pd
import pytest

from app.models.var import RunFailure, VarRun
from app.repositories.var_repository import VarMeta, VarRepository


@pytest.fixture()
def repo(tmp_path: Path) -> VarRepository:
    """Return a VarRepository over a fresh temporary data directory."""
    return VarRepository(data_dir=tmp_path)


def _make_run(
    run_id: str = "run-1", account_name: str = "acct", requested_at: datetime | None = None
) -> VarRun:
    return VarRun(
        run_id=run_id,
        account_name=account_name,
        mode="full",
        status="queued",
        correlation_id="corr-1",
        requested_at=requested_at or datetime(2026, 3, 1, 12, 0, 0),
        _links={"self": f"/v1/accounts/{account_name}/risk/var/runs/{run_id}"},
    )


class TestRunRoundTrip:
    """write_run/read_run/list_runs round-trip VarRun JSON under data/{a}/var/runs/."""

    def test_write_then_read_run(self, repo: VarRepository) -> None:
        """A written run reads back with the same fields."""
        run = _make_run()
        repo.write_run("acct", run)

        loaded = repo.read_run("acct", "run-1")

        assert loaded is not None
        assert loaded.run_id == "run-1"
        assert loaded.status == "queued"
        assert loaded.correlation_id == "corr-1"

    def test_read_run_returns_none_when_missing(self, repo: VarRepository) -> None:
        """Reading an unknown run returns None rather than raising."""
        assert repo.read_run("acct", "missing-run") is None

    def test_list_runs_newest_first(self, repo: VarRepository) -> None:
        """list_runs() orders by requested_at, newest first."""
        repo.write_run("acct", _make_run("run-1", requested_at=datetime(2026, 3, 1)))
        repo.write_run("acct", _make_run("run-2", requested_at=datetime(2026, 3, 3)))
        repo.write_run("acct", _make_run("run-3", requested_at=datetime(2026, 3, 2)))

        runs = repo.list_runs("acct")

        assert [r.run_id for r in runs] == ["run-2", "run-3", "run-1"]

    def test_list_runs_empty_for_unknown_account(self, repo: VarRepository) -> None:
        """list_runs() returns an empty list, not an error, for an account with no runs."""
        assert repo.list_runs("nobody") == []

    def test_write_run_round_trips_failure(self, repo: VarRepository) -> None:
        """A failed run's RunFailure (including reason/run_id/correlation_id) round-trips."""
        run = _make_run().model_copy(
            update={
                "status": "failed",
                "failure": RunFailure(
                    type="https://portfolio-analysis/errors/market-data-service-unavailable",
                    title="Market Data Service Unavailable",
                    detail="boom",
                    reason="market_data_unavailable",
                    run_id="run-1",
                    correlation_id="corr-1",
                ),
            }
        )
        repo.write_run("acct", run)

        loaded = repo.read_run("acct", "run-1")

        assert loaded is not None
        assert loaded.failure is not None
        assert loaded.failure.reason == "market_data_unavailable"

    def test_list_accounts_with_runs(self, repo: VarRepository) -> None:
        """list_accounts_with_runs() enumerates every account with a runs/ directory."""
        repo.write_run("acct-a", _make_run("run-1", account_name="acct-a"))
        repo.write_run("acct-b", _make_run("run-1", account_name="acct-b"))

        assert set(repo.list_accounts_with_runs()) == {"acct-a", "acct-b"}


class TestEmptyStoreReads:
    """Reads against a never-written account return empty, well-shaped DataFrames."""

    def test_read_estimates_empty(self, repo: VarRepository) -> None:
        """read_estimates() with no store returns an empty DataFrame with the right columns."""
        df = repo.read_estimates("acct")
        assert len(df) == 0
        assert "date" in df.columns
        assert "lookback_days" in df.columns
        assert "quality" in df.columns

    def test_read_outcomes_empty(self, repo: VarRepository) -> None:
        """read_outcomes() with no store returns an empty DataFrame with the right columns."""
        df = repo.read_outcomes("acct")
        assert len(df) == 0
        assert "date" in df.columns
        assert "outcome_status" in df.columns

    def test_read_instruments_empty(self, repo: VarRepository) -> None:
        """read_instruments() with no store returns an empty DataFrame with the right columns."""
        df = repo.read_instruments("acct")
        assert len(df) == 0
        assert "identifier" in df.columns

    def test_read_meta_none_before_first_commit(self, repo: VarRepository) -> None:
        """read_meta() returns None before anything has ever been committed."""
        assert repo.read_meta("acct") is None


class TestCommit:
    """commit() upserts estimates/outcomes/instruments and writes meta atomically."""

    def _estimate_row(self, d: date, lookback_days: int, **overrides: object) -> dict[str, object]:
        row: dict[str, object] = {
            "date": d,
            "method": "historical-simulation",
            "lookback_code": "2y",
            "lookback_days": lookback_days,
            "scenario_count": 500,
            "excluded_scenarios": 20,
            "actual_mv_pct": 100.0,
            "proxied_mv_pct": 0.0,
            "rescaled_mv_pct": 0.0,
            "quality": "ok",
            "quality_reason": "",
            "var_9500_gbp": 1000.0,
            "var_9750_gbp": 1200.0,
            "var_9900_gbp": 1500.0,
            "es_9500_gbp": 1100.0,
            "es_9750_gbp": 1300.0,
            "es_9900_gbp": 1600.0,
            "row_fingerprint": "fp1",
            "methodology_version": "1.0.0",
            "run_id": "run-1",
            "computed_at": datetime(2026, 3, 2, 10, 0, 0),
        }
        row.update(overrides)
        return row

    def _outcome_row(self, d: date, **overrides: object) -> dict[str, object]:
        row: dict[str, object] = {
            "date": d,
            "outcome_date": date(2026, 3, 3),
            "outcome_status": "realised",
            "total_value_gbp": 100000.0,
            "risky_value_gbp": 90000.0,
            "hypothetical_pnl_gbp": -500.0,
            "ladder_pnl_gbp": -480.0,
            "row_fingerprint": "fp1",
            "run_id": "run-1",
            "computed_at": datetime(2026, 3, 2, 10, 0, 0),
        }
        row.update(overrides)
        return row

    def test_commit_then_read_estimates(self, repo: VarRepository) -> None:
        """A committed estimate row reads back with its values intact."""
        estimates = pd.DataFrame([self._estimate_row(date(2026, 3, 2), 520)])
        repo.commit(
            "acct",
            estimates=estimates,
            outcomes=pd.DataFrame([self._outcome_row(date(2026, 3, 2))]),
            instruments=pd.DataFrame(),
            meta=VarMeta(
                account_name="acct",
                methodology_version="1.0.0",
                config_fingerprint="cfg1",
                last_successful_run_id="run-1",
                updated_at=datetime(2026, 3, 2, 10, 0, 0),
            ),
        )

        df = repo.read_estimates("acct")
        assert len(df) == 1
        assert df.iloc[0]["var_9900_gbp"] == pytest.approx(1500.0)

    def test_commit_upserts_only_affected_dates(self, repo: VarRepository) -> None:
        """Recommitting one date leaves other previously stored dates untouched."""
        day1, day2 = date(2026, 3, 2), date(2026, 3, 3)
        repo.commit(
            "acct",
            estimates=pd.DataFrame([self._estimate_row(day1, 520), self._estimate_row(day2, 520)]),
            outcomes=pd.DataFrame([self._outcome_row(day1), self._outcome_row(day2)]),
            instruments=pd.DataFrame(),
            meta=VarMeta(
                account_name="acct",
                methodology_version="1.0.0",
                config_fingerprint="cfg1",
                last_successful_run_id="run-1",
                updated_at=datetime(2026, 3, 2),
            ),
        )

        repo.commit(
            "acct",
            estimates=pd.DataFrame([self._estimate_row(day1, 520, var_9900_gbp=9999.0)]),
            outcomes=pd.DataFrame([self._outcome_row(day1, hypothetical_pnl_gbp=-1.0)]),
            instruments=pd.DataFrame(),
            meta=VarMeta(
                account_name="acct",
                methodology_version="1.0.0",
                config_fingerprint="cfg1",
                last_successful_run_id="run-2",
                updated_at=datetime(2026, 3, 3),
            ),
        )

        df = repo.read_estimates("acct").set_index("date")
        assert df.loc[pd.Timestamp(day1), "var_9900_gbp"] == pytest.approx(9999.0)
        assert df.loc[pd.Timestamp(day2), "var_9900_gbp"] == pytest.approx(1500.0)

    def test_commit_sorted_by_date_and_lookback(self, repo: VarRepository) -> None:
        """Stored estimate rows end up sorted by (date, lookback_days)."""
        day1, day2 = date(2026, 3, 2), date(2026, 3, 3)
        estimates = pd.DataFrame(
            [
                self._estimate_row(day2, 1300),
                self._estimate_row(day1, 1300),
                self._estimate_row(day2, 260),
                self._estimate_row(day1, 260),
            ]
        )
        repo.commit(
            "acct",
            estimates=estimates,
            outcomes=pd.DataFrame([self._outcome_row(day1), self._outcome_row(day2)]),
            instruments=pd.DataFrame(),
            meta=VarMeta(
                account_name="acct",
                methodology_version="1.0.0",
                config_fingerprint="cfg1",
                last_successful_run_id="run-1",
                updated_at=datetime(2026, 3, 3),
            ),
        )

        df = repo.read_estimates("acct")
        pairs = list(zip(df["date"], df["lookback_days"], strict=True))
        assert pairs == sorted(pairs)

    def test_commit_failure_leaves_store_untouched(
        self, repo: VarRepository, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If any write in the commit fails, no existing file changes and no temp files remain."""
        day1 = date(2026, 3, 2)
        repo.commit(
            "acct",
            estimates=pd.DataFrame([self._estimate_row(day1, 520)]),
            outcomes=pd.DataFrame([self._outcome_row(day1)]),
            instruments=pd.DataFrame(),
            meta=VarMeta(
                account_name="acct",
                methodology_version="1.0.0",
                config_fingerprint="cfg1",
                last_successful_run_id="run-1",
                updated_at=datetime(2026, 3, 2),
            ),
        )
        before_estimates = repo.read_estimates("acct").copy()

        call_count = {"n": 0}
        original_to_csv = pd.DataFrame.to_csv

        def failing_to_csv(self: pd.DataFrame, *args: object, **kwargs: object) -> object:
            call_count["n"] += 1
            if call_count["n"] == 3:
                raise OSError("simulated disk failure")
            return original_to_csv(self, *args, **kwargs)

        monkeypatch.setattr(pd.DataFrame, "to_csv", failing_to_csv)

        with pytest.raises(OSError):
            repo.commit(
                "acct",
                estimates=pd.DataFrame([self._estimate_row(day1, 520, var_9900_gbp=4242.0)]),
                outcomes=pd.DataFrame([self._outcome_row(day1)]),
                instruments=pd.DataFrame(),
                meta=VarMeta(
                    account_name="acct",
                    methodology_version="1.0.0",
                    config_fingerprint="cfg1",
                    last_successful_run_id="run-2",
                    updated_at=datetime(2026, 3, 3),
                ),
            )

        monkeypatch.undo()
        after_estimates = repo.read_estimates("acct")
        pd.testing.assert_frame_equal(
            before_estimates.reset_index(drop=True), after_estimates.reset_index(drop=True)
        )
        var_dir = repo._var_dir("acct")
        assert list(var_dir.glob("*.tmp")) == []

    def test_read_meta_after_commit(self, repo: VarRepository) -> None:
        """read_meta() reflects the most recently committed VarMeta."""
        repo.commit(
            "acct",
            estimates=pd.DataFrame(),
            outcomes=pd.DataFrame(),
            instruments=pd.DataFrame(),
            meta=VarMeta(
                account_name="acct",
                methodology_version="1.0.0",
                config_fingerprint="cfg1",
                last_successful_run_id="run-1",
                updated_at=datetime(2026, 3, 2, 10, 0, 0),
            ),
        )

        meta = repo.read_meta("acct")

        assert meta is not None
        assert meta.config_fingerprint == "cfg1"
        assert meta.last_successful_run_id == "run-1"
