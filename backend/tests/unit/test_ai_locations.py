from pathlib import Path

import pytest
from pydantic import ValidationError

from app.ai.locations import load_bootstrap_locations
from app.settings import CONFIG_DIR

LOCATIONS_PATH = CONFIG_DIR / "ai_bootstrap_locations.yaml"


def test_committed_locations_file_loads_and_covers_multiple_regions() -> None:
    config = load_bootstrap_locations(LOCATIONS_PATH)

    assert 10 <= len(config.locations) <= 15
    assert len({loc.region_uz for loc in config.locations}) >= 8


def test_committed_locations_have_unique_ids() -> None:
    config = load_bootstrap_locations(LOCATIONS_PATH)

    ids = [loc.id for loc in config.locations]
    assert len(ids) == len(set(ids))


def test_committed_locations_have_both_train_and_test_split() -> None:
    config = load_bootstrap_locations(LOCATIONS_PATH)

    assert len(config.train_locations) > 0
    assert len(config.test_locations) > 0
    assert len(config.train_locations) + len(config.test_locations) == len(config.locations)


def test_committed_locations_are_within_uzbekistan_bounding_box() -> None:
    config = load_bootstrap_locations(LOCATIONS_PATH)

    for loc in config.locations:
        assert 37.0 <= loc.latitude <= 46.0
        assert 55.0 <= loc.longitude <= 74.0


def test_load_bootstrap_locations_rejects_invalid_split(tmp_path: Path) -> None:
    bad_file = tmp_path / "bad.yaml"
    bad_file.write_text(
        "methodology_version: '0.1.0'\n"
        "locations:\n"
        "  - id: x\n"
        "    region_uz: r\n"
        "    label_uz: l\n"
        "    latitude: 41.0\n"
        "    longitude: 69.0\n"
        "    split: not_a_real_split\n",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        load_bootstrap_locations(bad_file)
