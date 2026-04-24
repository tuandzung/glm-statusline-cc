#!/usr/bin/env python3
"""Tests for V12: context bg must be Catppuccin accent (same color number as bar fill)."""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from statusline import THEME_DARK, THEME_LIGHT

# Catppuccin Macchiato accent 256-color codes (from §S)
MACCHIATO_ACCENT = {"green": 150, "yellow": 223, "red": 210}
# Catppuccin Latte accent 256-color codes
LATTE_ACCENT = {"green": 70, "yellow": 172, "red": 161}


def _color_number(escape):
    """Extract 256-color number from ANSI escape code."""
    m = re.search(r"(\d{2,3})m$", escape)
    return int(m.group(1)) if m else -1


def test_dark_ctx_bg_is_catppuccin_accent():
    """V12: dark ctx_bg color numbers must match Catppuccin Macchiato accent codes."""
    for color, expected in MACCHIATO_ACCENT.items():
        actual = _color_number(THEME_DARK["ctx_bg"][color])
        assert actual == expected, f"dark ctx_bg.{color}: {actual} != expected {expected}"


def test_light_ctx_bg_is_catppuccin_accent():
    """V12: light ctx_bg color numbers must match Catppuccin Latte accent codes."""
    for color, expected in LATTE_ACCENT.items():
        actual = _color_number(THEME_LIGHT["ctx_bg"][color])
        assert actual == expected, f"light ctx_bg.{color}: {actual} != expected {expected}"


def test_dark_bar_base_and_surface():
    """V12: dark bar filled=Base(17), empty=Surface2(60)."""
    assert _color_number(THEME_DARK["bar"]["filled"]) == 17
    assert _color_number(THEME_DARK["bar"]["empty"]) == 60


def test_light_bar_base_and_surface():
    """V12: light bar filled=Base(231), empty=Surface2(146)."""
    assert _color_number(THEME_LIGHT["bar"]["filled"]) == 231
    assert _color_number(THEME_LIGHT["bar"]["empty"]) == 146


def test_dark_ctx_bg_equals_bar_accent():
    """V12: dark ctx_bg numbers == Macchiato accent numbers (same palette)."""
    for color, num in MACCHIATO_ACCENT.items():
        assert _color_number(THEME_DARK["ctx_bg"][color]) == num


def test_light_ctx_bg_equals_bar_accent():
    """V12: light ctx_bg numbers == Latte accent numbers (same palette)."""
    for color, num in LATTE_ACCENT.items():
        assert _color_number(THEME_LIGHT["ctx_bg"][color]) == num


if __name__ == "__main__":
    test_dark_ctx_bg_is_catppuccin_accent()
    test_light_ctx_bg_is_catppuccin_accent()
    test_dark_bar_base_and_surface()
    test_light_bar_base_and_surface()
    test_dark_ctx_bg_equals_bar_accent()
    test_light_ctx_bg_equals_bar_accent()
    print("All V12 tests passed")
