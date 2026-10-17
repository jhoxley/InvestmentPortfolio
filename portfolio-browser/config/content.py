"""Typed, fail-fast loader for the app's static content configuration.

Holds non-secret, human-edited values (app name, build info, nav section
labels) that must never be hardcoded as string literals in application code
(project constitution, Principle IV).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, field_validator, model_validator

_UNKNOWN = "unknown"

# The canonical periodicity option keys (021). Code branches on these, so they
# are a fixed, spec-defined set and deliberately NOT configurable — the same
# split `src/components/date_range_controls.py` documents for its shortcut
# codes. Labels, service-side values and thresholds ARE configurable below.
PERIODICITY_DAY = "day"
PERIODICITY_WEEK = "week"
PERIODICITY_MONTH = "month"
PERIODICITY_QUARTER = "quarter"
PERIODICITY_YEAR = "year"

# Every key an automatic derivation can resolve to. `week` is absent by design:
# it is selectable but never derived (FR-009).
_DERIVABLE_PERIODICITY_KEYS = (
    PERIODICITY_DAY,
    PERIODICITY_MONTH,
    PERIODICITY_QUARTER,
    PERIODICITY_YEAR,
)

_EXPECTED_PERIODICITY_OPTIONS = 5


class NavigationSection(BaseModel):
    key: str
    label: str
    order: int
    is_default: bool = False


class BuildInfo(BaseModel):
    version: str = _UNKNOWN
    published_date: str = _UNKNOWN

    @field_validator("version", "published_date", mode="before")
    @classmethod
    def _normalize_missing(cls, value: object) -> object:
        if value is None or value == "":
            return _UNKNOWN
        return value


class PeriodicityOption(BaseModel):
    """One selectable charting interval (021).

    `key` is the stable identifier code branches on; `label` is what the user
    sees; `value` is what the analysis service is asked for. They coincide for
    every option except `year`, whose service-side value is `annual`.
    """

    key: str
    label: str
    value: str

    @field_validator("key", "label", "value")
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("periodicity option key/label/value must not be blank")
        return value


class PeriodicityThresholds(BaseModel):
    """Upper bounds, in years, for each automatically derived interval (FR-008)."""

    day_max_years: int
    month_max_years: int
    quarter_max_years: int

    @field_validator("day_max_years", "month_max_years", "quarter_max_years")
    @classmethod
    def _reject_non_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("periodicity thresholds must be positive")
        return value

    @model_validator(mode="after")
    def _validate_ascending(self) -> PeriodicityThresholds:
        if not self.day_max_years < self.month_max_years < self.quarter_max_years:
            raise ValueError(
                "periodicity thresholds must be strictly ascending "
                f"(day={self.day_max_years} < month={self.month_max_years} "
                f"< quarter={self.quarter_max_years})"
            )
        return self


class PeriodicityConfig(BaseModel):
    """The Periodicity control's label, options and derivation thresholds (021)."""

    label: str
    options: list[PeriodicityOption]
    thresholds: PeriodicityThresholds

    @model_validator(mode="after")
    def _validate_options(self) -> PeriodicityConfig:
        if len(self.options) != _EXPECTED_PERIODICITY_OPTIONS:
            raise ValueError(
                f"periodicity.options must contain exactly "
                f"{_EXPECTED_PERIODICITY_OPTIONS} entries, found {len(self.options)}"
            )

        for field in ("key", "label", "value"):
            values = [getattr(option, field) for option in self.options]
            if len(values) != len(set(values)):
                raise ValueError(f"periodicity.options {field} values must be unique")

        keys = {option.key for option in self.options}
        missing = [key for key in _DERIVABLE_PERIODICITY_KEYS if key not in keys]
        if missing:
            raise ValueError(
                "periodicity.options is missing option(s) that automatic derivation "
                f"can resolve to: {', '.join(missing)}"
            )
        return self

    def option_for(self, key_or_value: str) -> PeriodicityOption | None:
        """Return the option matching a key or a service-side value.

        Args:
            key_or_value: Either an option `key` (e.g. "year") or its
                service-side `value` (e.g. "annual").

        Returns:
            The matching option, or None if nothing matches.
        """
        for option in self.options:
            if key_or_value in (option.key, option.value):
                return option
        return None

    def value_for_key(self, key: str) -> str:
        """Return the service-side value for an option key.

        Args:
            key: The option key to resolve.

        Returns:
            The `value` to send to the analysis service.

        Raises:
            KeyError: If no option carries that key.
        """
        for option in self.options:
            if option.key == key:
                return option.value
        raise KeyError(f"Unknown periodicity key: {key!r}")


_EXPECTED_PROJECTION_HORIZONS = 4
_EXPECTED_PROJECTION_RETURNS = 4


class ProjectionHorizon(BaseModel):
    """One preset projection-horizon button (022; FR-004).

    `key` is the stable identifier code branches on (and the DOM id suffix);
    `label` is what the user sees on the button; `years` is how many years
    past the current start date the button resolves to.
    """

    key: str
    label: str
    years: int

    @field_validator("key", "label")
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("projection horizon key/label must not be blank")
        return value

    @field_validator("years")
    @classmethod
    def _reject_non_positive_years(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("projection horizon years must be positive")
        return value


class ProjectionReturn(BaseModel):
    """One selectable projection return measure (022; FR-008).

    `key` is the wire-format value sent to the analysis service's `return`
    query parameter — the exact same measure name its performance endpoint
    already uses; `label` is what the user sees on its toggle switch —
    e.g. `key="ITD (Ann.)"`, `label="Ann. ITD"` (the shorter label is this
    page's own display concision, not a different calculation — spec
    Assumptions).
    """

    key: str
    label: str

    @field_validator("key", "label")
    @classmethod
    def _reject_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("projection return key/label must not be blank")
        return value


class ProjectionConfig(BaseModel):
    """The Projection page's horizon buttons and selectable returns (022)."""

    horizons: list[ProjectionHorizon]
    returns: list[ProjectionReturn]

    @model_validator(mode="after")
    def _validate_horizons(self) -> ProjectionConfig:
        if len(self.horizons) != _EXPECTED_PROJECTION_HORIZONS:
            raise ValueError(
                f"projection.horizons must contain exactly "
                f"{_EXPECTED_PROJECTION_HORIZONS} entries, found {len(self.horizons)}"
            )
        for field in ("key", "label"):
            values = [getattr(horizon, field) for horizon in self.horizons]
            if len(values) != len(set(values)):
                raise ValueError(f"projection.horizons {field} values must be unique")

        years = [horizon.years for horizon in self.horizons]
        if years != sorted(years) or len(years) != len(set(years)):
            raise ValueError("projection.horizons years must be strictly ascending")
        return self

    @model_validator(mode="after")
    def _validate_returns(self) -> ProjectionConfig:
        if len(self.returns) != _EXPECTED_PROJECTION_RETURNS:
            raise ValueError(
                f"projection.returns must contain exactly "
                f"{_EXPECTED_PROJECTION_RETURNS} entries, found {len(self.returns)}"
            )
        for field in ("key", "label"):
            values = [getattr(item, field) for item in self.returns]
            if len(values) != len(set(values)):
                raise ValueError(f"projection.returns {field} values must be unique")
        return self


class ContentConfig(BaseModel):
    app_name: str
    build_info: BuildInfo = BuildInfo()
    nav_sections: list[NavigationSection]
    # Mandatory: a missing section fails fast at startup rather than silently
    # defaulting to values hardcoded in application code (Principle IV).
    periodicity: PeriodicityConfig
    projection: ProjectionConfig

    @model_validator(mode="after")
    def _validate_nav_sections(self) -> ContentConfig:
        sections = self.nav_sections
        if not sections:
            raise ValueError("nav_sections must contain at least one section")

        keys = [section.key for section in sections]
        if len(keys) != len(set(keys)):
            raise ValueError("nav_sections keys must be unique")

        orders = [section.order for section in sections]
        if len(orders) != len(set(orders)):
            raise ValueError("nav_sections order values must be unique")

        default_count = sum(1 for section in sections if section.is_default)
        if default_count != 1:
            raise ValueError(
                "nav_sections must have exactly one section with is_default=True, "
                f"found {default_count}"
            )
        return self

    def default_section(self) -> NavigationSection:
        return next(section for section in self.nav_sections if section.is_default)

    def ordered_sections(self) -> list[NavigationSection]:
        return sorted(self.nav_sections, key=lambda section: section.order)


def load_content_config(path: str | Path) -> ContentConfig:
    """Load and validate the content config, failing fast on any error."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return ContentConfig.model_validate(raw)


_DEFAULT_CONTENT_PATH = Path(__file__).resolve().parent / "content.yaml"


@lru_cache(maxsize=1)
def get_content_config() -> ContentConfig:
    """Load and cache the app's content config from its canonical path (021).

    Pages that need config data outside the initial `app.py` -> `build_shell`
    wiring (e.g. the Periodicity control's label, options and thresholds) call
    this rather than each computing their own path to `content.yaml`. Cached
    so the YAML is parsed and validated once per process, at first use — not
    once per callback invocation — and any config error still fails fast, at
    that first use, rather than being silently swallowed later.
    """
    return load_content_config(_DEFAULT_CONTENT_PATH)
