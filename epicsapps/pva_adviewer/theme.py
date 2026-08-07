#!/usr/bin/env python
"""
Theme definitions used for the pva adviewer.
"""

import sys
from typing import Optional

import wx
from wxutils import ColorTheme, dark_theme, get_theme, is_dark_theme, light_theme, register_darkdetect, set_theme


class AppTheme:
    """Manages optional per-app ColorTheme overrides, live dark/light switching, and shared UI constants."""

    # Sizes
    icon_size = 20
    btn_w = icon_size + 8
    btn_h = icon_size + 8
    btn_pad = 6
    unit_btn_w = 44
    unit_btn_h = 22
    unit_btn_gap = 4
    bg_btn_w = 30
    live_w = 24
    live_h = 72

    # Unit selector constants
    unit_keys = ["2th_deg", "d_A", "q_A^-1"]
    unit_labels = ["2θ", "d (Å)", "Q (Å⁻¹)"]
    bin_method_labels: tuple = (
        ("none", "None (full resolution)"),
        ("stride", "Stride (fastest)"),
        ("mean", "Mean (anti-aliased)"),
    )

    # Font scaling
    _pt_to_px = {9: 10, 10: 11, 11: 12, 12: 13, 13: 14}
    _win_px_adjust = -2

    def __init__(self, dark: Optional[ColorTheme] = None, light: Optional[ColorTheme] = None) -> None:
        self._dark = dark
        self._light = light

        if self._dark is None and self._light is None:
            return

        self._apply(is_dark_theme())
        register_darkdetect(self._apply)

    def _apply(self, is_dark: bool = True) -> None:
        set_theme((self._dark or dark_theme()) if is_dark else (self._light or light_theme()))

    @staticmethod
    def scaled_font(
        pt: int,
        family: int = wx.FONTFAMILY_DEFAULT,
        style: int = wx.FONTSTYLE_NORMAL,
        weight: int = wx.FONTWEIGHT_NORMAL,
    ) -> wx.Font:
        px = AppTheme._pt_to_px.get(pt, pt)
        if sys.platform == "win32":
            px = max(1, px + AppTheme._win_px_adjust)
        return wx.Font(wx.Size(0, px), family, style, weight)

    @staticmethod
    def btn_font() -> wx.Font:
        return AppTheme.scaled_font(12)
