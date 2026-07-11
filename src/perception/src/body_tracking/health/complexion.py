_CAVEAT = "外观描述，受光线与白平衡影响，非健康指标 / appearance only, lighting-dependent, not a health indicator"

_DIM_BRIGHTNESS = 70.0
_RUDDY_HIGH = 25.0
_RUDDY_LOW = 8.0


def describe_complexion(mean_rgb: tuple[float, float, float]) -> dict[str, str]:
    """
    Describe facial complexion appearance based on mean face-ROI color.

    Args:
        mean_rgb: Tuple of (R, G, B) channel values in range 0..255

    Returns:
        Dictionary with keys:
        - appearance_zh: Chinese appearance label
        - appearance_en: English appearance label
        - caveat: Non-medical disclaimer in bilingual text

    Raises:
        ValueError: If any channel is NaN or outside 0..255 range
    """
    r, g, b = (float(mean_rgb[0]), float(mean_rgb[1]), float(mean_rgb[2]))

    # Validate input ranges
    for channel_val in (r, g, b):
        if channel_val != channel_val:  # NaN check (NaN != NaN is True)
            raise ValueError(f"Channel value is NaN")
        if not (0 <= channel_val <= 255):
            raise ValueError(f"Channel value {channel_val} outside valid range 0..255")

    brightness = (r + g + b) / 3.0
    ruddiness = r - g

    if brightness < _DIM_BRIGHTNESS:
        zh, en = "面色偏暗", "dim appearance"
    elif ruddiness >= _RUDDY_HIGH:
        zh, en = "面色红润", "rosy appearance"
    elif ruddiness <= _RUDDY_LOW:
        zh, en = "面色偏白", "pale appearance"
    else:
        zh, en = "面色均匀", "even appearance"

    return {"appearance_zh": zh, "appearance_en": en, "caveat": _CAVEAT}
