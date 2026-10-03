"""Unit tests for VarRunService: admission control, failure handling, recovery."""

import threading
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from app.config import VarSettings
from app.exceptions import InstrumentNotFoundError, MarketDataServiceError, VarRunInProgressError
from app.models.market_data import IdentifierMappingEntry, ObservedPriceHistory, PriceHistoryPoint
from app.models.var import VarRun, VarRunRequest
from app.repositories.capital_repository import CapitalRepository
from app.repositories.ladder_repository import AccountMeta, LadderRepository
from app.repositories.var_repository import VarRepository
from app.services.accounts_service import AccountsService
from app.services.var.run_scheduler import InlineRunScheduler
from app.services.var.var_run_service import VarRunService, recover_interrupted


class _StubObservedClient:
    """A minimal ObservedPriceClient stub: flat 100.0 for every call, or a configured error."""

    def __init__(self) -> None:
        self.error: Exception | None = None
        self.errors_by_identifier: dict[str, Exception] = {}
        self.calls: list[str] = []

    def get_observed_price_history(
        self, identifier: str, from_date: date, to_date: date, currency: str
    ) -> ObservedPriceHistory:
        self.calls.append(identifier)
        if identifier in self.errors_by_identifier:
            raise self.errors_by_identifier[identifier]
        if self.error is not None:
            raise self.error
        import pandas as pd

        days = pd.bdate_range(start=from_date, end=to_date)
        points = [PriceHistoryPoint(date=d.date(), close=100.0) for d in days]
        return ObservedPriceHistory(
            points=points, first_observed_date=from_date, last_observed_date=to_date
        )


def _write_ladder(repo: LadderRepository, account: str) -> None:
    import pandas as pd

    df = pd.DataFrame(
        [
            {
                "date": date(2026, 3, 2),
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
    meta = AccountMeta(
        account_name=account,
        checksum="x",
        row_count=1,
        from_date=date(2026, 3, 2),
        to_date=date(2026, 3, 2),
        sub_accounts=["Equity A"],
        ingested_at=datetime.now(UTC),
    )
    repo.write(account, df, meta)


class _StubMappingRepo:
    """A minimal IdentifierMappingRepository stub: ticker=sub_account, plus any entries."""

    def __init__(self, entries: list[IdentifierMappingEntry] | None = None) -> None:
        self._entries = entries or []

    def lookup(self, sub_account: str) -> IdentifierMappingEntry | None:
        for entry in self._entries:
            if entry.name == sub_account:
                return entry
        return IdentifierMappingEntry(name=sub_account, ticker=sub_account)

    def entries(self) -> list[IdentifierMappingEntry]:
        return self._entries


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
    observed_client: object,
    scheduler: object,
    mapping_repo: "_StubMappingRepo | None" = None,
) -> VarRunService:
    ladder_repo, capital_repo, var_repo = repos
    return VarRunService(
        ladder_repo=ladder_repo,
        accounts_service=AccountsService(ladder_repo=ladder_repo, capital_repo=capital_repo),
        identifier_mapping_repo=mapping_repo or _StubMappingRepo(),  # type: ignore[arg-type]
        observed_price_client=observed_client,  # type: ignore[arg-type]
        var_repo=var_repo,
        scheduler=scheduler,  # type: ignore[arg-type]
        settings=VarSettings(lookbacks={"win": 1}),
    )


class TestCreateRunAdmission:
    """create_run() rejects a second request while one is active for the account."""

    def test_second_request_while_queued_is_rejected(
        self, repos: tuple[LadderRepository, CapitalRepository, VarRepository]
    ) -> None:
        """A run requested while another is queued/running raises VarRunInProgressError."""
        ladder_repo, _, _ = repos
        _write_ladder(ladder_repo, "acct")

        class _NeverRunsScheduler:
            def submit(self, job: object) -> None:
                pass

            def shutdown(self) -> None:
                pass

        service = _service(repos, _StubObservedClient(), _NeverRunsScheduler())
        service.create_run("acct", VarRunRequest(mode="full"), date(2026, 3, 3), "corr-1")

        with pytest.raises(VarRunInProgressError):
            service.create_run("acct", VarRunRequest(mode="full"), date(2026, 3, 3), "corr-2")

    def test_different_account_is_not_blocked(
        self, repos: tuple[LadderRepository, CapitalRepository, VarRepository]
    ) -> None:
        """An active run for one account never blocks a request for a different account."""
        ladder_repo, _, _ = repos
        _write_ladder(ladder_repo, "acct-a")
        _write_ladder(ladder_repo, "acct-b")

        class _NeverRunsScheduler:
            def submit(self, job: object) -> None:
                pass

            def shutdown(self) -> None:
                pass

        service = _service(repos, _StubObservedClient(), _NeverRunsScheduler())
        service.create_run("acct-a", VarRunRequest(mode="full"), date(2026, 3, 3), "corr-1")
        run_b = service.create_run("acct-b", VarRunRequest(mode="full"), date(2026, 3, 3), "corr-2")
        assert run_b.status == "queued"

    def test_concurrent_requests_produce_exactly_one_winner(
        self, repos: tuple[LadderRepository, CapitalRepository, VarRepository]
    ) -> None:
        """Two near-simultaneous create_run() calls for the same account: one wins, one 409s."""
        ladder_repo, _, _ = repos
        _write_ladder(ladder_repo, "acct")

        class _NeverRunsScheduler:
            def submit(self, job: object) -> None:
                pass

            def shutdown(self) -> None:
                pass

        service = _service(repos, _StubObservedClient(), _NeverRunsScheduler())
        results: list[str] = []
        barrier = threading.Barrier(2)

        def attempt(corr: str) -> None:
            barrier.wait()
            try:
                service.create_run("acct", VarRunRequest(mode="full"), date(2026, 3, 3), corr)
                results.append("ok")
            except VarRunInProgressError:
                results.append("conflict")

        threads = [threading.Thread(target=attempt, args=(f"c{i}",)) for i in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        assert sorted(results) == ["conflict", "ok"]


class TestExecuteFailureHandling:
    """execute() records a specific failure reason and leaves the store untouched."""

    def test_market_data_error_fails_the_run(
        self, repos: tuple[LadderRepository, CapitalRepository, VarRepository]
    ) -> None:
        """A MarketDataServiceError from the observed client fails with market_data_unavailable."""
        ladder_repo, _, var_repo = repos
        _write_ladder(ladder_repo, "acct")
        client = _StubObservedClient()
        client.error = MarketDataServiceError(sub_account="EquityA", detail="boom")
        service = _service(repos, client, InlineRunScheduler())

        run = service.create_run("acct", VarRunRequest(mode="full"), date(2026, 3, 3), "corr-1")

        final = var_repo.read_run("acct", run.run_id)
        assert final is not None
        assert final.status == "failed"
        assert final.failure is not None
        assert final.failure.reason == "market_data_unavailable"
        assert final.failure.correlation_id == "corr-1"
        assert final.failure.run_id == run.run_id
        assert len(var_repo.read_estimates("acct")) == 0

    def test_internal_error_is_caught_and_recorded(
        self, repos: tuple[LadderRepository, CapitalRepository, VarRepository]
    ) -> None:
        """An unexpected exception fails the run with reason internal_error, never crashes."""
        ladder_repo, _, var_repo = repos
        _write_ladder(ladder_repo, "acct")
        client = _StubObservedClient()
        client.error = RuntimeError("unexpected")
        service = _service(repos, client, InlineRunScheduler())

        run = service.create_run("acct", VarRunRequest(mode="full"), date(2026, 3, 3), "corr-1")

        final = var_repo.read_run("acct", run.run_id)
        assert final is not None
        assert final.status == "failed"
        assert final.failure is not None
        assert final.failure.reason == "internal_error"

    def test_run_never_left_running_after_failure(
        self, repos: tuple[LadderRepository, CapitalRepository, VarRepository]
    ) -> None:
        """A failed run's final status is never 'running'."""
        ladder_repo, _, var_repo = repos
        _write_ladder(ladder_repo, "acct")
        client = _StubObservedClient()
        client.error = InstrumentNotFoundError(identifier="EquityA")
        service = _service(repos, client, InlineRunScheduler())

        run = service.create_run("acct", VarRunRequest(mode="full"), date(2026, 3, 3), "corr-1")

        final = var_repo.read_run("acct", run.run_id)
        assert final is not None
        assert final.status != "running"


class TestRangeClipping:
    """A requested range is clipped to the ladder range; an empty intersection succeeds."""

    def test_range_entirely_before_ladder_succeeds_with_zero_dates(
        self, repos: tuple[LadderRepository, CapitalRepository, VarRepository]
    ) -> None:
        """A range before the ladder's first date computes 0 dates, not an error."""
        ladder_repo, _, var_repo = repos
        _write_ladder(ladder_repo, "acct")  # ladder is a single date: 2026-03-02
        service = _service(repos, _StubObservedClient(), InlineRunScheduler())

        request = VarRunRequest(mode="full", start=date(2020, 1, 1), end=date(2020, 1, 2))
        run = service.create_run("acct", request, date(2026, 3, 3), "corr-1")

        final = var_repo.read_run("acct", run.run_id)
        assert final is not None
        assert final.status == "succeeded"
        assert final.dates_computed == 0


class TestRecoverInterrupted:
    """recover_interrupted() rewrites every queued/running record to failed/interrupted."""

    def test_running_record_is_marked_failed_interrupted(self, tmp_path: Path) -> None:
        """A 'running' run record becomes 'failed' with reason 'interrupted'."""
        var_repo = VarRepository(data_dir=tmp_path)
        run = VarRun(
            run_id="r1",
            account_name="acct",
            mode="full",
            status="running",
            correlation_id="c1",
            requested_at=datetime.now(UTC),
            started_at=datetime.now(UTC),
            _links={"self": "/x"},
        )
        var_repo.write_run("acct", run)

        recover_interrupted(var_repo)

        recovered = var_repo.read_run("acct", "r1")
        assert recovered is not None
        assert recovered.status == "failed"
        assert recovered.failure is not None
        assert recovered.failure.reason == "interrupted"
        assert recovered.finished_at is not None

    def test_queued_record_is_also_recovered(self, tmp_path: Path) -> None:
        """A 'queued' run record (never even started) is also marked failed/interrupted."""
        var_repo = VarRepository(data_dir=tmp_path)
        run = VarRun(
            run_id="r1",
            account_name="acct",
            mode="full",
            status="queued",
            correlation_id="c1",
            requested_at=datetime.now(UTC),
            _links={"self": "/x"},
        )
        var_repo.write_run("acct", run)

        recover_interrupted(var_repo)

        recovered = var_repo.read_run("acct", "r1")
        assert recovered is not None
        assert recovered.status == "failed"

    def test_succeeded_and_failed_records_are_untouched(self, tmp_path: Path) -> None:
        """Finished runs (succeeded or already failed) are left exactly as they were."""
        var_repo = VarRepository(data_dir=tmp_path)
        succeeded = VarRun(
            run_id="r1",
            account_name="acct",
            mode="full",
            status="succeeded",
            correlation_id="c1",
            requested_at=datetime.now(UTC),
            _links={"self": "/x"},
        )
        var_repo.write_run("acct", succeeded)

        recover_interrupted(var_repo)

        recovered = var_repo.read_run("acct", "r1")
        assert recovered is not None
        assert recovered.status == "succeeded"

    def test_recovers_across_multiple_accounts(self, tmp_path: Path) -> None:
        """Interrupted runs are recovered for every account with a runs/ directory."""
        var_repo = VarRepository(data_dir=tmp_path)
        for account in ("acct-a", "acct-b"):
            var_repo.write_run(
                account,
                VarRun(
                    run_id="r1",
                    account_name=account,
                    mode="full",
                    status="running",
                    correlation_id="c1",
                    requested_at=datetime.now(UTC),
                    _links={"self": "/x"},
                ),
            )

        recover_interrupted(var_repo)

        for account in ("acct-a", "acct-b"):
            recovered = var_repo.read_run(account, "r1")
            assert recovered is not None
            assert recovered.status == "failed"


class TestInstrumentWarnings:
    """A 404 for a held instrument or its proxy degrades gracefully, with a warning."""

    def test_held_instrument_not_found_is_rescaled_with_warning(
        self, repos: tuple[LadderRepository, CapitalRepository, VarRepository]
    ) -> None:
        """A 404 for the only held instrument warns instrument_not_found and still succeeds."""
        ladder_repo, _, var_repo = repos
        _write_ladder(ladder_repo, "acct")
        client = _StubObservedClient()
        client.errors_by_identifier["Equity A"] = InstrumentNotFoundError(identifier="Equity A")
        service = _service(repos, client, InlineRunScheduler())

        run = service.create_run("acct", VarRunRequest(mode="full"), date(2026, 3, 3), "corr-1")

        final = var_repo.read_run("acct", run.run_id)
        assert final is not None
        assert final.status == "succeeded"
        assert any(
            w.kind == "instrument_not_found" and w.identifier == "Equity A" for w in final.warnings
        )
        # The account's only position has zero usable data, so its one scenario day is
        # excluded by the observed-share rule (0% coverage) rather than rescaled -- with
        # no OTHER position to rescale from, that is the honest outcome: insufficient,
        # not a silently-fabricated 100%-rescaled estimate.
        estimates = var_repo.read_estimates("acct")
        assert estimates.iloc[0]["quality"] == "insufficient"
        assert estimates.iloc[0]["scenario_count"] == 0

    def test_proxy_not_found_is_reported_as_proxy_unresolved(
        self, repos: tuple[LadderRepository, CapitalRepository, VarRepository]
    ) -> None:
        """A 404 for a configured proxy (not itself held) warns proxy_unresolved."""
        ladder_repo, _, var_repo = repos
        _write_ladder(ladder_repo, "acct")
        client = _StubObservedClient()
        client.errors_by_identifier["Missing Proxy"] = InstrumentNotFoundError(
            identifier="Missing Proxy"
        )
        mapping = _StubMappingRepo(
            entries=[
                IdentifierMappingEntry(
                    name="Equity A", ticker="Equity A", var_proxy="Missing Proxy"
                )
            ]
        )
        service = _service(repos, client, InlineRunScheduler(), mapping_repo=mapping)

        run = service.create_run("acct", VarRunRequest(mode="full"), date(2026, 3, 3), "corr-1")

        final = var_repo.read_run("acct", run.run_id)
        assert final is not None
        assert final.status == "succeeded"
        assert any(
            w.kind == "proxy_unresolved" and w.identifier == "Missing Proxy" for w in final.warnings
        )
