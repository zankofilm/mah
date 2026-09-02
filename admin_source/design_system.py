# -*- coding: utf-8 -*-
"""Design tokens and responsive rules for the Javanrood desktop UI.

The module intentionally contains no application state.  All visual dimensions are
resolved from the active window/screen so the same source remains readable on
1366x768, Full-HD, 2K and 4K displays.
"""

from __future__ import annotations

from dataclasses import dataclass

PROFILE_COMPACT = "compact"
PROFILE_COMFORTABLE = "comfortable"
PROFILE_SPACIOUS = "spacious"

COMPACT_MAX_WIDTH = 1199
SPACIOUS_MIN_WIDTH = 1800


@dataclass(frozen=True)
class UiMetrics:
    profile: str
    base_font_pt: float
    caption_font_pt: float
    title_font_pt: float
    hero_font_pt: float
    icon_small: int
    icon_normal: int
    icon_large: int
    control_height: int
    nav_height: int
    radius: int
    gap: int
    page_margin: int
    table_row_height: int


PROFILES = {
    PROFILE_COMPACT: UiMetrics(
        PROFILE_COMPACT, 10.0, 9.0, 13.0, 19.0,
        15, 18, 24, 36, 48, 9, 8, 12, 36,
    ),
    PROFILE_COMFORTABLE: UiMetrics(
        PROFILE_COMFORTABLE, 10.5, 9.5, 14.0, 22.0,
        16, 20, 26, 40, 52, 11, 10, 18, 40,
    ),
    PROFILE_SPACIOUS: UiMetrics(
        PROFILE_SPACIOUS, 11.0, 10.0, 15.0, 24.0,
        18, 22, 30, 44, 56, 12, 12, 22, 44,
    ),
}


def profile_for_width(width: int) -> str:
    width = int(width or 0)
    if width <= COMPACT_MAX_WIDTH:
        return PROFILE_COMPACT
    if width >= SPACIOUS_MIN_WIDTH:
        return PROFILE_SPACIOUS
    return PROFILE_COMFORTABLE


def metrics_for_width(width: int) -> UiMetrics:
    return PROFILES[profile_for_width(width)]


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def density_scale(logical_dpi: float | None) -> float:
    """A conservative scale for fixed-size SVG controls.

    Qt already scales point fonts and logical pixels when High-DPI mode is on; this
    small correction only covers unusual Windows scaling configurations and is
    deliberately capped to avoid double scaling.
    """
    try:
        dpi = float(logical_dpi or 96.0)
    except (TypeError, ValueError):
        dpi = 96.0
    return float(clamp(dpi / 96.0, 0.95, 1.20))


def scaled(value: int | float, logical_dpi: float | None = None) -> int:
    return max(1, int(round(float(value) * density_scale(logical_dpi))))


# Central palette.  Theme files consume these values instead of defining random
# shades per screen.
PALETTE = {
    "navy_950": "#06182f",
    "navy_900": "#08244a",
    "navy_800": "#0c3367",
    "navy_700": "#174c8b",
    "blue_600": "#2878d4",
    "blue_100": "#eaf2fb",
    "surface": "#ffffff",
    "canvas": "#eef3f8",
    "text": "#17243a",
    "muted": "#66758a",
    "border": "#dfe7f0",
    "success": "#23815a",
    "warning": "#d7861d",
    "danger": "#c43d4b",
    "gold": "#c49a3a",
}
