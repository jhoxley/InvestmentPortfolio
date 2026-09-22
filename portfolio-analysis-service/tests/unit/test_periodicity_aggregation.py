"""Unit tests for the pure calendar-period aggregation helper."""

from datetime import date

import pandas as pd

from app.models.periodicity import Periodicity
from app.services.periodicity_aggregation import aggregate_last_observation

# The decade used throughout the spec's success criteria (SC-002/SC-006). Verified in
# research.md §4: 2608 business days -> 10 annual / 40 quarterly / 120 monthly / 522 weekly.
DECADE_START = date(2016, 1, 4)
DECADE_END = date(2025, 12, 31)


def _daily_frame(start: date, end: date, columns: int = 1) -> pd.DataFrame:
    """Build a business-day-complete frame shaped like expand_business_days() output.

    Each value column carries a distinct, strictly increasing series so that "the last
    observation in the window" is unambiguous and cross-column consistency is detectable.

    Args:
        start: First business day (inclusive).
        end: Last business day (inclusive).
        columns: How many numeric value columns to generate.

    Returns:
        DataFrame with a `date` column of datetime.date plus `value_0..value_n`.
    """
    business_days = pd.bdate_range(start=start, end=end)
    data: dict[str, object] = {"date": [d.date() for d in business_days]}
    for i in range(columns):
        offset = i * 1_000_000
        data[f"value_{i}"] = [float(offset + n) for n in range(len(business_days))]
    return pd.DataFrame(data)


class TestDayPeriodicityIsIdentity:
    """`day` must return the input untouched so existing behaviour is structural (FR-003)."""

    def test_day_returns_input_unchanged(self) -> None:
        """Row count, dates, values and column order are all preserved."""
        df = _daily_frame(date(2026, 1, 5), date(2026, 1, 30), columns=2)
        result = aggregate_last_observation(df, Periodicity.DAY, date(2026, 1, 5))

        assert list(result.columns) == list(df.columns)
        pd.testing.assert_frame_equal(result, df)


class TestWindowCounts:
    """A ten-year range must divide into exactly the counts the spec promises (SC-002)."""

    def test_daily_baseline_row_count(self) -> None:
        """The decade fixture holds the expected 2608 business days."""
        assert len(_daily_frame(DECADE_START, DECADE_END)) == 2608

    def test_window_counts_per_periodicity(self) -> None:
        """annual=10, quarter=40, month=120, week=522 over 2016-01-04..2025-12-31."""
        df = _daily_frame(DECADE_START, DECADE_END)
        expected = {
            Periodicity.ANNUAL: 10,
            Periodicity.QUARTER: 40,
            Periodicity.MONTH: 120,
            Periodicity.WEEK: 522,
        }
        for periodicity, count in expected.items():
            result = aggregate_last_observation(df, periodicity, DECADE_START)
            assert len(result) == count, f"{periodicity.value} produced {len(result)} windows"


class TestCalendarAlignment:
    """Windows align to the real calendar, not to the requested dates (FR-005, FR-006)."""

    def test_weeks_begin_on_monday(self) -> None:
        """Every weekly entry falls on a Monday (no weekend Mondays exist to roll)."""
        df = _daily_frame(date(2026, 1, 5), date(2026, 2, 27))
        result = aggregate_last_observation(df, Periodicity.WEEK, date(2026, 1, 5))
        for d in result["date"]:
            assert d.weekday() == 0, f"Weekly window not dated on a Monday: {d}"

    def test_months_begin_on_the_first_or_next_business_day(self) -> None:
        """Every monthly entry is the 1st, or the first business day after it."""
        df = _daily_frame(date(2026, 1, 1), date(2026, 6, 30))
        result = aggregate_last_observation(df, Periodicity.MONTH, date(2026, 1, 1))
        for d in result["date"]:
            first_of_month = d.replace(day=1)
            expected = pd.bdate_range(start=first_of_month, periods=1)[0].date()
            assert d == expected, f"Monthly window {d} is not month-start-aligned"

    def test_february_2026_rolls_forward_from_a_sunday(self) -> None:
        """2026-02-01 is a Sunday, so February's window is dated 2026-02-02."""
        df = _daily_frame(date(2026, 1, 1), date(2026, 3, 31))
        result = aggregate_last_observation(df, Periodicity.MONTH, date(2026, 1, 1))
        assert date(2026, 2, 2) in set(result["date"])
        assert date(2026, 2, 1) not in set(result["date"])

    def test_quarters_begin_in_january_april_july_october(self) -> None:
        """Quarterly entries fall in the four calendar quarter-start months."""
        df = _daily_frame(date(2025, 1, 1), date(2025, 12, 31))
        result = aggregate_last_observation(df, Periodicity.QUARTER, date(2025, 1, 1))
        assert list(result["date"]) == [
            date(2025, 1, 1),
            date(2025, 4, 1),
            date(2025, 7, 1),
            date(2025, 10, 1),
        ]

    def test_annual_windows_begin_on_01_january(self) -> None:
        """Annual entries fall on 1 January, rolled forward when it is a weekend."""
        df = _daily_frame(date(2023, 1, 2), date(2025, 12, 31))
        result = aggregate_last_observation(df, Periodicity.ANNUAL, date(2023, 1, 2))
        assert list(result["date"]) == [date(2023, 1, 2), date(2024, 1, 1), date(2025, 1, 1)]


class TestFirstWindowIsClampedToResolvedStart:
    """A partial first window is dated at the resolved start, never the calendar boundary."""

    def test_partial_first_annual_window_is_clamped(self) -> None:
        """A range starting 2016-03-15 is dated 2016-03-15, not 2016-01-01 (FR-006)."""
        start = date(2016, 3, 15)
        df = _daily_frame(start, date(2017, 12, 29))
        result = aggregate_last_observation(df, Periodicity.ANNUAL, start)

        assert list(result["date"]) == [start, date(2017, 1, 2)]

    def test_no_entry_date_precedes_the_resolved_start(self) -> None:
        """Across every periodicity, no reported date falls outside the resolved range."""
        start = date(2016, 3, 15)
        end = date(2017, 12, 29)
        df = _daily_frame(start, end)
        for periodicity in (Periodicity.WEEK, Periodicity.MONTH, Periodicity.QUARTER):
            result = aggregate_last_observation(df, periodicity, start)
            assert result["date"].min() >= start
            assert result["date"].max() <= end


class TestLastObservationSemantics:
    """Each entry carries the last in-window observation, all from one source row."""

    def test_value_is_the_windows_last_observation(self) -> None:
        """The 2016 annual entry carries the value recorded on 2016-12-30."""
        df = _daily_frame(DECADE_START, DECADE_END)
        expected_2016 = df.loc[df["date"] == date(2016, 12, 30), "value_0"].iloc[0]

        result = aggregate_last_observation(df, Periodicity.ANNUAL, DECADE_START)
        first_row = result.iloc[0]

        assert first_row["date"] == DECADE_START
        assert first_row["value_0"] == expected_2016

    def test_all_attributes_come_from_the_same_source_date(self) -> None:
        """Every column on one entry is drawn from a single input row (FR-008)."""
        df = _daily_frame(date(2025, 1, 1), date(2025, 6, 30), columns=3)
        result = aggregate_last_observation(df, Periodicity.MONTH, date(2025, 1, 1))

        for _, row in result.iterrows():
            matches = df[
                (df["value_0"] == row["value_0"])
                & (df["value_1"] == row["value_1"])
                & (df["value_2"] == row["value_2"])
            ]
            assert len(matches) == 1, "Columns were drawn from different source dates"

    def test_partial_last_window_reports_the_resolved_end_value(self) -> None:
        """An incomplete final window is kept and valued at the resolved end (FR-007)."""
        start = date(2025, 1, 1)
        end = date(2025, 5, 14)
        df = _daily_frame(start, end)
        expected_last = df.loc[df["date"] == end, "value_0"].iloc[0]

        result = aggregate_last_observation(df, Periodicity.QUARTER, start)

        assert list(result["date"]) == [start, date(2025, 4, 1)]
        assert result.iloc[-1]["value_0"] == expected_last


class TestDegenerateRanges:
    """Very short and empty ranges must not raise or silently drop data."""

    def test_range_shorter_than_one_period_yields_one_entry(self) -> None:
        """Three business days at annual periodicity give one entry at the resolved start."""
        start = date(2025, 6, 2)
        end = date(2025, 6, 4)
        df = _daily_frame(start, end)
        expected_last = df.loc[df["date"] == end, "value_0"].iloc[0]

        result = aggregate_last_observation(df, Periodicity.ANNUAL, start)

        assert len(result) == 1
        assert result.iloc[0]["date"] == start
        assert result.iloc[0]["value_0"] == expected_last

    def test_empty_input_returns_empty(self) -> None:
        """An empty frame aggregates to an empty frame with the same columns."""
        df = pd.DataFrame({"date": [], "value_0": []})
        result = aggregate_last_observation(df, Periodicity.MONTH, date(2025, 1, 1))

        assert len(result) == 0
        assert list(result.columns) == ["date", "value_0"]


class TestPurityAndShape:
    """The helper must not mutate its caller's frame, and must return a clean shape."""

    def test_input_frame_is_not_mutated(self) -> None:
        """The caller's frame is unchanged after aggregation."""
        df = _daily_frame(date(2025, 1, 1), date(2025, 3, 31), columns=2)
        before = df.copy(deep=True)

        aggregate_last_observation(df, Periodicity.MONTH, date(2025, 1, 1))

        pd.testing.assert_frame_equal(df, before)

    def test_output_preserves_column_order_and_resets_index(self) -> None:
        """Columns keep their order and the index is a clean RangeIndex."""
        df = _daily_frame(date(2025, 1, 1), date(2025, 3, 31), columns=2)
        result = aggregate_last_observation(df, Periodicity.MONTH, date(2025, 1, 1))

        assert list(result.columns) == ["date", "value_0", "value_1"]
        assert list(result.index) == list(range(len(result)))

    def test_output_is_sorted_ascending_by_date(self) -> None:
        """Entries are ordered by date ascending (FR-010)."""
        df = _daily_frame(DECADE_START, DECADE_END)
        result = aggregate_last_observation(df, Periodicity.QUARTER, DECADE_START)
        dates = list(result["date"])

        assert dates == sorted(dates)


class TestWindowDatesAreUniformAcrossFrames:
    """Window dates depend only on (period, resolved_start) — never on the frame's rows."""

    def test_frames_with_different_coverage_share_window_dates(self) -> None:
        """Two positions covering different sub-ranges align on their shared windows."""
        resolved_start = date(2025, 1, 1)
        full = _daily_frame(resolved_start, date(2025, 12, 31))
        partial = _daily_frame(date(2025, 4, 15), date(2025, 12, 31))

        full_result = aggregate_last_observation(full, Periodicity.QUARTER, resolved_start)
        partial_result = aggregate_last_observation(partial, Periodicity.QUARTER, resolved_start)

        shared = set(full_result["date"]) & set(partial_result["date"])
        assert date(2025, 4, 1) in shared
        assert date(2025, 7, 1) in shared
        assert date(2025, 10, 1) in shared
        # The later-starting frame contributes no entry before its own first window.
        assert set(partial_result["date"]) == {
            date(2025, 4, 1),
            date(2025, 7, 1),
            date(2025, 10, 1),
        }
