#!/usr/bin/env python
"""
Extends wxmplot.ImageCanvas with pixel info (d-spacing, 2-theta) and overlay motion callback.
"""

from typing import Callable

import numpy as np
import wx
from vispy import scene

from wxmplot.image_canvas import BinMethod, ImageCanvas as _ImageCanvas

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
            np.zeros((1, 1, 4), dtype=np.float32),
            parent=self._view.scene,
            method='subdivide',
        )
        self._mask_visual.visible = False

    def set_d_spacing_func(self, func: Callable | None) -> None:
        """Set a function (ix, iy) -> float | None for d-spacing overlay."""
        self._d_spacing_func = func

    def set_two_theta_func(self, func: Callable | None) -> None:
        """Set a function (ix, iy) -> float | None for 2-theta overlay."""
        self._two_theta_func = func

    def set_mask_overlay(self, mask: "np.ndarray | None") -> None:
        """Show semi-transparent orange overlay on masked pixels, or hide if mask is None."""
        if mask is None or not np.any(mask):
            self._mask_visual.visible = False
            self._canvas.update()
            return
        h, w = mask.shape
        rgba = np.zeros((h, w, 4), dtype=np.float32)
        rgba[mask.astype(bool)] = [1.0, 0.35, 0.0, 0.55]
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
