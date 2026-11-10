"""Unit tests for StalenessGate's rebuild decision (014)."""

from datetime import date

from app.services.rebuild.staleness_gate import StalenessGate


class TestNoRebuildNeededWhenAlreadyCovered:
    """No rebuild is needed when the resolved end is already covered."""

    def test_no_rebuild_needed_when_resolved_end_equals_last_known_date(self) -> None:
        """resolved_end == last_known_date requires no rebuild."""
        gate = StalenessGate()
        decision = gate.evaluate(
            last_known_date=date(2026, 11, 6),
            resolved_end=date(2026, 11, 6),
            today=date(2026, 11, 10),
        )
        assert decision.rebuild_needed is False

    def test_no_rebuild_needed_when_resolved_end_before_last_known_date(self) -> None:
        """resolved_end before last_known_date requires no rebuild."""
        gate = StalenessGate()
        decision = gate.evaluate(
            last_known_date=date(2026, 11, 6),
            resolved_end=date(2026, 10, 1),
            today=date(2026, 11, 10),
        )
        assert decision.rebuild_needed is False


class TestRebuildNeededWhenResolvedEndIsLater:
    """A rebuild is needed and correctly capped when resolved_end is later."""

    def test_rebuild_needed_when_resolved_end_exceeds_last_known_date(self) -> None:
        """A multi-week gap triggers rebuild_needed=True."""
        gate = StalenessGate()
        decision = gate.evaluate(
            last_known_date=date(2026, 9, 23),
            resolved_end=date(2026, 11, 6),
            today=date(2026, 11, 10),
        )
        assert decision.rebuild_needed is True

    def test_rebuild_target_end_is_the_prior_business_day_relative_to_today(self) -> None:
        """The target end date is always today's T-1/T-0 business-day cap, not resolved_end."""
        gate = StalenessGate()
        # 2026-11-10 is a Tuesday; the most recent business day on/before it is itself.
        decision = gate.evaluate(
            last_known_date=date(2026, 9, 23),
            resolved_end=date(2026, 11, 6),
            today=date(2026, 11, 10),
        )
        assert decision.rebuild_target_end == date(2026, 11, 10)

    def test_rebuild_target_end_never_exceeds_the_prior_business_day_even_for_a_weekend_today(
        self,
    ) -> None:
        """When today itself is a Saturday, the cap rolls back to the preceding Friday."""
        gate = StalenessGate()
        saturday = date(2026, 11, 14)
        decision = gate.evaluate(
            last_known_date=date(2026, 9, 23), resolved_end=date(2026, 11, 13), today=saturday
        )
        assert decision.rebuild_target_end == date(2026, 11, 13)
        assert decision.rebuild_target_end <= saturday
