#!/usr/bin/env python
"""
Provides a scaled font utility for wxPython controls.
"""

import sys
import wx

__all__ = ["scaled_font"]

_PT_TO_PX = {9: 10, 10: 11, 11: 12, 12: 13, 13: 14}
_WIN_PX_ADJUST = -2


def scaled_font(
    pt: int,
    family: int = wx.FONTFAMILY_DEFAULT,
    style: int = wx.FONTSTYLE_NORMAL,
    weight: int = wx.FONTWEIGHT_NORMAL,
) -> wx.Font:
    px = _PT_TO_PX.get(pt, pt)
    if sys.platform == "win32":
        px = max(1, px + _WIN_PX_ADJUST)
    return wx.Font(wx.Size(0, px), family, style, weight)

def btn_font() -> wx.Font:
    """Return the standard FlatButton font."""
    return scaled_font(12)
