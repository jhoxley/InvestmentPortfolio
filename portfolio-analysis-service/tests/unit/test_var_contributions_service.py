"""Direct (non-HTTP) unit tests for VarContributionsService (015-var-contributions).

Builds real ladder/VaR-run state through VarRunService (so the estimates store and the
persisted scenario-returns snapshot are both genuine, not hand-stubbed), then calls
VarContributionsService.get_contributions() directly -- faster and more isolated than a
full BDD round trip through the HTTP API.
"""

from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import pytest

from app.config import VarSettings
from app.models.market_data import ObservedPriceHistory, PriceHistoryPoint
from app.models.var import VarRunRequest
from app.repositories.capital_repository import CapitalRepository
from app.repositories.ladder_repository import AccountMeta, LadderRepository
from app.repositories.var_repository import VarRepository
from app.services.accounts_service import AccountsService
from app.services.var.run_scheduler import InlineRunScheduler
from app.services.var.var_contributions_service import VarContributionsService
from app.services.var.var_run_service import VarRunService
from tests.conftest import FakeIdentifierMappingRepository


class _ConfigurableObservedClient:
    """An ObservedPriceClient stub returning a per-identifier configured price series."""

    def __init__(self) -> None:
        self._series: dict[str, list[PriceHistoryPoint]] = {}

    def configure(self, identifier: str, points: list[PriceHistoryPoint]) -> None:
        """Set the full known observation history for one identifier."""
        self._series[identifier] = sorted(points, key=lambda p: p.date)

    def get_observed_price_history(
        self, identifier: str, from_date: date, to_date: date, currency: str
    ) -> ObservedPriceHistory:
        """Return the configured points within [from_date, to_date], or a flat default."""
        del currency
        if identifier in self._series:
            full = self._series[identifier]
            windowed = [p for p in full if from_date <= p.date <= to_date]
            first = full[0].date if full else None
            last = full[-1].date if full else None
            return ObservedPriceHistory(
                points=windowed, first_observed_date=first, last_observed_date=last
            )
        days = pd.bdate_range(start=from_date, end=to_date)
        points = [PriceHistoryPoint(date=d.date(), close=100.0) for d in days]
        return ObservedPriceHistory(
            points=points, first_observed_date=from_date, last_observed_date=to_date
        )


def _write_ladder(
    repo: LadderRepository, account: str, as_of: date, positions: dict[str, float], cash: float
) -> None:
    """Write a stored position ladder with real quantity/market_value for one date."""
    rows = [
        {
            "date": as_of,
            "sub_account": sub,
            "book_cost": 0.0,
            "quantity": 1.0,
            "total_income": 0.0,
            "price": value,
            "market_value": value,
            "portfolio_weight": 0.0,
            "position_return": 0.0,
            "weighted_position_return": 0.0,
        }
        for sub, value in positions.items()
    ]
    if cash:
        rows.append(
            {
                "date": as_of,
                "sub_account": "Cash",
                "book_cost": 0.0,
                "quantity": cash,
                "total_income": 0.0,
                "price": 1.0,
                "market_value": cash,
                "portfolio_weight": 0.0,
                "position_return": 0.0,
                "weighted_position_return": 0.0,
            }
        )
    df = pd.DataFrame(rows)
    meta = AccountMeta(
        account_name=account,
        checksum="x",
        row_count=len(df),
        from_date=as_of,
        to_date=as_of,
        sub_accounts=sorted(df["sub_account"].unique().tolist()),
        ingested_at=datetime.now(UTC),
    )
    repo.write(account, df, meta)


def _series(start: date, prices: list[float]) -> list[PriceHistoryPoint]:
    """Build a consecutive-business-day price series starting at `start`."""
    days = pd.bdate_range(start=start, periods=len(prices))
    return [PriceHistoryPoint(date=d.date(), close=p) for d, p in zip(days, prices, strict=True)]


@pytest.fixture()
def repos(tmp_path: Path) -> tuple[LadderRepository, CapitalRepository, VarRepository]:
    """Fresh ladder/capital/var repositories over the same temp data directory."""
    return (
        LadderRepository(data_dir=tmp_path),
        CapitalRepository(data_dir=tmp_path),
        VarRepository(data_dir=tmp_path),
    )


def _run_service(
    repos: tuple[LadderRepository, CapitalRepository, VarRepository],
    observed_client: _ConfigurableObservedClient,
    mapping_repo: FakeIdentifierMappingRepository,
    settings: VarSettings,
) -> VarRunService:
    ladder_repo, capital_repo, var_repo = repos
    return VarRunService(
        ladder_repo=ladder_repo,
        accounts_service=AccountsService(ladder_repo=ladder_repo, capital_repo=capital_repo),
        identifier_mapping_repo=mapping_repo,  # type: ignore[arg-type]
        observed_price_client=observed_client,
        var_repo=var_repo,
        scheduler=InlineRunScheduler(),
        settings=settings,
    )


def _contributions_service(
    repos: tuple[LadderRepository, CapitalRepository, VarRepository],
    mapping_repo: FakeIdentifierMappingRepository,
    settings: VarSettings,
) -> VarContributionsService:
    ladder_repo, capital_repo, var_repo = repos
    return VarContributionsService(
        ladder_repo=ladder_repo,
        accounts_service=AccountsService(ladder_repo=ladder_repo, capital_repo=capital_repo),
        var_repo=var_repo,
        identifier_mapping_repo=mapping_repo,  # type: ignore[arg-type]
        settings=settings,
    )


class TestComputedContributionsGroupedByPosition:
    """The computed path returns one group per position, plus Cash, summing to total ES."""

    def test_component_es_sums_to_stored_total_es_and_cash_is_zero(
        self, repos: tuple[LadderRepository, CapitalRepository, VarRepository]
    ) -> None:
        """Component ES across position groups (incl. Cash) sums to the stored total ES."""
        ladder_repo, _, var_repo = repos
        as_of = date(2026, 3, 6)
        _write_ladder(
            ladder_repo, "acct", as_of, {"Equity A": 60000.0, "Equity B": 30000.0}, cash=10000.0
        )

        mapping = FakeIdentifierMappingRepository()
        mapping.set_entry("Equity A", ticker="Equity A")
        mapping.set_entry("Equity B", ticker="Equity B")

        client = _ConfigurableObservedClient()
        start = pd.bdate_range(end=as_of, periods=6)[0].date()
        client.configure("Equity A", _series(start, [100, 99, 101, 98, 102, 97]))
        client.configure("Equity B", _series(start, [50, 51, 49, 52, 48, 53]))

        settings = VarSettings(lookbacks={"win": 5}, headline_lookback="win")
        run_service = _run_service(repos, client, mapping, settings)
        run_service.create_run("acct", VarRunRequest(mode="full"), as_of, "corr-1")

        estimates = var_repo.read_estimates("acct")
        row = estimates[(estimates["date"] == pd.Timestamp(as_of))]
        assert len(row) == 1, estimates.to_string()
        total_es = float(row.iloc[0]["es_9500_gbp"])

        contributions_service = _contributions_service(repos, mapping, settings)
        response = contributions_service.get_contributions(
            "acct", as_of, "win", 5, 9500, "position"
        )

        assert response.date == as_of
        keys = {g.key for g in response.groups}
        assert keys == {"Equity A", "Equity B", "Cash"}

        cash = next(g for g in response.groups if g.key == "Cash")
        assert cash.standalone_var_gbp == pytest.approx(0.0)
        assert cash.incremental_var_gbp == pytest.approx(0.0)
        assert cash.component_es_gbp == pytest.approx(0.0)
        assert cash.marginal_var_gbp_per_gbp == pytest.approx(0.0)
        assert cash.actual_mv_pct == pytest.approx(100.0)

        total_component_es = sum(g.component_es_gbp for g in response.groups)
        assert total_component_es == pytest.approx(total_es, abs=1e-6)

        total_weight = sum(g.weight_pct for g in response.groups)
        assert total_weight == pytest.approx(100.0, abs=1e-6)


class TestComputedContributionsGroupedByTheme:
    """Grouping by theme aggregates positions sharing a theme into one entry."""

    def test_two_positions_sharing_a_theme_aggregate_into_one_group(
        self, repos: tuple[LadderRepository, CapitalRepository, VarRepository]
    ) -> None:
        """Equity A and Equity B, both themed 'Global', produce one 'Global' group."""
        ladder_repo, _, var_repo = repos
        as_of = date(2026, 3, 6)
        _write_ladder(
            ladder_repo, "acct", as_of, {"Equity A": 60000.0, "Equity B": 30000.0}, cash=10000.0
        )

        mapping = FakeIdentifierMappingRepository()
        mapping.set_entry("Equity A", ticker="Equity A", theme="Global")
        mapping.set_entry("Equity B", ticker="Equity B", theme="Global")

        client = _ConfigurableObservedClient()
        start = pd.bdate_range(end=as_of, periods=6)[0].date()
        client.configure("Equity A", _series(start, [100, 99, 101, 98, 102, 97]))
        client.configure("Equity B", _series(start, [50, 51, 49, 52, 48, 53]))

        settings = VarSettings(lookbacks={"win": 5}, headline_lookback="win")
        run_service = _run_service(repos, client, mapping, settings)
        run_service.create_run("acct", VarRunRequest(mode="full"), as_of, "corr-1")

        contributions_service = _contributions_service(repos, mapping, settings)
        response = contributions_service.get_contributions("acct", as_of, "win", 5, 9500, "theme")

        keys = {g.key for g in response.groups}
        assert keys == {"Global", "Cash"}
        global_group = next(g for g in response.groups if g.key == "Global")
        assert global_group.market_value_gbp == pytest.approx(90000.0)
        assert global_group.identifier is None

        estimates = var_repo.read_estimates("acct")
        row = estimates[estimates["date"] == pd.Timestamp(as_of)].iloc[0]
        total_es = float(row["es_9500_gbp"])
        total_component_es = sum(g.component_es_gbp for g in response.groups)
        assert total_component_es == pytest.approx(total_es, abs=1e-6)


class TestComputedContributionsProvenanceQuality:
    """A group's coverage percentages are market-value-weighted across its member positions.

    This mirrors the existing account-wide convention (`estimate()`'s own
    actual/proxied/rescaled_mv_pct): a single position's own worst-treatment is binary
    (0% or 100%), so a genuinely mixed percentage only appears for a group spanning
    several positions with different treatments -- exactly the `group_by=theme` case.
    """

    def test_theme_group_mixes_an_actual_and_a_fully_proxied_position(
        self, repos: tuple[LadderRepository, CapitalRepository, VarRepository]
    ) -> None:
        """A theme combining one actual and one always-proxied position splits by value."""
        ladder_repo, _, var_repo = repos
        as_of = date(2026, 3, 9)
        _write_ladder(
            ladder_repo, "acct", as_of, {"Equity A": 70000.0, "Equity B": 30000.0}, cash=0.0
        )

        mapping = FakeIdentifierMappingRepository()
        mapping.set_entry("Equity A", ticker="Equity A", theme="Global")
        mapping.set_entry(
            "Equity B",
            ticker="Equity B",
            var_proxy="Proxy P",
            var_proxy_mode="always",
            theme="Global",
        )

        client = _ConfigurableObservedClient()
        start = pd.bdate_range(end=as_of, periods=4)[0].date()
        client.configure("Equity A", _series(start, [100, 99, 101, 98]))
        client.configure("Equity B", _series(start, [50, 51, 49, 52]))
        client.configure("Proxy P", _series(start, [20, 21, 19, 22]))

        settings = VarSettings(
            lookbacks={"win": 3}, headline_lookback="win", min_observed_share_per_scenario=0.0
        )
        run_service = _run_service(repos, client, mapping, settings)
        run_service.create_run("acct", VarRunRequest(mode="full"), as_of, "corr-1")

        assert not var_repo.read_estimates("acct").empty

        contributions_service = _contributions_service(repos, mapping, settings)
        response = contributions_service.get_contributions("acct", as_of, "win", 3, 9500, "theme")

        global_group = next(g for g in response.groups if g.key == "Global")
        # Equity A (70000, actual) + Equity B (30000, always-proxied) -> 30% proxied by value.
        assert global_group.proxied_mv_pct == pytest.approx(30.0, abs=1e-6)
        assert global_group.actual_mv_pct == pytest.approx(70.0, abs=1e-6)


class TestNotComputedAndInsufficientBranches:
    """get_contributions() never calls build_scenario_matrix for these two gating cases."""

    def test_no_estimate_at_all_returns_not_computed_shape(
        self, repos: tuple[LadderRepository, CapitalRepository, VarRepository]
    ) -> None:
        """An account with a ladder but no VaR run at all returns the empty shape."""
        ladder_repo, _, _ = repos
        _write_ladder(ladder_repo, "acct", date(2026, 3, 6), {"Equity A": 1000.0}, cash=0.0)
        mapping = FakeIdentifierMappingRepository()
        settings = VarSettings()
        service = _contributions_service(repos, mapping, settings)

        response = service.get_contributions("acct", date(2026, 3, 6), "2y", 520, 9500, "position")

        assert response.date is None
        assert response.groups == []
        assert response.quality is None
        assert "status" in response.links
        assert "runs" in response.links

    def test_insufficient_quality_returns_empty_groups_without_building_matrix(
        self,
        repos: tuple[LadderRepository, CapitalRepository, VarRepository],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An insufficient-quality stored row short-circuits before any matrix build."""
        ladder_repo, _, var_repo = repos
        as_of = date(2026, 3, 6)
        _write_ladder(ladder_repo, "acct", as_of, {"Equity A": 1000.0}, cash=0.0)

        estimates = pd.DataFrame(
            [
                {
                    "date": pd.Timestamp(as_of),
                    "method": "historical-simulation",
                    "lookback_code": "win",
                    "lookback_days": 5,
                    "scenario_count": 1,
                    "excluded_scenarios": 4,
                    "actual_mv_pct": 100.0,
                    "proxied_mv_pct": 0.0,
                    "rescaled_mv_pct": 0.0,
                    "quality": "insufficient",
                    "quality_reason": "scenario_count 1 < 4",
                    "var_9500_gbp": None,
                    "es_9500_gbp": None,
                    "row_fingerprint": "fp",
                    "methodology_version": "1.0.0",
                    "run_id": "run-1",
                    "computed_at": datetime.now(UTC),
                }
            ]
        )
        outcomes = pd.DataFrame(
            [
                {
                    "date": pd.Timestamp(as_of),
                    "outcome_date": pd.Timestamp(as_of),
                    "outcome_status": "pending",
                    "total_value_gbp": 1000.0,
                    "risky_value_gbp": 1000.0,
                    "hypothetical_pnl_gbp": None,
                    "ladder_pnl_gbp": None,
                    "row_fingerprint": "fp",
                    "run_id": "run-1",
                    "computed_at": datetime.now(UTC),
                }
            ]
        )
        from app.repositories.var_repository import VarMeta

        var_repo.commit(
            "acct",
            estimates=estimates,
            outcomes=outcomes,
            instruments=pd.DataFrame(),
            meta=VarMeta(
                account_name="acct",
                methodology_version="1.0.0",
                config_fingerprint="fp",
                last_successful_run_id="run-1",
                updated_at=datetime.now(UTC),
            ),
        )

        from app.services.var import var_contributions_service as service_module

        def _unexpected_build(*args: object, **kwargs: object) -> None:
            raise AssertionError("build_scenario_matrix must not be called for insufficient rows")

        monkeypatch.setattr(service_module, "build_scenario_matrix", _unexpected_build)

        mapping = FakeIdentifierMappingRepository()
        settings = VarSettings(lookbacks={"win": 5}, headline_lookback="win")
        service = _contributions_service(repos, mapping, settings)

        response = service.get_contributions("acct", as_of, "win", 5, 9500, "position")

        assert response.quality == "insufficient"
        assert response.groups == []
        assert response.total_value_gbp == pytest.approx(1000.0)
