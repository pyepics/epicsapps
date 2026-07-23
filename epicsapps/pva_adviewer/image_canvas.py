#!/usr/bin/env python
"""
Extends wxmplot.ImageCanvas with pixel info (d-spacing, 2-theta) and overlay motion callback.
"""

from typing import Callable

import numpy as np
import wx
from vispy import scene

from wxmplot.image_canvas import BinMethod, ImageCanvas as _ImageCanvas

from epicsapps.pva_adviewer.theme import get_theme

__all__ = ["ImageCanvas", "BinMethod"]


class ImageCanvas(_ImageCanvas):
    """Extended ImageCanvas"""

    def __init__(self, parent: wx.Window) -> None:
        """Initializes the ImageCanvas."""
        super().__init__(parent)
        self._d_spacing_func = None
        self._two_theta_func = None
        self._overlay_motion_callback = None

        self._mask_visual = scene.visuals.Image(
            np.zeros((1, 1, 4), dtype=np.uint8),
            parent=self._view.scene,
            method='auto',
        )
        self._mask_visual.visible = False
        self._mask_rgba_buf: "np.ndarray | None" = None

        self._line_label_visual = scene.visuals.Text(
            text="",
            color=self._theme_green(),
            font_size=6,
            bold=True,
            anchor_x="center",
            anchor_y="top",
            parent=self._canvas.scene,
        )
        self._line_label_visual.visible = False

        self._canvas.native.Bind(wx.EVT_SIZE, self._on_canvas_size)

    def _theme_green(self) -> tuple:
        c = get_theme().green
        return (c.Red() / 255, c.Green() / 255, c.Blue() / 255, 1.0)

    def _on_theme_change(self, is_dark: bool = False) -> None:
        super()._on_theme_change(is_dark)
        self._line_label_visual.color = self._theme_green()

    def set_d_spacing_func(self, func: Callable | None) -> None:
        """Set a function (ix, iy) -> float | None for d-spacing overlay."""
        self._d_spacing_func = func

    def set_two_theta_func(self, func: Callable | None) -> None:
        """Set a function (ix, iy) -> float | None for 2-theta overlay."""
        self._two_theta_func = func

    def set_line_length_label(self, text: "str | None") -> None:
        """Show a length label in the bottom-right corner of the canvas, or hide it."""
        if not text:
            self._line_label_visual.visible = False
            self._canvas.update()
            return
        cw, ch = self._canvas.size
        self._line_label_visual.text = text
        self._line_label_visual.pos = (cw / 2, ch - 20)
        self._line_label_visual.visible = True
        self._canvas.update()

    def _on_canvas_size(self, event: wx.SizeEvent) -> None:
        event.Skip()
        if self._line_label_visual.visible:
            cw, ch = self._canvas.size
            self._line_label_visual.pos = (cw / 2, ch - 20)

    def set_mask_overlay(self, mask: "np.ndarray | None") -> None:
        """Show semi-transparent orange overlay on masked pixels, or hide if mask is None."""
        if mask is None or not np.any(mask):
            self._mask_visual.visible = False
            self._canvas.update()
            return
        h, w = mask.shape
        if self._mask_rgba_buf is None or self._mask_rgba_buf.shape[:2] != (h, w):
            self._mask_rgba_buf = np.zeros((h, w, 4), dtype=np.uint8)
        else:
            self._mask_rgba_buf[:] = 0
        self._mask_rgba_buf[mask.astype(bool)] = [255, 89, 0, 140]
        self._mask_visual.set_data(self._mask_rgba_buf)
        self._mask_visual.visible = True
        self._canvas.update()

    def set_mask_overlay_rgba(self, rgba: "np.ndarray | None") -> None:
        """Apply a pre-computed RGBA mask buffer (must be called on main thread)."""
        if rgba is None:
            self._mask_visual.visible = False
            self._canvas.update()
            return
        self._mask_visual.set_data(rgba)
        self._mask_visual.visible = True
        self._canvas.update()

    def set_overlay_motion_callback(self, callback: Callable[[int, int], None] | None) -> None:
        """Set a callback invoked with parent-relative (x, y) on every mouse move."""
        self._overlay_motion_callback = callback

    def format_pixel_info(self, ix: int, iy: int, intensity: float) -> str:
        """Append d-spacing and 2-theta to the base pixel info string."""
        text = f"x: {ix}  y: {iy}  I: {intensity:.4g}"
        if self._d_spacing_func is not None:
            d = self._d_spacing_func(ix, iy)
            if d is not None:
                text += f"  d: {d:.4g} \u212b"
        if self._two_theta_func is not None:
            tth = self._two_theta_func(ix, iy)
            if tth is not None:
                text += f"  2\u03b8: {tth:.4g}\u00b0"
        return text

    def _on_mouse_move(self, event: wx.MouseEvent) -> None:
        super()._on_mouse_move(event)
        if self._overlay_motion_callback is not None:
            screen_pt = self._canvas.native.ClientToScreen(wx.Point(event.GetX(), event.GetY()))
            panel_pt = self.GetParent().ScreenToClient(screen_pt)
            self._overlay_motion_callback(panel_pt.x, panel_pt.y)
