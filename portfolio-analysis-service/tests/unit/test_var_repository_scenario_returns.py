"""Unit tests for VarRepository's scenario-returns snapshot store (015-var-contributions)."""

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.repositories.var_repository import VarRepository
from app.services.var.return_panel import ReturnPanel


def _panel(
    identifiers: tuple[str, ...],
    grid: list[date],
    returns: np.ndarray,
    observed: np.ndarray,
    first_observed: dict[str, date | None] | None = None,
) -> ReturnPanel:
    return ReturnPanel(
        grid=tuple(grid),
        identifiers=identifiers,
        returns=returns,
        observed=observed,
        first_observed=first_observed or dict.fromkeys(identifiers, grid[0] if grid else None),
    )


class TestReadScenarioReturnsEmpty:
    """read_scenario_returns() returns None when nothing has ever been committed."""

    def test_returns_none_when_nothing_committed(self, tmp_path: Path) -> None:
        """No committed snapshot files at all -> None, not an empty panel."""
        repo = VarRepository(data_dir=tmp_path)
        assert repo.read_scenario_returns("acct") is None


class TestCommitScenarioReturnsRoundTrip:
    """commit_scenario_returns() persists a panel that read_scenario_returns() reloads."""

    def test_round_trips_returns_observed_and_first_observed(self, tmp_path: Path) -> None:
        """A committed panel reloads with the same grid, identifiers, returns and observed."""
        repo = VarRepository(data_dir=tmp_path)
        grid = [date(2026, 3, 2), date(2026, 3, 3)]
        panel = _panel(
            ("A", "B"),
            grid,
            np.array([[0.01, np.nan], [-0.02, 0.03]]),
            np.array([[True, False], [True, True]]),
            first_observed={"A": date(2026, 3, 1), "B": date(2026, 3, 3)},
        )

        repo.commit_scenario_returns("acct", panel)
        reloaded = repo.read_scenario_returns("acct")

        assert reloaded is not None
        assert reloaded.grid == tuple(grid)
        assert reloaded.identifiers == ("A", "B")
        np.testing.assert_allclose(reloaded.returns, panel.returns, equal_nan=True)
        np.testing.assert_array_equal(reloaded.observed, panel.observed)
        assert reloaded.first_observed == {"A": date(2026, 3, 1), "B": date(2026, 3, 3)}

    def test_files_are_created_on_disk(self, tmp_path: Path) -> None:
        """The three expected files appear under the account's var/ directory."""
        repo = VarRepository(data_dir=tmp_path)
        panel = _panel(("A",), [date(2026, 3, 2)], np.array([[0.01]]), np.array([[True]]))
        repo.commit_scenario_returns("acct", panel)

        var_dir = tmp_path / "acct" / "var"
        assert (var_dir / "scenario_returns.csv").exists()
        assert (var_dir / "scenario_observed.csv").exists()
        assert (var_dir / "scenario_returns_meta.json").exists()


class TestCommitScenarioReturnsOuterJoin:
    """A second commit outer-joins new dates/identifiers; overlap takes the new value."""

    def test_second_commit_extends_coverage_and_overwrites_overlap(self, tmp_path: Path) -> None:
        """A second, partially-overlapping commit unions dates/identifiers, latest wins."""
        repo = VarRepository(data_dir=tmp_path)

        first = _panel(
            ("A", "B"),
            [date(2026, 3, 2), date(2026, 3, 3)],
            np.array([[0.01, 0.02], [0.03, 0.04]]),
            np.array([[True, True], [True, True]]),
        )
        repo.commit_scenario_returns("acct", first)

        second = _panel(
            ("B", "C"),
            [date(2026, 3, 3), date(2026, 3, 4)],
            np.array([[0.99, 0.05], [0.06, 0.07]]),
            np.array([[True, True], [True, True]]),
            first_observed={"B": date(2026, 3, 3), "C": date(2026, 3, 4)},
        )
        repo.commit_scenario_returns("acct", second)

        reloaded = repo.read_scenario_returns("acct")
        assert reloaded is not None
        assert reloaded.grid == (date(2026, 3, 2), date(2026, 3, 3), date(2026, 3, 4))
        assert reloaded.identifiers == ("A", "B", "C")

        def cell(d: date, ident: str) -> float:
            row = reloaded.grid.index(d)
            col = reloaded.identifiers.index(ident)
            return float(reloaded.returns[row, col])

        # Outside the second commit's rectangle: preserved from the first commit.
        assert cell(date(2026, 3, 2), "A") == pytest.approx(0.01)
        assert cell(date(2026, 3, 2), "B") == pytest.approx(0.02)
        # Inside the second commit's rectangle: overwritten (B on 03-03 was 0.04, now 0.99).
        assert cell(date(2026, 3, 3), "B") == pytest.approx(0.99)
        assert cell(date(2026, 3, 4), "C") == pytest.approx(0.07)
        # "A" was never part of the second commit's identifiers -> unknown on its new date.
        assert np.isnan(cell(date(2026, 3, 4), "A"))

    def test_merge_preserves_existing_first_observed_outside_new_commit(
        self, tmp_path: Path
    ) -> None:
        """An identifier not touched by the second commit keeps its earlier first_observed."""
        repo = VarRepository(data_dir=tmp_path)
        first = _panel(
            ("A",),
            [date(2026, 3, 2)],
            np.array([[0.01]]),
            np.array([[True]]),
            first_observed={"A": date(2026, 1, 1)},
        )
        repo.commit_scenario_returns("acct", first)

        second = _panel(
            ("B",),
            [date(2026, 3, 3)],
            np.array([[0.02]]),
            np.array([[True]]),
            first_observed={"B": date(2026, 3, 3)},
        )
        repo.commit_scenario_returns("acct", second)

        reloaded = repo.read_scenario_returns("acct")
        assert reloaded is not None
        assert reloaded.first_observed["A"] == date(2026, 1, 1)
        assert reloaded.first_observed["B"] == date(2026, 3, 3)


class TestCommitScenarioReturnsAtomicity:
    """A failure partway through a commit leaves every existing file untouched."""

    def test_failure_leaves_prior_files_unchanged(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A write failure partway through leaves every existing file byte-for-byte intact."""
        repo = VarRepository(data_dir=tmp_path)
        first = _panel(("A",), [date(2026, 3, 2)], np.array([[0.01]]), np.array([[True]]))
        repo.commit_scenario_returns("acct", first)

        var_dir = tmp_path / "acct" / "var"
        before_returns = (var_dir / "scenario_returns.csv").read_text(encoding="utf-8")
        before_observed = (var_dir / "scenario_observed.csv").read_text(encoding="utf-8")
        before_meta = (var_dir / "scenario_returns_meta.json").read_text(encoding="utf-8")

        original_to_csv = pd.DataFrame.to_csv
        call_count = {"n": 0}

        def _flaky_to_csv(self: pd.DataFrame, *args: object, **kwargs: object) -> None:
            call_count["n"] += 1
            if call_count["n"] == 2:
                raise OSError("simulated failure")
            return original_to_csv(self, *args, **kwargs)

        monkeypatch.setattr(pd.DataFrame, "to_csv", _flaky_to_csv)

        second = _panel(("B",), [date(2026, 3, 3)], np.array([[0.02]]), np.array([[True]]))
        with pytest.raises(OSError):
            repo.commit_scenario_returns("acct", second)

        assert (var_dir / "scenario_returns.csv").read_text(encoding="utf-8") == before_returns
        assert (var_dir / "scenario_observed.csv").read_text(encoding="utf-8") == before_observed
        assert (var_dir / "scenario_returns_meta.json").read_text(encoding="utf-8") == before_meta
        assert list(var_dir.glob("*.tmp")) == []
