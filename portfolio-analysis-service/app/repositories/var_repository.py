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
from datetime import datetime
from pathlib import Path

import pandas as pd
from pydantic import BaseModel

from app.models.var import VarRun

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
    for col in _DATE_COLUMNS | _DATETIME_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col])
    return df.reindex(columns=columns)


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
    for col in _DATE_COLUMNS | _DATETIME_COLUMNS:
        if col in out.columns and not out.empty:
            out[col] = pd.to_datetime(out[col])
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

        Args:
            account_name: The account identifier.

        Returns:
            DataFrame with INSTRUMENT_COLUMNS; empty (but correctly shaped) if nothing has
            ever been committed.
        """
        return _read_csv_or_empty(self._instruments_path(account_name), INSTRUMENT_COLUMNS)

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

        instruments_out = _parse_date_columns(instruments).reindex(columns=INSTRUMENT_COLUMNS)

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
                var_dir, _format_for_csv(instruments_out), INSTRUMENT_COLUMNS
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
