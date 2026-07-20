#!/usr/bin/env python
"""
Reusable custom wx controls shared across pva adviewer panels.
"""

from typing import Callable

import wx
from wxutils import FlatToggleButton, FlatMenuBar

from epicsapps.pva_adviewer.theme import AppTheme, get_theme, register_darkdetect

__all__ = ["LiveToggle", "PlotToggleButton"]


class LiveToggle(FlatToggleButton):
    """Vertical LIVE toggle button."""

    def __init__(self, parent: wx.Window, live: bool = False, tooltip: str = "Toggle live updates") -> None:
        super().__init__(parent, label="LIVE", value=live, size=wx.Size(AppTheme.live_w, AppTheme.live_h))
        if tooltip:
            self.SetToolTip(tooltip)
        register_darkdetect(self._on_theme)

    def _on_theme(self, _is_dark: bool = True) -> None:
        if self:
            wx.CallAfter(self.Refresh)

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
        t = get_theme()

        gc.SetBrush(wx.Brush(t.background))
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.DrawRectangle(0, 0, w, h)

        red = t.red
        if self._value:
            bg = wx.Brush(wx.Colour(red.Red(), red.Green(), red.Blue(), 40))
            border = red
            text_color = red
        elif self._hovered:
            bg = wx.Brush(t.white)
            border = t.white
            text_color = t.foreground
        else:
            bg = wx.TRANSPARENT_BRUSH
            border = t.white
            text_color = t.foreground

        gc.SetPen(wx.Pen(border, 1))
        gc.SetBrush(bg)
        gc.DrawRoundedRectangle(1, 1, w - 2, h - 2, self._corner_radius)

        font = AppTheme.scaled_font(10, weight=wx.FONTWEIGHT_BOLD)
        gc.SetFont(font, text_color)
        _, ch_h = gc.GetTextExtent("L")
        y = (h - (4 * ch_h + 6)) / 2
        for ch in "LIVE":
            tw, th = gc.GetTextExtent(ch)
            gc.DrawText(ch, (w - tw) / 2, y)
            y += th + 2


class PlotToggleButton(FlatToggleButton):
    """Square toggle button."""

    def __init__(self, parent: wx.Window, label: str, tooltip: str = "") -> None:
        super().__init__(parent, label=label, size=wx.Size(AppTheme.live_w, AppTheme.live_w))
        if tooltip:
            self.SetToolTip(tooltip)
        register_darkdetect(self._on_theme)

    def set_hovered(self, hovered: bool) -> None:
        if hovered != self._hovered:
            self._hovered = hovered
            self.Refresh()

    def _on_theme(self, _is_dark: bool = True) -> None:
        if self:
            wx.CallAfter(self.Refresh)

    def _on_paint(self, _: wx.PaintEvent) -> None:
        dc = wx.AutoBufferedPaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        w, h = self.GetClientSize()
        t = get_theme()

        gc.SetBrush(wx.Brush(t.background))
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.DrawRectangle(0, 0, w, h)

        green = t.green
        if self._value:
            bg = wx.Brush(wx.Colour(green.Red(), green.Green(), green.Blue(), 40))
            border = green
            text_color = green
        elif self._hovered:
            bg = wx.Brush(t.white)
            border = t.white
            text_color = t.foreground
        else:
            bg = wx.TRANSPARENT_BRUSH
            border = t.white
            text_color = t.foreground

        gc.SetPen(wx.Pen(border, 1))
        gc.SetBrush(bg)
        gc.DrawRoundedRectangle(1, 1, w - 2, h - 2, self._corner_radius)

        font = AppTheme.scaled_font(10, weight=wx.FONTWEIGHT_BOLD)
        gc.SetFont(font, text_color)
        tw, th = gc.GetTextExtent(self._label)
        gc.DrawText(self._label, (w - tw) / 2, (h - th) / 2)
