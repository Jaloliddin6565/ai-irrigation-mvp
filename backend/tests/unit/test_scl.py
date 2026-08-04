from app.providers.satellite.scl import (
    EXCLUDED_SCL_CLASSES,
    SclClass,
    build_scl_exclusion_js_array,
    is_excluded,
)


def test_minimum_required_classes_are_excluded() -> None:
    required = {
        SclClass.NO_DATA,
        SclClass.SATURATED_OR_DEFECTIVE,
        SclClass.CLOUD_SHADOWS,
        SclClass.CLOUD_MEDIUM_PROBABILITY,
        SclClass.CLOUD_HIGH_PROBABILITY,
        SclClass.THIN_CIRRUS,
        SclClass.SNOW_OR_ICE,
    }
    assert required <= EXCLUDED_SCL_CLASSES


def test_vegetation_and_bare_soil_are_kept() -> None:
    assert SclClass.VEGETATION not in EXCLUDED_SCL_CLASSES
    assert SclClass.NOT_VEGETATED not in EXCLUDED_SCL_CLASSES
    assert SclClass.UNCLASSIFIED not in EXCLUDED_SCL_CLASSES


def test_is_excluded_matches_membership() -> None:
    assert is_excluded(int(SclClass.CLOUD_HIGH_PROBABILITY)) is True
    assert is_excluded(int(SclClass.VEGETATION)) is False


def test_js_array_contains_exactly_the_excluded_class_numbers_sorted() -> None:
    js = build_scl_exclusion_js_array()
    assert js.startswith("[") and js.endswith("]")
    numbers = [int(x.strip()) for x in js.strip("[]").split(",")]
    assert set(numbers) == {int(c) for c in EXCLUDED_SCL_CLASSES}
    assert numbers == sorted(numbers)
