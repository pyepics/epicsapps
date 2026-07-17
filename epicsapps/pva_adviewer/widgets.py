#!/usr/bin/env python
"""
Reusable custom wx controls shared across pva adviewer panels.
"""

from typing import Callable

import wx
from wxutils import FlatToggleButton, FlatMenuBar

from epicsapps.pva_adviewer.fonts import scaled_font
from epicsapps.pva_adviewer.theme import BG_SURFACE, LIVE_H, LIVE_SCHEME, LIVE_W, BG_BTN_SCHEME

__all__ = ["LiveToggle", "PlotToggleButton"]


class LiveToggle(FlatToggleButton):
    """Vertical LIVE toggle button."""

    def __init__(self, parent: wx.Window, live: bool = False, tooltip: str = "Toggle live updates") -> None:
        super().__init__(parent, label="LIVE", value=live, toggle_scheme=LIVE_SCHEME, size=wx.Size(LIVE_W, LIVE_H))
        if tooltip:
            self.SetToolTip(tooltip)

    def set_live(self, live: bool) -> None:
        self.SetValue(live)

    def set_hovered(self, hovered: bool) -> None:
        if hovered != self._hovered:
            self._hovered = hovered
            self.Refresh()

    def set_toggled_callback(self, cb: Callable[[bool], None]) -> None:
        self.SetAction(lambda _e: cb(self.GetValue()))

    @property
    def is_live(self) -> bool:
        return self.GetValue()

    def _on_paint(self, _: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        w, h = self.GetClientSize()

        gc.SetBrush(wx.Brush(BG_SURFACE))
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.DrawRectangle(0, 0, w, h)

        colour = (self._on_hover if self._hovered else self._on) if self._value else (self._off_hover if self._hovered else self._off)
        gc.SetPen(wx.Pen(colour, 1))
        gc.SetBrush(wx.TRANSPARENT_BRUSH)
        gc.DrawRoundedRectangle(1, 1, w - 2, h - 2, self._corner_radius)

        font = scaled_font(10, weight=wx.FONTWEIGHT_BOLD)
        gc.SetFont(font, colour)
        _, ch_h = gc.GetTextExtent("L")
        y = (h - (4 * ch_h + 6)) / 2
        for ch in "LIVE":
            tw, th = gc.GetTextExtent(ch)
            gc.DrawText(ch, (w - tw) / 2, y)
            y += th + 2


class PlotToggleButton(FlatToggleButton):
    """Square toggle button."""

    def __init__(
        self,
        parent: wx.Window,
        label: str,
        scheme: tuple = None,
        tooltip: str = "",
    ) -> None:
        if scheme is None:
            scheme = BG_BTN_SCHEME
        super().__init__(parent, label=label, toggle_scheme=scheme, size=wx.Size(LIVE_W, LIVE_W))
        if tooltip:
            self.SetToolTip(tooltip)

    def _on_paint(self, _: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        w, h = self.GetClientSize()

        gc.SetBrush(wx.Brush(BG_SURFACE))
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.DrawRectangle(0, 0, w, h)

        colour = (self._on_hover if self._hovered else self._on) if self._value else (self._off_hover if self._hovered else self._off)
        gc.SetPen(wx.Pen(colour, 1))
        gc.SetBrush(wx.TRANSPARENT_BRUSH)
        gc.DrawRoundedRectangle(1, 1, w - 2, h - 2, self._corner_radius)

        font = scaled_font(10, weight=wx.FONTWEIGHT_BOLD)
        gc.SetFont(font, colour)
        tw, th = gc.GetTextExtent(self._label)
        gc.DrawText(self._label, (w - tw) / 2, (h - th) / 2)
