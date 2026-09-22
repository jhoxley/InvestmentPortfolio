from pathlib import Path

import pytest

from config.content import load_content_config

VALID_YAML = """
app_name: "Investment Portfolio Browser"
build_info:
  version: "0.1.0"
  published_date: "2026-07-13"
nav_sections:
  - key: overview
    label: Overview
    order: 1
    is_default: true
  - key: positions
    label: Positions
    order: 2
  - key: performance
    label: Performance
    order: 3
  - key: income
    label: Income
    order: 4
"""


def write_yaml(tmp_path: Path, text: str) -> Path:
    config_path = tmp_path / "content.yaml"
    config_path.write_text(text, encoding="utf-8")
    return config_path


def test_valid_config_loads(tmp_path: Path) -> None:
    # PERIODICITY_YAML is defined lower in this module (021); a fully valid
    # config requires it, since the periodicity section is mandatory.
    config = load_content_config(write_yaml(tmp_path, VALID_YAML + PERIODICITY_YAML))
    assert config.app_name == "Investment Portfolio Browser"
    assert config.build_info.version == "0.1.0"
    assert config.build_info.published_date == "2026-07-13"
    assert len(config.nav_sections) == 4
    assert config.default_section().key == "overview"


def test_missing_version_and_date_fall_back_to_unknown(tmp_path: Path) -> None:
    yaml_text = """
app_name: "Investment Portfolio Browser"
build_info: {}
nav_sections:
  - key: overview
    label: Overview
    order: 1
    is_default: true
"""
    config = load_content_config(write_yaml(tmp_path, yaml_text + PERIODICITY_YAML))
    assert config.build_info.version == "unknown"
    assert config.build_info.published_date == "unknown"


def test_null_version_normalizes_to_unknown(tmp_path: Path) -> None:
    yaml_text = """
app_name: "Investment Portfolio Browser"
build_info:
  version: null
  published_date: null
nav_sections:
  - key: overview
    label: Overview
    order: 1
    is_default: true
"""
    config = load_content_config(write_yaml(tmp_path, yaml_text + PERIODICITY_YAML))
    assert config.build_info.version == "unknown"
    assert config.build_info.published_date == "unknown"


def test_empty_nav_sections_raises(tmp_path: Path) -> None:
    yaml_text = """
app_name: "Investment Portfolio Browser"
build_info:
  version: "0.1.0"
  published_date: "2026-07-13"
nav_sections: []
"""
    with pytest.raises(ValueError, match="at least one"):
        load_content_config(write_yaml(tmp_path, yaml_text + PERIODICITY_YAML))


def test_zero_default_sections_raises(tmp_path: Path) -> None:
    yaml_text = """
app_name: "Investment Portfolio Browser"
build_info:
  version: "0.1.0"
  published_date: "2026-07-13"
nav_sections:
  - key: overview
    label: Overview
    order: 1
  - key: positions
    label: Positions
    order: 2
"""
    with pytest.raises(ValueError, match="exactly one"):
        load_content_config(write_yaml(tmp_path, yaml_text + PERIODICITY_YAML))


def test_two_default_sections_raises(tmp_path: Path) -> None:
    yaml_text = """
app_name: "Investment Portfolio Browser"
build_info:
  version: "0.1.0"
  published_date: "2026-07-13"
nav_sections:
  - key: overview
    label: Overview
    order: 1
    is_default: true
  - key: positions
    label: Positions
    order: 2
    is_default: true
"""
    with pytest.raises(ValueError, match="exactly one"):
        load_content_config(write_yaml(tmp_path, yaml_text + PERIODICITY_YAML))


def test_duplicate_key_raises(tmp_path: Path) -> None:
    yaml_text = """
app_name: "Investment Portfolio Browser"
build_info:
  version: "0.1.0"
  published_date: "2026-07-13"
nav_sections:
  - key: overview
    label: Overview
    order: 1
    is_default: true
  - key: overview
    label: Overview Duplicate
    order: 2
"""
    with pytest.raises(ValueError, match="unique"):
        load_content_config(write_yaml(tmp_path, yaml_text + PERIODICITY_YAML))


def test_duplicate_order_raises(tmp_path: Path) -> None:
    yaml_text = """
app_name: "Investment Portfolio Browser"
build_info:
  version: "0.1.0"
  published_date: "2026-07-13"
nav_sections:
  - key: overview
    label: Overview
    order: 1
    is_default: true
  - key: positions
    label: Positions
    order: 1
"""
    with pytest.raises(ValueError, match="unique"):
        load_content_config(write_yaml(tmp_path, yaml_text + PERIODICITY_YAML))


def test_real_content_yaml_loads() -> None:
    real_path = Path(__file__).resolve().parents[2] / "config" / "content.yaml"
    config = load_content_config(real_path)
    assert config.default_section().key == "overview"
    assert {section.key for section in config.nav_sections} == {
        "overview",
        "positions",
        "performance",
        "income",
    }


# --- periodicity section (021) --------------------------------------------

PERIODICITY_YAML = """
periodicity:
  label: "Periodicity"
  options:
    - { key: day,     label: day,     value: day }
    - { key: week,    label: week,    value: week }
    - { key: month,   label: month,   value: month }
    - { key: quarter, label: quarter, value: quarter }
    - { key: year,    label: year,    value: annual }
  thresholds:
    day_max_years: 1
    month_max_years: 3
    quarter_max_years: 5
"""


def _with_periodicity(body: str) -> str:
    """Append a periodicity section to the otherwise-valid base config."""
    return VALID_YAML + body


def test_valid_periodicity_section_loads(tmp_path: Path) -> None:
    config = load_content_config(write_yaml(tmp_path, _with_periodicity(PERIODICITY_YAML)))

    assert config.periodicity.label == "Periodicity"
    assert [o.key for o in config.periodicity.options] == [
        "day",
        "week",
        "month",
        "quarter",
        "year",
    ]
    assert config.periodicity.thresholds.day_max_years == 1
    assert config.periodicity.thresholds.month_max_years == 3
    assert config.periodicity.thresholds.quarter_max_years == 5


def test_year_option_maps_to_the_services_annual_value(tmp_path: Path) -> None:
    """The one place the UI's vocabulary and the service's diverge (FR-003)."""
    config = load_content_config(write_yaml(tmp_path, _with_periodicity(PERIODICITY_YAML)))

    by_key = {o.key: o for o in config.periodicity.options}
    assert by_key["year"].label == "year"
    assert by_key["year"].value == "annual"
    for key in ("day", "week", "month", "quarter"):
        assert by_key[key].value == key


def test_value_for_key_resolves_the_service_side_value(tmp_path: Path) -> None:
    config = load_content_config(write_yaml(tmp_path, _with_periodicity(PERIODICITY_YAML)))

    assert config.periodicity.value_for_key("year") == "annual"
    assert config.periodicity.value_for_key("month") == "month"


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        (
            PERIODICITY_YAML.replace("    - { key: year,    label: year,    value: annual }\n", ""),
            "only four options",
        ),
        (
            PERIODICITY_YAML.replace(
                "  thresholds:",
                "    - { key: decade,  label: decade,  value: decade }\n  thresholds:",
            ),
            "six options",
        ),
        (
            PERIODICITY_YAML.replace(
                "- { key: week,    label: week,    value: week }",
                "- { key: day,     label: weekly,  value: week }",
            ),
            "duplicate key",
        ),
        (
            PERIODICITY_YAML.replace(
                "- { key: week,    label: week,    value: week }",
                "- { key: week,    label: day,     value: week }",
            ),
            "duplicate label",
        ),
        (
            PERIODICITY_YAML.replace(
                "- { key: week,    label: week,    value: week }",
                "- { key: week,    label: week,    value: day }",
            ),
            "duplicate value",
        ),
        (
            PERIODICITY_YAML.replace("month_max_years: 3", "month_max_years: 1"),
            "thresholds not strictly ascending",
        ),
        (
            PERIODICITY_YAML.replace("day_max_years: 1", "day_max_years: 0"),
            "non-positive threshold",
        ),
        (
            PERIODICITY_YAML.replace(
                "- { key: quarter, label: quarter, value: quarter }",
                "- { key: fortnight, label: fortnight, value: week }",
            ),
            "a derivable interval missing from options",
        ),
    ],
)
def test_invalid_periodicity_section_is_rejected(
    tmp_path: Path, mutation: str, reason: str
) -> None:
    """Every malformed shape must fail fast at load (Principle IV)."""
    with pytest.raises(ValueError):
        load_content_config(write_yaml(tmp_path, _with_periodicity(mutation)))


def test_missing_periodicity_section_is_rejected(tmp_path: Path) -> None:
    """The section is mandatory — a config without it must fail fast, not default."""
    with pytest.raises(ValueError):
        load_content_config(write_yaml(tmp_path, VALID_YAML))
