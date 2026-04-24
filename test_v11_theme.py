#!/usr/bin/env python3
"""Tests for V11: theme resolution."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from statusline import resolve_theme, THEME_DARK, THEME_LIGHT


def test_default_dark():
    """V11: missing env → dark theme."""
    os.environ.pop("STATUSLINE_THEME", None)
    assert resolve_theme() is THEME_DARK


def test_explicit_dark():
    """V11: STATUSLINE_THEME=dark → dark theme."""
    os.environ["STATUSLINE_THEME"] = "dark"
    assert resolve_theme() is THEME_DARK


def test_explicit_light():
    """V11: STATUSLINE_THEME=light → light theme."""
    os.environ["STATUSLINE_THEME"] = "light"
    assert resolve_theme() is THEME_LIGHT


def test_case_insensitive():
    """V11: STATUSLINE_THEME case insensitive."""
    os.environ["STATUSLINE_THEME"] = "LIGHT"
    assert resolve_theme() is THEME_LIGHT


def test_invalid_falls_back_dark():
    """V11: invalid value → dark."""
    os.environ["STATUSLINE_THEME"] = "garbage"
    assert resolve_theme() is THEME_DARK


def test_whitespace_trimmed():
    """V11: whitespace trimmed."""
    os.environ["STATUSLINE_THEME"] = "  light  "
    assert resolve_theme() is THEME_LIGHT


def test_light_has_different_cwd():
    """Light theme cwd color differs from dark."""
    assert THEME_LIGHT["cwd"] != THEME_DARK["cwd"]


def test_light_has_different_fg():
    """Light theme fg color differs from dark."""
    assert THEME_LIGHT["fg"] != THEME_DARK["fg"]


if __name__ == "__main__":
    test_default_dark()
    test_explicit_dark()
    test_explicit_light()
    test_case_insensitive()
    test_invalid_falls_back_dark()
    test_whitespace_trimmed()
    test_light_has_different_cwd()
    test_light_has_different_fg()
    print("All V11 tests passed")
