"""Domain enums shared by ORM models and Pydantic schemas.

Values are kept in sync with the keys used in backend/config/*.yaml
(crop_type <-> crops.yaml, soil_texture <-> soils.yaml, irrigation_method
<-> irrigation_methods.yaml) so a Field's selections map directly onto the
agronomic config without a translation layer.
"""

from enum import StrEnum


class PreferredLanguage(StrEnum):
    UZ = "uz"
    RU = "ru"
    EN = "en"


class CropType(StrEnum):
    COTTON = "cotton"
    WHEAT = "wheat"
    ORCHARD = "orchard"
    VINEYARD = "vineyard"
    VEGETABLES = "vegetables"


class SoilTexture(StrEnum):
    SAND = "sand"
    SANDY_LOAM = "sandy_loam"
    LOAM = "loam"
    CLAY_LOAM = "clay_loam"
    CLAY = "clay"
    UNKNOWN = "unknown"


class IrrigationMethod(StrEnum):
    DRIP = "drip"
    SPRINKLER = "sprinkler"
    FURROW = "furrow"
    BASIN = "basin"
    UNKNOWN = "unknown"


class CropStage(StrEnum):
    INITIAL = "initial"
    DEVELOPMENT = "development"
    MID = "mid"
    LATE = "late"


class QualitativeAmount(StrEnum):
    LITTLE = "little"
    MODERATE = "moderate"
    A_LOT = "a_lot"


class ValueSource(StrEnum):
    MEASURED = "measured"
    FARMER_ESTIMATE = "farmer_estimate"


class AnalysisDataMode(StrEnum):
    FIXTURE = "fixture"
    LIVE = "live"
