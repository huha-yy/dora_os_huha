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
