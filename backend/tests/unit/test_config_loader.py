from pathlib import Path

import pytest

from app.domain.config_loader import load_agronomic_config
from app.settings import CONFIG_DIR


def test_load_agronomic_config_valid() -> None:
    config = load_agronomic_config(CONFIG_DIR)

    assert config.crops.methodology_version == "0.1.0"
    assert "cotton" in config.crops.crops
    assert config.soils.soils["clay"].field_capacity > config.soils.soils["sand"].field_capacity
    assert config.irrigation_methods.irrigation_methods["drip"].efficiency > (
        config.irrigation_methods.irrigation_methods["furrow"].efficiency
    )
    assert config.confidence_weights.thresholds.high > config.confidence_weights.thresholds.medium


def test_load_agronomic_config_missing_directory_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_agronomic_config(tmp_path)
