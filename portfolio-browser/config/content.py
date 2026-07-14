"""Typed, fail-fast loader for the app's static content configuration.

Holds non-secret, human-edited values (app name, build info, nav section
labels) that must never be hardcoded as string literals in application code
(project constitution, Principle IV).
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, field_validator, model_validator

_UNKNOWN = "unknown"


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


class ContentConfig(BaseModel):
    app_name: str
    build_info: BuildInfo = BuildInfo()
    nav_sections: list[NavigationSection]

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
