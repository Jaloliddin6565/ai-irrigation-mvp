"""Sentinel-2 L2A Scene Classification Layer (SCL) mask definition.

SCL class numbers are from the official ESA Sentinel-2 L2A product
specification. This module is the single, explicit, tested place defining
which classes are excluded before any spectral index is aggregated over a
parcel — never buried inside an opaque evalscript string. If the masking
policy needs to change, change `EXCLUDED_SCL_CLASSES` here; the evalscript
template in statistics.py reads it, it does not hardcode its own copy.
"""

from enum import IntEnum


class SclClass(IntEnum):
    NO_DATA = 0
    SATURATED_OR_DEFECTIVE = 1
    DARK_AREA_PIXELS = 2
    CLOUD_SHADOWS = 3
    VEGETATION = 4
    NOT_VEGETATED = 5
    WATER = 6
    UNCLASSIFIED = 7
    CLOUD_MEDIUM_PROBABILITY = 8
    CLOUD_HIGH_PROBABILITY = 9
    THIN_CIRRUS = 10
    SNOW_OR_ICE = 11


# Minimum exclusion set for a parcel-level agronomic index to be trustworthy:
# no data, saturated/defective sensor pixels, cloud shadows, medium/high
# probability cloud, cirrus, and snow/ice. Vegetation/bare-soil/water/
# unclassified pixels are kept — excluding water (SCL 6) too would also be
# defensible for some crops (e.g. flooded rice) but is left to future
# Uzbekistan field validation, not decided here without evidence.
EXCLUDED_SCL_CLASSES: frozenset[SclClass] = frozenset(
    {
        SclClass.NO_DATA,
        SclClass.SATURATED_OR_DEFECTIVE,
        SclClass.CLOUD_SHADOWS,
        SclClass.CLOUD_MEDIUM_PROBABILITY,
        SclClass.CLOUD_HIGH_PROBABILITY,
        SclClass.THIN_CIRRUS,
        SclClass.SNOW_OR_ICE,
    }
)


def is_excluded(scl_value: int) -> bool:
    """True if a raw SCL pixel value should be masked out of statistics."""
    return scl_value in EXCLUDED_SCL_CLASSES


def build_scl_exclusion_js_array() -> str:
    """Render the excluded class list as a JS array literal for the
    evalscript sent to the Statistical API (see statistics.py)."""
    return "[" + ", ".join(str(int(c)) for c in sorted(EXCLUDED_SCL_CLASSES)) + "]"
