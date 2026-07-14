#!/usr/bin/env python
"""
1D azimuthal integration profile plot. Extends wxmplot.LinePlot with PONI overlay, unit buttons, and LiveToggle.
"""

from typing import Callable

import wx
from wxmplot import LinePlot
from wxutils import get_color, draw_folder

from epicsapps.pva_adviewer.theme import LIVE_H, LIVE_W, PONI_LOADED, PONI_MISSING, ICON_SIZE, UNIT_BTN_W, UNIT_BTN_H, UNIT_BTN_GAP
from epicsapps.pva_adviewer.widgets import LiveToggle
from epicsapps.pva_adviewer.fonts import scaled_font, UNIT_KEYS, UNIT_LABELS

__all__ = ["IntegrationPlot"]


class IntegrationPlot(LinePlot):
    """Azimuthal integration profile plot with PONI overlay and unit buttons."""

    _BTN_W = ICON_SIZE + 8
    _BTN_H = ICON_SIZE + 8
    _BTN_PAD = 6

    def __init__(self, parent: wx.Window) -> None:
        """Initialise the IntegrationPlot."""
        super().__init__(parent)

        self._poni_text: str = "No calibration loaded"
        self._poni_colour: wx.Colour = PONI_MISSING
        self._load_poni_cb: Callable[[], None] | None = None
        self._calibrated: bool = False

        self._active_unit: str = UNIT_KEYS[0]
        self._unit_changed_cb: Callable[[str], None] | None = None
        self._unit_btn_rects: list[wx.Rect] = []
        self.UNIT_BTN_Hovered: int = -1
        self._unit_btn_pressed: int = -1

        self._btn_hovered: bool = False
        self._btn_pressed: bool = False
        self._btn_rect: wx.Rect = wx.Rect(0, 0, 0, 0)

        self._live_toggle = LiveToggle(self, live=False, tooltip="Toggle live ROI integration")
        self._live_toggle.Hide()

        self.Bind(wx.EVT_MOTION, self._on_integration_mouse_move)
        self.Bind(wx.EVT_LEFT_DOWN, self._on_integration_mouse_down)
        self.Bind(wx.EVT_LEFT_UP, self._on_integration_mouse_up)

        wx.CallAfter(self._reposition_children)

    def set_poni_info(self, text: str, success: bool) -> None:
        """Update the PONI calibration status text and colour."""
        self._poni_text = text
        self._poni_colour = PONI_LOADED if success else PONI_MISSING
        self.Refresh()

    def set_load_poni_callback(self, callback: Callable[[], None]) -> None:
        """Register a callback to invoke when the load-PONI button is clicked."""
        self._load_poni_cb = callback

    def set_unit_changed_callback(self, callback: Callable[[str], None]) -> None:
        """Register a callback fired with the new unit key when the user switches units."""
        self._unit_changed_cb = callback

    def set_live_integration_callback(self, callback: Callable[[bool], None]) -> None:
        """Register a callback fired with the live toggle state."""
        self._live_toggle.set_toggled_callback(callback)

    def set_calibrated(self, calibrated: bool) -> None:
        """Show or hide the unit buttons and live toggle based on calibration state."""
        self._calibrated = calibrated
        if calibrated:
            self._live_toggle.Show()
        else:
            self._live_toggle.set_live(False)
            self._live_toggle.Hide()
        self._reposition_children()
        self.Refresh()

    def set_active_unit(self, unit: str) -> None:
        """Set the active unit button by key."""
        if unit in UNIT_KEYS:
            self._active_unit = unit
            self.Refresh()

    @property
    def is_live_integration(self) -> bool:
        """Whether live ROI integration is currently active."""
        return self._live_toggle.is_live

    def format_hover_info(self, x: float, y: float) -> str:
        """Return hover info using the active unit label."""
        return f"{self._x_label}: {x:.4g}   I: {y:.4g}"

    def draw_overlays(self, gc: wx.GraphicsContext, W: int, H: int) -> None:
        """Draw the PONI overlay and, when calibrated, the unit buttons."""
        self._draw_poni_overlay(gc, W, H)
        if self._calibrated:
            self._draw_unit_buttons(gc, W, H)

    def _reposition_children(self) -> None:
        """Reposition the VisPy canvas and live toggle within the panel."""
        self._reposition_canvas()
        W, H = self.GetSize()
        x = W - LIVE_W - self._BTN_PAD
        y = self._mt + max(0, (H - self._mt - self._mb - LIVE_H) // 2)
        self._live_toggle.SetPosition(wx.Point(x, y))
        self._live_toggle.Raise()

    def _btn_rect_for(self, W: int, H: int) -> wx.Rect:
        """Return the bounding rect of the load-PONI button."""
        return wx.Rect(W - self._BTN_W - self._BTN_PAD, H - self._BTN_H - self._BTN_PAD, self._BTN_W, self._BTN_H)

    def _unit_btn_at(self, pt: wx.Point) -> int:
        """Return the index of the unit button under pt, or -1."""
        for i, r in enumerate(self._unit_btn_rects):
            if r.Contains(pt):
                return i
        return -1

    def _on_integration_mouse_move(self, event: wx.MouseEvent) -> None:
        """Update button hover state in addition to base hover logic."""
        pt = event.GetPosition()
        W, H = self.GetSize()
        inside_btn = self._btn_rect_for(W, H).Contains(pt)
        if inside_btn != self._btn_hovered:
            self._btn_hovered = inside_btn
            self.Refresh()
        if self._calibrated:
            idx = self._unit_btn_at(pt)
            if idx != self.UNIT_BTN_Hovered:
                self.UNIT_BTN_Hovered = idx
                self.Refresh()
        event.Skip()

    def _on_integration_mouse_down(self, event: wx.MouseEvent) -> None:
        """Handle clicks on the PONI button and unit buttons."""
        pt = event.GetPosition()
        W, H = self.GetSize()
        if self._btn_rect_for(W, H).Contains(pt):
            self._btn_pressed = True
            self.Refresh()
            event.Skip()
            return
        if self._calibrated:
            idx = self._unit_btn_at(pt)
            if idx != -1:
                self._unit_btn_pressed = idx
                self.Refresh()
                event.Skip()
                return
        event.Skip()

    def _on_integration_mouse_up(self, event: wx.MouseEvent) -> None:
        """Fire PONI or unit callbacks on button release."""
        pt = event.GetPosition()
        W, H = self.GetSize()
        was_btn = self._btn_pressed
        was_unit = self._unit_btn_pressed
        self._btn_pressed = False
        self._unit_btn_pressed = -1
        self.Refresh()
        if was_btn and self._btn_rect_for(W, H).Contains(pt) and self._load_poni_cb is not None:
            self._load_poni_cb()
        if was_unit != -1 and self._unit_btn_at(pt) == was_unit:
            self._active_unit = UNIT_KEYS[was_unit]
            if self._unit_changed_cb is not None:
                self._unit_changed_cb(self._active_unit)
        event.Skip()

    def _draw_unit_buttons(self, gc: wx.GraphicsContext, W: int, H: int) -> None:
        """Paint the 2θ / d / Q unit selector buttons."""
        active_green = wx.Colour(72, 199, 116)
        fg = get_color("text")
        bg = get_color("button_bg")
        bg_hover = get_color("highight")
        bg_active = get_color("nb_active")
        border = get_color("graytext")
        border_active = active_green

        total_w = len(UNIT_KEYS) * UNIT_BTN_W + (len(UNIT_KEYS) - 1) * UNIT_BTN_GAP
        start_x = W - self._mr - total_w
        self._unit_btn_rects = []
        font = scaled_font(9, weight=wx.FONTWEIGHT_BOLD)
        for i, (key, label) in enumerate(zip(UNIT_KEYS, UNIT_LABELS)):
            x = start_x + i * (UNIT_BTN_W + UNIT_BTN_GAP)
            r = wx.Rect(x, 2, UNIT_BTN_W, UNIT_BTN_H)
            self._unit_btn_rects.append(r)
            active = key == self._active_unit
            if i == self._unit_btn_pressed:
                b, brd, f = get_color("hotlight"), border_active if active else border, active_green if active else fg
            elif active:
                b, brd, f = bg_active, border_active, active_green
            elif i == self.UNIT_BTN_Hovered:
                b, brd, f = bg_hover, border, fg
            else:
                b, brd, f = bg, border, fg
            gc.SetBrush(wx.Brush(b))
            gc.SetPen(wx.Pen(brd, 1))
            gc.DrawRoundedRectangle(r.x, r.y, r.width, r.height, 3)
            gc.SetFont(font, f)
            tw, th = gc.GetTextExtent(label)
            gc.DrawText(label, r.x + (r.width - tw) / 2, r.y + (r.height - th) / 2)

    def _draw_poni_overlay(self, gc: wx.GraphicsContext, W: int, H: int) -> None:
        """Paint the load-PONI button, calibration status text, and hover/max info."""
        btn_bg = get_color("button_bg")
        btn_hover = get_color("highight")
        btn_press = get_color("hotlight")
        active_green = wx.Colour(72, 199, 116)

        br = self._btn_rect_for(W, H)
        self._btn_rect = br
        bg = btn_press if self._btn_pressed else (btn_hover if self._btn_hovered else btn_bg)
        gc.SetBrush(wx.Brush(bg))
        gc.SetPen(wx.TRANSPARENT_PEN)
        gc.DrawRoundedRectangle(br.x, br.y, br.width, br.height, 4)
        gc.SetAntialiasMode(wx.ANTIALIAS_DEFAULT)
        off = (br.width - ICON_SIZE) / 2
        gc.PushState()
        gc.Translate(br.x + off, br.y + off)
        draw_folder(gc, ICON_SIZE)
        gc.PopState()

        font = scaled_font(11, style=wx.FONTSTYLE_ITALIC)
        gc.SetFont(font, self._poni_colour)
        tw, th = gc.GetTextExtent(self._poni_text)
        gc.DrawText(self._poni_text, br.x - tw - self._BTN_PAD, br.y + (br.height - th) / 2)

        info_font = scaled_font(11, weight=wx.FONTWEIGHT_BOLD)
        gc.SetFont(info_font, active_green)
        x = self._BTN_PAD
        if self.ys is not None:
            lbl = f"max: {float(self.ys.max()):.4g}"
            lw, lh = gc.GetTextExtent(lbl)
            gc.DrawText(lbl, x, br.y + (br.height - lh) / 2)
            x += lw + 16
        if self._hover_data_x is not None and self._hover_data_y is not None:
            coord = self.format_hover_info(self._hover_data_x, self._hover_data_y)
            _, ch = gc.GetTextExtent(coord)
            gc.DrawText(coord, x, br.y + (br.height - ch) / 2)
