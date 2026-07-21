import math

import pytest

from body_tracking.health.complexion import describe_complexion


def test_rosy_when_red_dominant():
    d = describe_complexion((200.0, 150.0, 150.0))
    assert d["appearance_zh"] == "面色红润"
    assert d["appearance_en"] == "rosy appearance"


def test_pale_when_low_ruddiness_and_bright():
    d = describe_complexion((190.0, 195.0, 195.0))
    assert d["appearance_zh"] == "面色偏白"


def test_dim_when_dark():
    d = describe_complexion((40.0, 38.0, 36.0))
    assert d["appearance_zh"] == "面色偏暗"


def test_caveat_is_non_medical():
    d = describe_complexion((150.0, 140.0, 140.0))
    assert "not a health" in d["caveat"].lower()


# Finding 1: Test for the fourth label (even appearance)
def test_even_when_moderate_ruddiness_and_bright():
    """Assert the even appearance label is never missed in regression."""
    d = describe_complexion((150.0, 140.0, 140.0))
    assert d["appearance_zh"] == "面色均匀"
    assert d["appearance_en"] == "even appearance"


# Finding 2: Input validation tests
def test_input_validation_nan_red():
    """Raise ValueError when red channel is NaN."""
    with pytest.raises(ValueError, match="NaN"):
        describe_complexion((float("nan"), 100.0, 100.0))


def test_input_validation_nan_green():
    """Raise ValueError when green channel is NaN."""
    with pytest.raises(ValueError, match="NaN"):
        describe_complexion((100.0, float("nan"), 100.0))


def test_input_validation_nan_blue():
    """Raise ValueError when blue channel is NaN."""
    with pytest.raises(ValueError, match="NaN"):
        describe_complexion((100.0, 100.0, float("nan")))


def test_input_validation_out_of_range_negative():
    """Raise ValueError when channel is below 0."""
    with pytest.raises(ValueError, match="outside valid range"):
        describe_complexion((-1.0, 100.0, 100.0))


def test_input_validation_out_of_range_above_255():
    """Raise ValueError when channel is above 255."""
    with pytest.raises(ValueError, match="outside valid range"):
        describe_complexion((256.0, 100.0, 100.0))


# Finding 3: Boundary-value tests
def test_brightness_boundary_70_exactly():
    """At brightness=70 (the threshold), should NOT be dim."""
    # brightness = (85 + 70 + 55) / 3 = 70.0 exactly
    # ruddiness = 85 - 70 = 15 (between 8 and 25, so even)
    d = describe_complexion((85.0, 70.0, 55.0))
    assert d["appearance_zh"] == "面色均匀"
    assert d["appearance_en"] == "even appearance"


def test_brightness_boundary_below_70():
    """Just below brightness=70 should be dim."""
    # brightness = (74.97 + 69.97 + 64.97) / 3 = 69.97
    # This is < 70, so should be dim
    d = describe_complexion((74.97, 69.97, 64.97))
    assert d["appearance_zh"] == "面色偏暗"
    assert d["appearance_en"] == "dim appearance"


def test_ruddiness_boundary_25_exactly():
    """At ruddiness=25 (the threshold), should be rosy."""
    # ruddiness = 185 - 160 = 25.0 exactly
    # brightness = (185 + 160 + 160) / 3 = 168.33 >= 70
    d = describe_complexion((185.0, 160.0, 160.0))
    assert d["appearance_zh"] == "面色红润"
    assert d["appearance_en"] == "rosy appearance"


def test_ruddiness_boundary_below_25():
    """Just below ruddiness=25 should not be rosy."""
    # ruddiness = 184.99 - 160 = 24.99
    # brightness = (184.99 + 160 + 160) / 3 = 168.33 >= 70
    # 8 < 24.99 < 25, so should be even
    d = describe_complexion((184.99, 160.0, 160.0))
    assert d["appearance_zh"] == "面色均匀"
    assert d["appearance_en"] == "even appearance"


def test_ruddiness_boundary_8_exactly():
    """At ruddiness=8 (the threshold), should be pale."""
    # ruddiness = 180 - 172 = 8.0 exactly
    # brightness = (180 + 172 + 170) / 3 = 174 >= 70
    d = describe_complexion((180.0, 172.0, 170.0))
    assert d["appearance_zh"] == "面色偏白"
    assert d["appearance_en"] == "pale appearance"


def test_ruddiness_boundary_above_8():
    """Just above ruddiness=8 should not be pale."""
    # ruddiness = 180.01 - 172 = 8.01
    # brightness = (180.01 + 172 + 170) / 3 = 174.0 >= 70
    # 8 < 8.01 < 25, so should be even
    d = describe_complexion((180.01, 172.0, 170.0))
    assert d["appearance_zh"] == "面色均匀"
    assert d["appearance_en"] == "even appearance"
