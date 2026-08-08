"""Loader for the bootstrap Uzbekistan sampling locations
(backend/config/ai_bootstrap_locations.yaml) used only by
backend/scripts/train_ai_soil_moisture.py.

These are representative bootstrap coordinates used to create an open-data
pre-calibration dataset — not field sensor observations. See the YAML
file's header for the full rationale and the train/test split discipline.
"""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict


class BootstrapLocation(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    region_uz: str
    label_uz: str
    latitude: float
    longitude: float
    split: Literal["train", "test"]


class BootstrapLocationsConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    methodology_version: str
    locations: list[BootstrapLocation]

    @property
    def train_locations(self) -> list[BootstrapLocation]:
        return [loc for loc in self.locations if loc.split == "train"]

    @property
    def test_locations(self) -> list[BootstrapLocation]:
        return [loc for loc in self.locations if loc.split == "test"]


def load_bootstrap_locations(path: Path) -> BootstrapLocationsConfig:
    with path.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return BootstrapLocationsConfig.model_validate(raw)
