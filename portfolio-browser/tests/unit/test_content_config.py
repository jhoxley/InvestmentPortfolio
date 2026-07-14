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
    config = load_content_config(write_yaml(tmp_path, VALID_YAML))
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
    config = load_content_config(write_yaml(tmp_path, yaml_text))
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
    config = load_content_config(write_yaml(tmp_path, yaml_text))
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
        load_content_config(write_yaml(tmp_path, yaml_text))


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
        load_content_config(write_yaml(tmp_path, yaml_text))


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
        load_content_config(write_yaml(tmp_path, yaml_text))


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
        load_content_config(write_yaml(tmp_path, yaml_text))


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
        load_content_config(write_yaml(tmp_path, yaml_text))


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
