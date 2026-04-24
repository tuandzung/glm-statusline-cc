#!/usr/bin/env python3
"""Tests for V10: powerline separator fg = prev segment bg."""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from statusline import join_segments, segment, bg_to_fg, THEME_DARK

BG_CWD = THEME_DARK["cwd"]
BG_MODEL = THEME_DARK["model"]
FG = THEME_DARK["fg"]

def test_separator_fg_is_prev_segment_bg():
    """V10: separator between two segments must have fg = prev segment bg color number."""
    seg_a = (segment("A", "text", BG_CWD, FG), BG_CWD)
    seg_b = (segment("B", "text", BG_MODEL, FG), BG_MODEL)
    result = join_segments(seg_a, seg_b)
    sep_idx = result.find("")
    assert sep_idx > 0, "separator not found"
    before_sep = result[:sep_idx]
    assert "\x1b[38;5;111m" in before_sep, f"expected fg=111 (cwd bg), got: {repr(before_sep)}"
    assert "\x1b[48;5;183m" in before_sep, f"expected bg=183 (model bg), got: {repr(before_sep)}"


def test_bg_to_fg():
    """bg_to_fg converts 48;5 to 38;5."""
    assert bg_to_fg("\x1b[48;5;111m") == "\x1b[38;5;111m"
    assert bg_to_fg("\x1b[48;5;22m") == "\x1b[38;5;22m"


def test_trailing_separator_fg():
    """Trailing separator fg should be last segment's bg color."""
    seg = (segment("X", "text", BG_CWD, FG), BG_CWD)
    result = join_segments(seg)
    assert "\x1b[38;5;111m" in result, f"trailing separator missing fg=111, got: {repr(result)}"


if __name__ == "__main__":
    test_bg_to_fg()
    test_separator_fg_is_prev_segment_bg()
    test_trailing_separator_fg()
    print("All V10 tests passed")
