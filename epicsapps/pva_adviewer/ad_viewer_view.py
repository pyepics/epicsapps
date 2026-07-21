#!/usr/bin/env python
"""
AD Viewer view
"""

import logging
import sys
import time
from pathlib import Path
from typing import Callable, Protocol

import numpy as np
import wx
from wxmplot import Histogram
from wxutils import FlatTextCtrl, FlatIconButton, draw_chevron_left, draw_chevron_right, draw_cog, draw_folder

from epicsapps.pva_adviewer import ImageCanvas, ImageSettingsPopup, IntegrationPlot, LiveToggle
from epicsapps.pva_adviewer.theme import AppTheme, get_theme
from epicsapps.pva_adviewer.widgets import PlotToggleButton

__all__ = ["ADViewerView"]

_log = logging.getLogger(__name__)

RoiCoords = tuple[int, int, int, int]
IntegrationSettings = tuple[int, str]

_DEFAULT_COLORMAP: str = "grays"
_DEFAULT_NPT: int = 1_000
_INTEGRATION_UNITS: list[str] = ["2th_deg", "d_A", "q_A^-1"]


class _FileLoadCallback(Protocol):
    def __call__(self, filepath: Path) -> None: ...


class _RoiChangedCallback(Protocol):
    def __call__(self, x1: int | None, y1: int | None, x2: int | None, y2: int | None) -> None: ...


class _FrameNavCallback(Protocol):
    def __call__(self, index: int) -> None: ...


class ADViewerView(wx.Panel):
    """AD Viewer panel – renders detector images and exposes a clean API for the controller."""

    def __init__(self, parent: wx.Window) -> None:
        super().__init__(parent)

        self._current_frame: np.ndarray | None = None
        self._live_updates: bool = True
        self._auto_scale: bool = True
        self._filter_gaps: bool = True
        # Throttle the intensity histogram + contrast-readback so they don't bottleneck the live image canvas
        self._histogram_min_interval_s: float = 0.1
        self._last_histogram_update: float = 0.0
        self._last_pushed_levels: tuple[float, float] | None = None
        self._current_colormap: str = _DEFAULT_COLORMAP
        self._current_npt: int = _DEFAULT_NPT
        self._current_unit: str = _INTEGRATION_UNITS[0]
        self._poni_label_text: str = "No calibration loaded"
        self._mask_above: float | None = None
        self._mask_below: float | None = None
        self._pixel_size: float | None = 1.0
        self._integration_plot_visible: bool = True

        self._load_file_cb: _FileLoadCallback | None = None
        self._load_poni_cb: _FileLoadCallback | None = None
        self._integration_changed_cb: Callable[[], None] | None = None
        self._roi_live_integration_cb: Callable[[bool], None] | None = None
        self._roi_cleared_cb: Callable[[], None] | None = None
        self._reset_view_cb: Callable[[], None] | None = None
        self._mask_changed_cb: Callable | None = None
        self._mask_toggle_cb: Callable | None = None
        self._pixel_size_changed_cb: Callable | None = None
        self._line_changed_cb: Callable | None = None
        self._frame_nav_cb: _FrameNavCallback | None = None
        self._current_frame_index: int = 0
        self._total_frames: int = 0

        self._build_layout()

    def _build_layout(self) -> None:
        self._intensity_histogram = Histogram(self, colormap="gray", on_levels_changed=self._on_histogram_levels_changed, log_scale=True, show_colorbar=True)
        self._integration_plot = IntegrationPlot(self)

        self.SetBackgroundColour(wx.BLACK)

        self._canvas_panel = wx.Panel(self)
        self._canvas_panel.SetBackgroundColour(wx.BLACK)
        self._image_canvas = ImageCanvas(self._canvas_panel)

        # Parent overlay buttons to the VisPy native widget so they render above it on Windows
        overlay_parent = self._image_canvas.native

        self._load_file_btn = FlatIconButton(overlay_parent, draw_folder, tooltip="Load image file")
        self._load_file_btn.Bind(wx.EVT_BUTTON, lambda _: self._trigger_load_file())

        self._prev_btn = FlatIconButton(overlay_parent, draw_chevron_left, tooltip="Previous frame")
        self._prev_btn.Bind(wx.EVT_BUTTON, self._on_prev_frame)
        self._prev_btn.Hide()

        self._next_btn = FlatIconButton(overlay_parent, draw_chevron_right, tooltip="Next frame")
        self._next_btn.Bind(wx.EVT_BUTTON, self._on_next_frame)
        self._next_btn.Hide()

        self._frame_ctrl = FlatTextCtrl(
            overlay_parent, value="0", centered=True,
            size=wx.Size(AppTheme.unit_btn_w, AppTheme.btn_h),
        )
        self._frame_ctrl.Bind(wx.EVT_TEXT_ENTER, self._on_frame_ctrl_enter)
        self._frame_ctrl.Bind(wx.EVT_KILL_FOCUS, self._on_frame_ctrl_enter)
        self._frame_ctrl.Hide()

        self._settings_btn = FlatIconButton(overlay_parent, draw_cog, tooltip="Image settings")
        self._settings_btn.Bind(wx.EVT_BUTTON, self._on_settings_btn)

        self._live_toggle = LiveToggle(overlay_parent, live=self._live_updates)
        self._live_toggle.set_toggled_callback(self._apply_live_updates)

        self._mask_btn = PlotToggleButton(overlay_parent, label="M", tooltip="Toggle pixel masking")
        self._mask_btn.SetAction(lambda _e: self._on_mask_toggle_btn(self._mask_btn.GetValue()))

        self._status_overlay = wx.StaticText(overlay_parent, label="")
        t = get_theme()
        self._status_overlay.SetBackgroundColour(t.background)
        self._status_overlay.SetForegroundColour(t.white)
        self._status_overlay.SetFont(AppTheme.scaled_font(13))
        self._status_overlay.Hide()

        canvas_sizer = wx.BoxSizer(wx.VERTICAL)
        canvas_sizer.Add(self._image_canvas, 1, wx.EXPAND)
        self._canvas_panel.SetSizer(canvas_sizer)
        self._canvas_panel.SetMinSize((-1, 200))

        # Track size changes on the native VisPy widget so overlays reposition whenever the canvas resizes
        overlay_parent.Bind(wx.EVT_SIZE, self._on_overlay_parent_size)
        overlay_parent.Bind(wx.EVT_MOTION, self._on_canvas_panel_motion)
        overlay_parent.Bind(wx.EVT_LEAVE_WINDOW, self._on_canvas_panel_leave)

        inner = wx.BoxSizer(wx.VERTICAL)
        inner.Add(self._intensity_histogram, 0, wx.EXPAND)
        inner.Add(self._canvas_panel, 3, wx.EXPAND)
        inner.Add(self._integration_plot, 1, wx.EXPAND)
        self._inner_sizer = inner
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(inner, 1, wx.EXPAND | wx.ALL, 5)
        self.SetSizer(sizer)

        self._image_canvas.set_roi_cleared_callback(self._on_roi_or_line_cleared)
        self._integration_plot.set_load_poni_callback(self._trigger_load_poni)
        self._integration_plot.set_unit_changed_callback(self._on_unit_changed)
        self._integration_plot.set_live_integration_callback(self._on_roi_live_integration_toggled)
        self._image_canvas.set_overlay_motion_callback(self._on_canvas_panel_motion_xy)
        self._image_canvas.set_filter_gaps(self._filter_gaps)

        self._reposition_overlay_buttons()

    def bind_load_file(self, callback: _FileLoadCallback) -> None:
        self._load_file_cb = callback

    def bind_load_poni(self, callback: _FileLoadCallback) -> None:
        self._load_poni_cb = callback

    def bind_integration_settings_changed(self, callback: Callable[[], None]) -> None:
        self._integration_changed_cb = callback

    def bind_roi_changed(self, callback: _RoiChangedCallback) -> None:
        self._image_canvas.set_roi_changed_callback(callback)

    def bind_line_changed(self, callback: Callable) -> None:
        self._line_changed_cb = callback
        self._image_canvas.set_line_changed_callback(callback)

    def bind_frame_navigation(self, callback: _FrameNavCallback) -> None:
        self._frame_nav_cb = callback

    def bind_roi_live_integration(self, callback: Callable[[bool], None]) -> None:
        self._roi_live_integration_cb = callback
        self._integration_plot.set_live_integration_callback(callback)

    def bind_bg_changed(self, callback: Callable[[bool], None]) -> None:
        self._integration_plot.set_bg_callback(callback)

    def bind_bg_inspect_changed(self, callback: Callable[[bool], None]) -> None:
        self._integration_plot.set_bg_inspect_callback(callback)

    def bind_bkg_roi_changed(self, callback: Callable[[float, float], None]) -> None:
        self._integration_plot.set_bkg_roi_changed_callback(callback)

    def bind_poly_order_changed(self, callback: Callable[[int], None]) -> None:
        self._integration_plot.set_poly_order_callback(callback)

    @property
    def bg_inspect_active(self) -> bool:
        return self._integration_plot.bg_inspect_active

    def set_bg_active(self, active: bool) -> None:
        self._integration_plot.set_bg_active(active)

    def set_bkg_data(self, xs: np.ndarray, ys: np.ndarray) -> None:
        self._integration_plot.set_bkg_data(xs, ys)

    def clear_bkg_data(self) -> None:
        self._integration_plot.clear_bkg_data()

    def show_bkg_roi(self, x_min: float, x_max: float) -> None:
        self._integration_plot.show_bkg_roi(x_min, x_max)

    def hide_bkg_roi(self) -> None:
        self._integration_plot.hide_bkg_roi()

    def get_bkg_roi(self) -> tuple[float, float]:
        return self._integration_plot.get_bkg_roi()

    def bind_roi_cleared(self, callback: Callable[[], None]) -> None:
        self._roi_cleared_cb = callback

    def bind_reset_view(self, callback: Callable[[], None]) -> None:
        self._reset_view_cb = callback

    def bind_mask_changed(self, callback: Callable) -> None:
        self._mask_changed_cb = callback

    def bind_mask_toggle(self, callback: Callable[[bool], None]) -> None:
        self._mask_toggle_cb = callback

    def bind_pixel_size_changed(self, callback: Callable) -> None:
        self._pixel_size_changed_cb = callback

    def set_mask_active(self, active: bool) -> None:
        self._mask_btn.SetValue(active)

    def set_mask_overlay(self, mask: "np.ndarray | None") -> None:
        self._image_canvas.set_mask_overlay(mask)

    @property
    def pixel_size(self) -> "float | None":
        return self._pixel_size

    def set_line_length_label(self, text: "str | None") -> None:
        self._image_canvas.set_line_length_label(text)

    @property
    def is_roi_live_integration(self) -> bool:
        return self._integration_plot.is_live_integration

    @property
    def current_frame(self) -> np.ndarray | None:
        return self._current_frame

    def update_frame(self, frame: np.ndarray) -> None:
        if frame is None or frame.size == 0:
            _log.warning(f"update_frame: skipping (frame is None or empty)")
            return
        if not self._live_updates:
            return
        _log.info(f"update_frame: calling display_frame with shape={frame.shape}, dtype={frame.dtype}")
        self.display_frame(frame, reset_histogram_range=self._auto_scale)

    def display_frame(self, frame: np.ndarray, reset_histogram_range: bool = True) -> None:
        """Forward frame to the GPU every call and throttle the side widgets."""
        _log.info(f"display_frame: shape={frame.shape}, dtype={frame.dtype}, min={frame.min()}, max={frame.max()}")
        self._current_frame = frame
        display_2d = frame.mean(axis=2) if frame.ndim == 3 else frame.copy()
        self._image_canvas.set_image(display_2d)
        _log.info(f"display_frame: called set_image on canvas")

        now = time.perf_counter()
        if now - self._last_histogram_update < self._histogram_min_interval_s:
            return
        self._last_histogram_update = now
        if reset_histogram_range:
            self._intensity_histogram.set_data(frame, auto_scale=False)
        else:
            # Keep existing axis range; only refresh bars for the new frame
            self._intensity_histogram.set_data(frame, auto_scale=False, data_range=self._intensity_histogram.get_range())
        lo, hi = self._image_canvas.get_contrast_range()
        self._intensity_histogram.set_levels(lo, hi)
        self._last_pushed_levels = (lo, hi)

    def set_live_updates(self, enabled: bool) -> None:
        self._live_updates = enabled
        self._live_toggle.set_live(enabled)

    def set_poni_label(self, text: str, success: bool = True) -> None:
        self._poni_label_text = text
        self._integration_plot.set_poni_info(text, success=success)
        self._integration_plot.set_calibrated(success)

    def set_active_unit(self, unit: str) -> None:
        self._current_unit = unit
        self._integration_plot.set_active_unit(unit)

    def set_d_spacing_func(self, func: Callable | None) -> None:
        self._image_canvas.set_d_spacing_func(func)

    def set_two_theta_func(self, func: Callable | None) -> None:
        self._image_canvas.set_two_theta_func(func)

    def get_integration_settings(self) -> IntegrationSettings:
        return self._current_npt, self._current_unit

    def get_roi_coords(self) -> RoiCoords | None:
        return self._image_canvas.get_roi_coords()

    def get_line_coords(self) -> RoiCoords | None:
        return self._image_canvas.get_line_coords()

    @property
    def is_integration_plot_visible(self) -> bool:
        return self._integration_plot_visible

    def set_integration_plot_visible(self, visible: bool) -> None:
        if visible == self._integration_plot_visible:
            return
        self._integration_plot_visible = visible
        self._inner_sizer.Show(self._integration_plot, visible, recursive=True)
        self.Layout()

    def set_integration_data(self, xs: np.ndarray, ys: np.ndarray, x_label: str) -> None:
        if not self._integration_plot_visible:
            return
        self._integration_plot.set_data(xs, ys, x_label=x_label)

    def clear_integration_plot(self) -> None:
        if not self._integration_plot_visible:
            return
        self._integration_plot.clear()

    def reset_view(self) -> None:
        self._image_canvas.reset_view()

    def set_status_overlay(self, text: str) -> None:
        """Show a centered status message over the canvas (or hide it when *text* is empty)."""
        if text:
            self._status_overlay.SetLabel(text)
            self._status_overlay.Show()
            self._status_overlay.Raise()
            self._reposition_overlay_buttons()
        else:
            self._status_overlay.Hide()

    def set_frame_navigation(self, total_frames: int, current_index: int = 0) -> None:
        self._total_frames = total_frames
        self._current_frame_index = current_index
        visible = total_frames > 1 and not self._live_updates
        self._prev_btn.Show(visible)
        self._next_btn.Show(visible)
        self._frame_ctrl.Show(visible)
        if visible:
            self._frame_ctrl.SetValue(str(current_index + 1))
        self._reposition_overlay_buttons()

    def _on_roi_or_line_cleared(self) -> None:
        if self._roi_cleared_cb is not None:
            self._roi_cleared_cb()

    def _on_unit_changed(self, unit: str) -> None:
        self._current_unit = unit
        self._integration_plot.set_active_unit(unit)
        if self._integration_changed_cb is not None:
            self._integration_changed_cb()

    def _on_roi_live_integration_toggled(self, enabled: bool) -> None:
        if self._roi_live_integration_cb is not None:
            self._roi_live_integration_cb(enabled)

    def _on_histogram_levels_changed(self, min_val: float, max_val: float) -> None:
        _log.info(f"Histogram levels changed: min={min_val}, max={max_val}, setting auto_scale=False")
        self._auto_scale = False
        self._image_canvas.set_contrast(min_val, max_val)
        self._intensity_histogram.set_levels(min_val, max_val)
        _log.info(f"Canvas contrast set, auto_scale on canvas: {self._image_canvas._auto_scale}")

    def _on_overlay_parent_size(self, event: wx.SizeEvent) -> None:
        event.Skip()
        self._reposition_overlay_buttons()

    def _reposition_overlay_buttons(self) -> None:
        # Coordinates are now relative to the native VisPy widget (overlay parent)
        panel_w, panel_h = self._image_canvas.native.GetClientSize()
        if self._status_overlay.IsShown():
            self._status_overlay.SetSize(self._status_overlay.GetBestSize())
            ow, oh = self._status_overlay.GetSize()
            self._status_overlay.SetPosition(wx.Point(max(0, (panel_w - ow) // 2), max(0, (panel_h - oh) // 2)))
            self._status_overlay.Raise()
        cog_sz = self._settings_btn.GetBestSize()
        x = panel_w - cog_sz.width - 4
        self._settings_btn.SetPosition(wx.Point(x, 4))
        self._settings_btn.Raise()

        lw, _lh = self._live_toggle.GetSize()
        self._live_toggle.SetPosition(wx.Point(x + (cog_sz.width - lw) // 2, 4 + cog_sz.height + 4))
        self._live_toggle.Raise()

        load_sz = self._load_file_btn.GetBestSize()
        x -= load_sz.width + 4
        self._load_file_btn.SetPosition(wx.Point(x, 4))
        self._load_file_btn.Raise()

        mask_sz = self._mask_btn.GetBestSize()
        mx = panel_w - cog_sz.width - 4 + (cog_sz.width - mask_sz.width) // 2
        my = panel_h - mask_sz.height - 4
        self._mask_btn.SetPosition(wx.Point(mx, my))
        self._mask_btn.Raise()

        if self._total_frames > 1:
            next_sz = self._next_btn.GetBestSize()
            x -= next_sz.width + 2
            self._next_btn.SetPosition(wx.Point(x, 4))
            self._next_btn.Raise()

            ctrl_w, ctrl_h = self._frame_ctrl.GetSize()
            x -= ctrl_w + 2
            self._frame_ctrl.SetPosition(wx.Point(x, 4 + (next_sz.height - ctrl_h) // 2))
            self._frame_ctrl.Raise()

            prev_sz = self._prev_btn.GetBestSize()
            x -= prev_sz.width + 2
            self._prev_btn.SetPosition(wx.Point(x, 4))
            self._prev_btn.Raise()

    def _overlay_buttons(self) -> list:
        btns = [self._mask_btn, self._load_file_btn, self._settings_btn, self._live_toggle]
        if self._total_frames > 1:
            btns += [self._prev_btn, self._next_btn]
        return btns

    def _update_overlay_hover(self, pt: wx.Point) -> None:
        for btn in self._overlay_buttons():
            if not btn.IsShown():
                continue
            pos = btn.GetPosition()
            sz = btn.GetSize()
            btn.set_hovered(wx.Rect(pos.x, pos.y, sz.width, sz.height).Contains(pt))

    def _on_canvas_panel_motion(self, event: wx.MouseEvent) -> None:
        self._update_overlay_hover(event.GetPosition())
        event.Skip()

    def _on_canvas_panel_motion_xy(self, x: int, y: int) -> None:
        self._update_overlay_hover(wx.Point(x, y))

    def _on_canvas_panel_leave(self, event: wx.MouseEvent) -> None:
        pos = wx.GetMousePosition()
        for btn in self._overlay_buttons():
            if not btn.GetScreenRect().Contains(pos):
                btn.set_hovered(False)
        event.Skip()

    def _on_settings_btn(self, event: wx.CommandEvent) -> None:
        lo, hi = self._image_canvas.get_contrast_range()
        popup = ImageSettingsPopup(
            self,
            colormap=self._current_colormap,
            auto_scale=self._auto_scale,
            filter_gaps=self._filter_gaps,
            contrast_min=lo,
            contrast_max=hi,
            bin_method=self._image_canvas.bin_method,
            on_colormap_changed=self._apply_colormap,
            on_auto_scale_changed=self._apply_auto_scale,
            on_filter_gaps_changed=self._apply_filter_gaps,
            on_levels_changed=self._on_histogram_levels_changed,
            on_bin_method_changed=self._apply_bin_method,
            on_reset_view=self._apply_reset_view,
            on_mask_changed=self._apply_mask_changed,
            mask_above=self._mask_above,
            mask_below=self._mask_below,
            pixel_size=self._pixel_size,
            on_pixel_size_changed=self._apply_pixel_size,
        )
        btn_sz = self._settings_btn.GetSize()
        popup_w, _ = popup.GetSize()
        pos = self._settings_btn.ClientToScreen(wx.Point(btn_sz.width - popup_w, btn_sz.height))
        popup.Position(pos, (0, 0))
        popup.Popup()

    def _on_prev_frame(self, event: wx.CommandEvent) -> None:
        if self._current_frame_index > 0:
            self._navigate_to(self._current_frame_index - 1)

    def _on_next_frame(self, event: wx.CommandEvent) -> None:
        if self._current_frame_index < self._total_frames - 1:
            self._navigate_to(self._current_frame_index + 1)

    def _on_frame_ctrl_enter(self, event: wx.Event) -> None:
        try:
            index = max(1, min(int(self._frame_ctrl.GetValue()), self._total_frames)) - 1
        except ValueError:
            self._frame_ctrl.SetValue(str(self._current_frame_index + 1))
            event.Skip()
            return
        self._navigate_to(index)
        event.Skip()

    def _navigate_to(self, index: int) -> None:
        self._current_frame_index = index
        self._frame_ctrl.SetValue(str(index + 1))
        if self._frame_nav_cb is not None:
            self._frame_nav_cb(index)

    def _apply_colormap(self, colormap: str) -> None:
        self._current_colormap = colormap
        self._image_canvas.set_colormap(colormap)
        self._intensity_histogram.set_colormap(colormap)

    def _apply_auto_scale(self, enabled: bool) -> None:
        self._auto_scale = enabled
        self._image_canvas.set_auto_scale(enabled)
        if self._current_frame is not None:
            self._intensity_histogram.set_data(self._current_frame, auto_scale=False)
            lo, hi = self._image_canvas.get_contrast_range()
            self._intensity_histogram.set_levels(lo, hi)

    def _apply_filter_gaps(self, enabled: bool) -> None:
        self._filter_gaps = enabled
        self._image_canvas.set_filter_gaps(enabled)
        if self._current_frame is not None:
            self._intensity_histogram.set_data(self._current_frame, auto_scale=False)
            lo, hi = self._image_canvas.get_contrast_range()
            self._intensity_histogram.set_levels(lo, hi)

    def _apply_bin_method(self, method: str) -> None:
        self._image_canvas.set_bin_method(method)

    def _apply_live_updates(self, enabled: bool) -> None:
        _log.info(f"_apply_live_updates: changing from {self._live_updates} to {enabled}")
        self._live_updates = enabled
        if enabled:
            self._prev_btn.Hide()
            self._next_btn.Hide()
            self._frame_ctrl.Hide()
            self._reposition_overlay_buttons()

    def _apply_reset_view(self) -> None:
        self._image_canvas.reset_view()
        if self._reset_view_cb is not None:
            self._reset_view_cb()

    def _on_mask_toggle_btn(self, active: bool) -> None:
        if self._mask_toggle_cb is not None:
            self._mask_toggle_cb(active)

    def _apply_mask_changed(self, above: "float | None", below: "float | None") -> None:
        self._mask_above = above
        self._mask_below = below
        if self._mask_changed_cb is not None:
            self._mask_changed_cb(above, below)

    def _apply_pixel_size(self, value: "float | None") -> None:
        self._pixel_size = value
        if self._pixel_size_changed_cb is not None:
            self._pixel_size_changed_cb(value)

    def _trigger_load_file(self) -> None:
        with wx.FileDialog(
            self,
            "Open image file",
            wildcard="HDF5 files (*.h5;*.hdf5)|*.h5;*.hdf5" + ("|All files (*.*)|*.*" if sys.platform == "win32" else ""),
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dlg:
            if dlg.ShowModal() == wx.ID_CANCEL:
                return
            filepath = Path(dlg.GetPath())
        if self._load_file_cb is not None:
            self._load_file_cb(filepath)

    def _trigger_load_poni(self) -> None:
        with wx.FileDialog(
            self,
            "Open .poni calibration file",
            wildcard="PONI files (*.poni)|*.poni" + ("|All files (*.*)|*.*" if sys.platform == "win32" else ""),
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dlg:
            if dlg.ShowModal() == wx.ID_CANCEL:
                return
            poni_path = Path(dlg.GetPath())
        if self._load_poni_cb is not None:
            self._load_poni_cb(poni_path)
