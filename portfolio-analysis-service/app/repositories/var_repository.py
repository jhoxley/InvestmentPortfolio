"""Filesystem repository for the VaR calculation store (estimates, outcomes, runs, meta).

Mirrors LadderRepository's layout and atomicity conventions: each account occupies
data_dir/{account}/var/, and every write goes to a temporary file first, then an
os.replace() swap -- so a failure partway through a commit never leaves a half-written
file in place (FR-022).
"""

import contextlib
import json
import os
import tempfile
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
from pydantic import BaseModel

from app.models.var import VarRun
from app.services.var.return_panel import ReturnPanel

ESTIMATE_COLUMNS = [
    "date",
    "method",
    "lookback_code",
    "lookback_days",
    "scenario_count",
    "excluded_scenarios",
    "actual_mv_pct",
    "proxied_mv_pct",
    "rescaled_mv_pct",
    "quality",
    "quality_reason",
    "var_9500_gbp",
    "var_9750_gbp",
    "var_9900_gbp",
    "es_9500_gbp",
    "es_9750_gbp",
    "es_9900_gbp",
    "row_fingerprint",
    "methodology_version",
    "run_id",
    "computed_at",
]

OUTCOME_COLUMNS = [
    "date",
    "outcome_date",
    "outcome_status",
    "total_value_gbp",
    "risky_value_gbp",
    "hypothetical_pnl_gbp",
    "ladder_pnl_gbp",
    "row_fingerprint",
    "run_id",
    "computed_at",
]

INSTRUMENT_COLUMNS = [
    "identifier",
    "sub_accounts",
    "first_observed_date",
    "last_observed_date",
    "proxy",
    "proxy_mode",
    "proxy_scale",
    "outlier_count",
]

_DATE_COLUMNS = {"date", "first_observed_date", "last_observed_date", "outcome_date"}
_DATETIME_COLUMNS = {"computed_at"}


class VarMeta(BaseModel):
    """Metadata persisted alongside each account's VaR store as var/meta.json."""

    account_name: str
    methodology_version: str
    config_fingerprint: str
    last_successful_run_id: str
    updated_at: datetime


def _empty_frame(columns: list[str]) -> pd.DataFrame:
    """Return an empty DataFrame with exactly the given columns.

    Args:
        columns: Column names, in order.

    Returns:
        A zero-row DataFrame with those columns.
    """
    return pd.DataFrame(columns=columns)


def _read_csv_or_empty(path: Path, columns: list[str]) -> pd.DataFrame:
    """Read a stored CSV, or return an empty, correctly-shaped frame if it doesn't exist.

    Args:
        path: Path to the CSV file.
        columns: The canonical columns for this store (used both for the empty case and
            to reindex a non-empty read, so column order is always stable).

    Returns:
        DataFrame with date-like columns parsed to pandas Timestamps.
    """
    if not path.exists():
        return _empty_frame(columns)
    df = pd.read_csv(path)
    if df.empty:
        return _empty_frame(columns)
    return _parse_date_columns(df).reindex(columns=columns)


def _format_for_csv(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of df with date/datetime columns formatted as ISO strings.

    Args:
        df: The DataFrame to format (not mutated).

    Returns:
        A copy safe to pass to DataFrame.to_csv() with stable, re-parseable output.
    """
    out = df.copy()
    for col in _DATE_COLUMNS:
        if col in out.columns:
            out[col] = pd.to_datetime(out[col]).dt.strftime("%Y-%m-%d")
    for col in _DATETIME_COLUMNS:
        if col in out.columns:
            out[col] = pd.to_datetime(out[col]).dt.strftime("%Y-%m-%dT%H:%M:%S")
    return out


def _parse_date_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of df with every known date/datetime column parsed to Timestamp.

    Normalises both freshly read CSV data and caller-supplied frames (which may hold
    plain `datetime.date`/`datetime.datetime` objects) to the same dtype, so merging and
    sorting never mixes `Timestamp` with `date` in one object-dtype column.

    Args:
        df: The DataFrame to normalise (not mutated).

    Returns:
        A copy with date-like columns converted via pd.to_datetime().
    """
    out = df.copy()
    for col in _DATE_COLUMNS:
        if col in out.columns and not out.empty:
            out[col] = pd.to_datetime(out[col])
    for col in _DATETIME_COLUMNS:
        if col in out.columns and not out.empty:
            # Stored timestamps round-trip through the CSV as naive (UTC, implicitly --
            # see _format_for_csv). Caller-supplied values may be tz-aware (e.g.
            # datetime.now(UTC)); normalise both to the same naive-UTC dtype so merging
            # never mixes tz-aware and tz-naive datetimes in one column.
            parsed = pd.to_datetime(out[col], utc=True)
            out[col] = parsed.dt.tz_localize(None)
    return out


def _upsert_by_date(existing: pd.DataFrame, new: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Replace every row whose `date` appears in `new`, keeping all other existing rows.

    Args:
        existing: The currently stored rows (already date-parsed).
        new: The freshly computed rows for the dates being (re)computed (already
            date-parsed). May contain multiple rows per date (e.g. one per look-back).
        columns: Canonical column order for the result.

    Returns:
        The merged frame, reindexed to `columns`. Not sorted -- callers sort afterwards.
    """
    if new.empty:
        merged = existing
    elif existing.empty:
        merged = new
    else:
        touched_dates = set(new["date"])
        kept = existing[~existing["date"].isin(touched_dates)]
        merged = pd.concat([kept, new], ignore_index=True)

    if merged.empty:
        return _empty_frame(columns)
    return merged.reindex(columns=columns)


class VarRepository:
    """Read/write the VaR calculation store to the local filesystem.

    Layout, per account:
        data_dir/{account}/var/estimates.csv
        data_dir/{account}/var/outcomes.csv
        data_dir/{account}/var/instruments.csv
        data_dir/{account}/var/meta.json
        data_dir/{account}/var/runs/{run_id}.json
    """

    def __init__(self, data_dir: Path) -> None:
        """Initialise with the base data directory (shared with LadderRepository).

        Args:
            data_dir: Root directory under which per-account subdirectories live.
        """
        self._data_dir = data_dir

    def _var_dir(self, account_name: str) -> Path:
        """Return the account's var/ subdirectory.

        Args:
            account_name: The account identifier.

        Returns:
            Path to data_dir/{account_name}/var.
        """
        return self._data_dir / account_name / "var"

    def _runs_dir(self, account_name: str) -> Path:
        """Return the account's var/runs/ subdirectory.

        Args:
            account_name: The account identifier.

        Returns:
            Path to data_dir/{account_name}/var/runs.
        """
        return self._var_dir(account_name) / "runs"

    def _estimates_path(self, account_name: str) -> Path:
        """Return the path to the account's estimates.csv."""
        return self._var_dir(account_name) / "estimates.csv"

    def _outcomes_path(self, account_name: str) -> Path:
        """Return the path to the account's outcomes.csv."""
        return self._var_dir(account_name) / "outcomes.csv"

    def _instruments_path(self, account_name: str) -> Path:
        """Return the path to the account's instruments.csv."""
        return self._var_dir(account_name) / "instruments.csv"

    def _meta_path(self, account_name: str) -> Path:
        """Return the path to the account's var/meta.json."""
        return self._var_dir(account_name) / "meta.json"

    def _scenario_returns_path(self, account_name: str) -> Path:
        """Return the path to the account's var/scenario_returns.csv."""
        return self._var_dir(account_name) / "scenario_returns.csv"

    def _scenario_observed_path(self, account_name: str) -> Path:
        """Return the path to the account's var/scenario_observed.csv."""
        return self._var_dir(account_name) / "scenario_observed.csv"

    def _scenario_returns_meta_path(self, account_name: str) -> Path:
        """Return the path to the account's var/scenario_returns_meta.json."""
        return self._var_dir(account_name) / "scenario_returns_meta.json"

    def _run_path(self, account_name: str, run_id: str) -> Path:
        """Return the path to one run's JSON record.

        Args:
            account_name: The account identifier.
            run_id: The run identifier.

        Returns:
            Path to data_dir/{account_name}/var/runs/{run_id}.json.
        """
        return self._runs_dir(account_name) / f"{run_id}.json"

    def read_estimates(self, account_name: str) -> pd.DataFrame:
        """Read every stored VaR estimate row for an account.

        Args:
            account_name: The account identifier.

        Returns:
            DataFrame with ESTIMATE_COLUMNS; empty (but correctly shaped) if nothing has
            ever been committed.
        """
        return _read_csv_or_empty(self._estimates_path(account_name), ESTIMATE_COLUMNS)

    def read_outcomes(self, account_name: str) -> pd.DataFrame:
        """Read every stored realised-outcome row for an account.

        Args:
            account_name: The account identifier.

        Returns:
            DataFrame with OUTCOME_COLUMNS; empty (but correctly shaped) if nothing has
            ever been committed.
        """
        return _read_csv_or_empty(self._outcomes_path(account_name), OUTCOME_COLUMNS)

    def read_instruments(self, account_name: str) -> pd.DataFrame:
        """Read the last successful run's per-instrument treatment summary.

        Unlike estimates/outcomes, the instrument table's columns are not fixed: beyond
        INSTRUMENT_COLUMNS it carries one dynamic treatment_<code> column per configured
        look-back, so a stored file's own columns are read as-is rather than reindexed.

        Args:
            account_name: The account identifier.

        Returns:
            DataFrame with INSTRUMENT_COLUMNS (plus any stored treatment_<code> columns);
            empty (but correctly shaped to INSTRUMENT_COLUMNS) if nothing has ever been
            committed.
        """
        path = self._instruments_path(account_name)
        if not path.exists():
            return _empty_frame(INSTRUMENT_COLUMNS)
        df = pd.read_csv(path)
        if df.empty:
            return _empty_frame(INSTRUMENT_COLUMNS)
        return _parse_date_columns(df)

    def read_meta(self, account_name: str) -> VarMeta | None:
        """Read the account's var/meta.json.

        Args:
            account_name: The account identifier.

        Returns:
            The stored VarMeta, or None if nothing has ever been committed.
        """
        path = self._meta_path(account_name)
        if not path.exists():
            return None
        with path.open(encoding="utf-8") as f:
            return VarMeta.model_validate(json.load(f))

    def read_scenario_returns(self, account_name: str) -> ReturnPanel | None:
        """Read the account's accumulated, look-back-independent scenario-returns snapshot.

        Unlike estimates/outcomes/instruments, this store has no fixed column set: each
        column is an identifier that has ever been fetched by some run for this account
        (015-var-contributions, research.md §2).

        Args:
            account_name: The account identifier.

        Returns:
            A ReturnPanel reconstructed from the stored wide CSVs, or None if nothing has
            ever been committed.
        """
        returns_path = self._scenario_returns_path(account_name)
        observed_path = self._scenario_observed_path(account_name)
        meta_path = self._scenario_returns_meta_path(account_name)
        if not (returns_path.exists() and observed_path.exists() and meta_path.exists()):
            return None

        returns_df = pd.read_csv(returns_path, index_col="date", parse_dates=["date"])
        observed_df = pd.read_csv(observed_path, index_col="date", parse_dates=["date"])
        if returns_df.empty:
            return None

        returns_df = returns_df.sort_index()
        observed_df = observed_df.sort_index().reindex(columns=returns_df.columns)

        with meta_path.open(encoding="utf-8") as f:
            meta = json.load(f)

        identifiers = tuple(returns_df.columns)
        grid = tuple(ts.date() for ts in returns_df.index)
        first_observed: dict[str, date | None] = {}
        for identifier in identifiers:
            raw = meta.get("identifiers", {}).get(identifier, {}).get("first_observed_date")
            first_observed[identifier] = date.fromisoformat(raw) if raw else None

        return ReturnPanel(
            grid=grid,
            identifiers=identifiers,
            returns=returns_df.to_numpy(dtype=float),
            observed=observed_df.fillna(0).to_numpy(dtype=bool),
            first_observed=first_observed,
        )

    def commit_scenario_returns(self, account_name: str, panel: ReturnPanel) -> None:
        """Upsert a run's fetched scenario-returns panel into the accumulated snapshot.

        New dates/identifiers are outer-joined onto whatever is already stored; any cell
        within `panel`'s own (grid x identifiers) rectangle replaces the stored value
        (including with NaN/not-observed, if that is what `panel` holds for that cell) --
        the same "latest fetch wins" semantics a stale re-fetch already has for estimates
        (research.md §2). All-or-none: writes every file to a temp path first, then
        `os.replace()`s them in turn, matching `commit()`'s existing atomicity.

        Args:
            account_name: The account identifier.
            panel: The freshly fetched ReturnPanel to merge in.

        Raises:
            OSError: If any underlying file write fails. The store is left unchanged.
        """
        var_dir = self._var_dir(account_name)
        var_dir.mkdir(parents=True, exist_ok=True)

        existing = self.read_scenario_returns(account_name)
        incoming_index = pd.DatetimeIndex([pd.Timestamp(d) for d in panel.grid])
        incoming_returns = pd.DataFrame(
            panel.returns, index=incoming_index, columns=list(panel.identifiers)
        )
        incoming_observed = pd.DataFrame(
            panel.observed, index=incoming_index, columns=list(panel.identifiers)
        )

        if existing is None:
            merged_returns = incoming_returns
            merged_observed = incoming_observed
            merged_first_observed = dict(panel.first_observed)
        else:
            existing_index = pd.DatetimeIndex([pd.Timestamp(d) for d in existing.grid])
            existing_returns = pd.DataFrame(
                existing.returns, index=existing_index, columns=list(existing.identifiers)
            )
            existing_observed = pd.DataFrame(
                existing.observed, index=existing_index, columns=list(existing.identifiers)
            )

            union_index = existing_index.union(incoming_index).sort_values()
            union_columns = sorted(set(existing.identifiers) | set(panel.identifiers))

            existing_r = existing_returns.reindex(index=union_index, columns=union_columns)
            existing_o = existing_observed.reindex(index=union_index, columns=union_columns)
            incoming_r = incoming_returns.reindex(index=union_index, columns=union_columns)
            incoming_o = incoming_observed.reindex(index=union_index, columns=union_columns)

            mask = pd.DataFrame(False, index=union_index, columns=union_columns)
            mask.loc[incoming_index, list(panel.identifiers)] = True

            merged_returns = existing_r.where(~mask, incoming_r)
            merged_observed = existing_o.where(~mask, incoming_o)
            merged_first_observed = {**existing.first_observed, **panel.first_observed}

        merged_returns = merged_returns.sort_index()
        merged_observed = merged_observed.sort_index().reindex(columns=merged_returns.columns)
        merged_returns.index.name = "date"
        merged_observed.index.name = "date"

        meta_payload: dict[str, object] = {
            "identifiers": {
                identifier: {
                    "first_observed_date": d.isoformat() if d else None,
                }
                for identifier, d in sorted(merged_first_observed.items())
            },
            "updated_at": datetime.now(UTC).isoformat(),
        }

        tmp_paths: list[Path] = []
        try:
            returns_tmp = self._write_temp_csv(
                var_dir, merged_returns.reset_index(), ["date", *merged_returns.columns]
            )
            tmp_paths.append(returns_tmp)
            observed_tmp = self._write_temp_csv(
                var_dir,
                merged_observed.astype("Int64").reset_index(),
                ["date", *merged_observed.columns],
            )
            tmp_paths.append(observed_tmp)
            meta_tmp = self._write_temp_json(var_dir, meta_payload)
            tmp_paths.append(meta_tmp)
        except Exception:
            for tmp in tmp_paths:
                with contextlib.suppress(OSError):
                    os.unlink(tmp)
            raise

        os.replace(returns_tmp, self._scenario_returns_path(account_name))
        os.replace(observed_tmp, self._scenario_observed_path(account_name))
        os.replace(meta_tmp, self._scenario_returns_meta_path(account_name))

    def commit(
        self,
        account_name: str,
        estimates: pd.DataFrame,
        outcomes: pd.DataFrame,
        instruments: pd.DataFrame,
        meta: VarMeta,
    ) -> None:
        """Upsert a run's results into the store, all-or-none.

        Builds the complete new contents of estimates.csv, outcomes.csv and
        instruments.csv in memory, writes each to a temporary file in the var/
        directory, and only once every temp file exists does it os.replace() them into
        place in turn, with meta.json last. If any step raises, every temp file created
        so far is removed and no existing file is modified (FR-022).

        Args:
            account_name: The account identifier.
            estimates: New/recomputed estimate rows (any subset of ESTIMATE_COLUMNS'
                dates); every existing row whose date appears here is replaced.
            outcomes: New/recomputed outcome rows (one per date); every existing row
                whose date appears here is replaced.
            instruments: The full replacement instrument-treatment table (not upserted --
                always a complete snapshot from the triggering run).
            meta: The new VarMeta to persist.

        Raises:
            OSError: If any underlying file write fails. The store is left unchanged.
        """
        var_dir = self._var_dir(account_name)
        var_dir.mkdir(parents=True, exist_ok=True)

        merged_estimates = _upsert_by_date(
            self.read_estimates(account_name), _parse_date_columns(estimates), ESTIMATE_COLUMNS
        )
        if not merged_estimates.empty:
            merged_estimates = merged_estimates.sort_values(["date", "lookback_days"]).reset_index(
                drop=True
            )

        merged_outcomes = _upsert_by_date(
            self.read_outcomes(account_name), _parse_date_columns(outcomes), OUTCOME_COLUMNS
        )
        if not merged_outcomes.empty:
            merged_outcomes = merged_outcomes.sort_values("date").reset_index(drop=True)

        # Unlike estimates/outcomes, the instrument table's columns are not fixed: it
        # always carries the INSTRUMENT_COLUMNS base plus one dynamic treatment_<code>
        # column per configured look-back (feature 012 User Story 6). Preserve whatever
        # columns the caller supplies rather than reindexing to a fixed set.
        instruments_out = _parse_date_columns(instruments)
        instrument_columns = (
            list(instruments_out.columns) if not instruments_out.empty else INSTRUMENT_COLUMNS
        )

        tmp_paths: list[Path] = []
        try:
            estimates_tmp = self._write_temp_csv(
                var_dir, _format_for_csv(merged_estimates), ESTIMATE_COLUMNS
            )
            tmp_paths.append(estimates_tmp)
            outcomes_tmp = self._write_temp_csv(
                var_dir, _format_for_csv(merged_outcomes), OUTCOME_COLUMNS
            )
            tmp_paths.append(outcomes_tmp)
            instruments_tmp = self._write_temp_csv(
                var_dir, _format_for_csv(instruments_out), instrument_columns
            )
            tmp_paths.append(instruments_tmp)
            meta_tmp = self._write_temp_json(var_dir, meta.model_dump(mode="json"))
            tmp_paths.append(meta_tmp)
        except Exception:
            for tmp in tmp_paths:
                with contextlib.suppress(OSError):
                    os.unlink(tmp)
            raise

        os.replace(estimates_tmp, self._estimates_path(account_name))
        os.replace(outcomes_tmp, self._outcomes_path(account_name))
        os.replace(instruments_tmp, self._instruments_path(account_name))
        os.replace(meta_tmp, self._meta_path(account_name))

    def _write_temp_csv(self, var_dir: Path, df: pd.DataFrame, columns: list[str]) -> Path:
        """Write a DataFrame to a temp CSV file in var_dir and return its path.

        Args:
            var_dir: The account's var/ directory (already created).
            df: The (already CSV-formatted) DataFrame to write.
            columns: Column order to enforce.

        Returns:
            Path to the written temporary file.
        """
        fd, tmp_path = tempfile.mkstemp(dir=var_dir, suffix=".csv.tmp")
        os.close(fd)
        try:
            df.reindex(columns=columns).to_csv(tmp_path, index=False)
        except Exception:
            with contextlib.suppress(OSError):
                os.unlink(tmp_path)
            raise
        return Path(tmp_path)

    def _write_temp_json(self, var_dir: Path, payload: dict[str, object]) -> Path:
        """Write a dict to a temp JSON file in var_dir and return its path.

        Args:
            var_dir: The account's var/ directory (already created).
            payload: JSON-serialisable content.

        Returns:
            Path to the written temporary file.
        """
        fd, tmp_path = tempfile.mkstemp(dir=var_dir, suffix=".json.tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, default=str)
        except Exception:
            with contextlib.suppress(OSError):
                os.unlink(tmp_path)
            raise
        return Path(tmp_path)

    def write_run(self, account_name: str, run: VarRun) -> None:
        """Persist a run record atomically.

        Args:
            account_name: The account identifier.
            run: The VarRun to write (overwrites any existing record with the same id).
        """
        runs_dir = self._runs_dir(account_name)
        runs_dir.mkdir(parents=True, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=runs_dir, suffix=".json.tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(run.model_dump_json(by_alias=True))
        except Exception:
            with contextlib.suppress(OSError):
                os.unlink(tmp_path)
            raise
        os.replace(tmp_path, self._run_path(account_name, run.run_id))

    def read_run(self, account_name: str, run_id: str) -> VarRun | None:
        """Read one run record.

        Args:
            account_name: The account identifier.
            run_id: The run identifier.

        Returns:
            The stored VarRun, or None if it does not exist.
        """
        path = self._run_path(account_name, run_id)
        if not path.exists():
            return None
        return VarRun.model_validate_json(path.read_text(encoding="utf-8"))

    def list_runs(self, account_name: str) -> list[VarRun]:
        """List every run record for an account, newest first.

        Args:
            account_name: The account identifier.

        Returns:
            VarRun records sorted by requested_at descending; empty list if the account
            has no runs directory.
        """
        runs_dir = self._runs_dir(account_name)
        if not runs_dir.exists():
            return []
        runs = [
            VarRun.model_validate_json(path.read_text(encoding="utf-8"))
            for path in runs_dir.glob("*.json")
        ]
        return sorted(runs, key=lambda r: r.requested_at, reverse=True)

    def list_accounts_with_runs(self) -> list[str]:
        """List every account that has at least one VaR run recorded.

        Returns:
            Account names (subdirectory names of data_dir) with a var/runs directory.
        """
        if not self._data_dir.exists():
            return []
        return [
            child.name
            for child in self._data_dir.iterdir()
            if child.is_dir() and (child / "var" / "runs").is_dir()
        ]
