#!/usr/bin/env python
"""
Controller for the PVA adviewer.
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Lock, RLock

import numpy as np
import wx
from wxutils import FlatMessageDialog

from epicsapps.pva_adviewer.ad_viewer_model import ADViewerModel, FrameModel, StreamRatesModel
from epicsapps.pva_adviewer.ad_viewer_view import ADViewerView
from epicsapps.pva_adviewer.image_loader_model import ImageLoaderModel
from epicsapps.pva_adviewer.integration_model import HAS_PYFAI, IntegrationModel

__all__ = ["ADViewerController"]

_log = logging.getLogger(__name__)


class ADViewerController:
    """Bridges the AD Viewer model and view."""

    def __init__(self, ad_model: ADViewerModel, image_loader: ImageLoaderModel, view: ADViewerView) -> None:
        """Initialises the controller, wires up bindings, and starts the PV stream."""
        self._ad_model = ad_model
        self._image_loader = image_loader
        self._view = view
        self._pending_frame: np.ndarray | None = None
        self._pending_lock = Lock()

        self._integration = IntegrationModel()
        self._mask_active: bool = False
        self._overlay_visible: bool = False
        self._stored_mask_above: "float | None" = None
        self._stored_mask_below: "float | None" = None
        self._compute_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="adviewer-compute")
        self._compute_lock = RLock()
        self._pending_compute_args: "tuple | None" = None
        self._compute_active: bool = False

        # Stored data for toggling inspect mode without re-integrating
        self._last_xs: np.ndarray | None = None
        self._last_raw_ys: np.ndarray | None = None
        self._last_sub_xs: np.ndarray | None = None
        self._last_sub_ys: np.ndarray | None = None
        self._last_bkg_xs: np.ndarray | None = None
        self._last_bkg_ys: np.ndarray | None = None
        self._last_x_label: str = ""

        self._view.bind_load_file(self._on_load_file)
        self._view.bind_load_poni(self._on_load_poni)
        self._view.bind_integration_settings_changed(self._on_integration_settings_changed)
        self._view.bind_roi_live_integration(self._on_roi_live_integration_changed)
        self._view.bind_roi_changed(self._on_roi_changed)
        self._view.bind_roi_cleared(self._on_roi_cleared)
        self._view.bind_reset_view(self._on_reset_view)
        self._view.bind_line_changed(self._on_line_changed)
        self._view.bind_frame_navigation(self._on_navigate_frame)
        self._view.bind_bg_changed(self._on_bg_changed)
        self._view.bind_bg_inspect_changed(self._on_bg_inspect_changed)
        self._view.bind_bkg_roi_changed(self._on_bkg_roi_changed)
        self._view.bind_poly_order_changed(self._on_poly_order_changed)
        self._view.bind_mask_changed(self._on_mask_changed)
        self._view.bind_mask_toggle(self._on_mask_toggle)
        self._view.bind_pixel_size_changed(self._on_pixel_size_changed)

        self._stats_prev = None
        self._stats_prev_time: float = 0.0
        self._stats_timer = wx.Timer()
        self._stats_timer.Bind(wx.EVT_TIMER, self._on_stats_tick)
        self._stats_timer.Start(1000)

    def _on_stats_tick(self, _event=None) -> None:
        now = time.monotonic()
        curr = self._ad_model.stats
        if self._stats_prev is None or not self._ad_model.is_subscribed:
            self._stats_prev = curr
            self._stats_prev_time = now
            self._view.set_fps(None)
            return
        elapsed = now - self._stats_prev_time
        rates = StreamRatesModel.between(self._stats_prev, curr, elapsed, 0.0)
        self._stats_prev = curr
        self._stats_prev_time = now
        self._view.set_fps(rates.fps if rates.fps > 0 else None)

    def subscribe(self, pv_name: str) -> None:
        """Subscribe to a PVA channel and start delivering frames to the view."""
        if not pv_name:
            self._view.set_status_overlay("No PV configured")
            _log.warning("subscribe() called with empty PV name")
            return
        _log.info(f"Subscribing to PV: {pv_name}")
        self._view.set_status_overlay("")
        self._ad_model.subscribe(pv_name=pv_name, frame_callback=self._on_new_frame)

    def unsubscribe(self) -> None:
        """Tear down the active PVA subscription."""
        self._ad_model.unsubscribe()

    def shutdown(self) -> None:
        """Release all PVA resources. Call on application exit."""
        self._stats_timer.Stop()
        self._compute_pool.shutdown(wait=False)
        self._ad_model.shutdown()

    def _on_new_frame(self, frame: FrameModel) -> None:
        """Deliver a detector frame to the view on the GUI thread, dropping frames if busy."""
        _log.info(f"Received frame: {frame}")
        with self._pending_lock:
            already_pending = self._pending_frame is not None
            self._pending_frame = frame.image
        if not already_pending:
            wx.CallAfter(self._on_new_frame_gui)

    def _on_new_frame_gui(self) -> None:
        """Handle a new frame on the GUI thread: update image and optionally ROI plot."""
        try:
            with self._pending_lock:
                frame = self._pending_frame
                self._pending_frame = None
            if frame is None:
                _log.warning("_on_new_frame_gui called but frame is None")
                return
            _log.info(f"Displaying frame on GUI thread, shape={frame.shape}, dtype={frame.dtype}")
            self._view.update_frame(frame)
            current_frame = self._view.current_frame
            if current_frame is None:
                return
            if self._integration.is_calibrated and self._view.is_integration_plot_visible:
                if self._view.is_roi_live_integration:
                    self._run_integration(current_frame)
            self._submit_compute(current_frame)
        except Exception:
            _log.exception("Error in _on_new_frame_gui - this might cause frames to stop updating")

    def _on_load_poni(self, poni_path: Path) -> None:
        """Load a .poni calibration file and wire pixel-level d-spacing / 2θ overlays."""
        if not HAS_PYFAI:
            FlatMessageDialog(self._view, "pyFAI is not installed.", "Missing Dependency").ShowModal()
            return
        try:
            self._integration.load_poni(poni_path)
        except Exception as exc:
            _log.exception("Failed to load .poni file %s", poni_path)
            FlatMessageDialog(self._view, f"Failed to load .poni file:\n{exc}", "Error").ShowModal()
            return

        self._view.set_poni_label(poni_path.name, success=True)
        self._view.set_d_spacing_func(self._integration.compute_d_spacing)
        self._view.set_two_theta_func(self._integration.compute_two_theta)
        self._view.set_active_unit("2th_deg")
        current_frame = self._view.current_frame
        if current_frame is not None:
            self._run_integration(current_frame)

    def _on_roi_cleared(self) -> None:
        """Show the full-image plot when the ROI or line is cleared."""
        self._view.set_line_length_label(None)
        current_frame = self._view.current_frame
        if current_frame is None:
            return
        if self._integration.is_calibrated:
            self._run_integration(current_frame)
        self._submit_compute(current_frame)

    def _on_reset_view(self) -> None:
        """Re-plot the full image when the view is reset."""
        self._view.set_line_length_label(None)
        current_frame = self._view.current_frame
        if current_frame is None:
            return
        if self._integration.is_calibrated:
            self._run_integration(current_frame)
        self._submit_compute(current_frame)

    def _on_integration_settings_changed(self) -> None:
        """Re-integrate the current frame when the unit or npt changes."""
        current_frame = self._view.current_frame
        if current_frame is not None and self._integration.is_calibrated:
            self._run_integration(current_frame)

    def _on_roi_live_integration_changed(self, enabled: bool) -> None:
        """React to the live integration toggle."""
        if not enabled:
            return
        current_frame = self._view.current_frame
        if current_frame is None:
            return
        roi = self._view.get_roi_coords()
        line = self._view.get_line_coords()
        if roi is None and line is None:
            return
        if self._integration.is_calibrated:
            self._run_integration(current_frame)
        self._submit_compute(current_frame)

    def _run_integration(self, frame: np.ndarray) -> None:
        """Run pyFAI azimuthal or line integration and push results to the view."""
        npt, unit = self._view.get_integration_settings()
        line = self._view.get_line_coords()
        if line is not None:
            try:
                xs, ys, x_label = self._integration.integrate1d_line(frame, *line, unit=unit)
            except Exception:
                _log.exception("pyFAI line integration failed")
                return
            self._view.set_integration_data(xs, ys, x_label)
            return
        roi = self._view.get_roi_coords()
        try:
            xs, ys, x_label = self._integration.integrate1d(frame, npt, unit, roi=roi)
        except Exception:
            _log.exception("pyFAI integrate1d failed")
            return

        self._last_xs = xs
        self._last_raw_ys = ys
        self._last_x_label = x_label

        if self._integration.has_background:
            try:
                sub_xs, sub_ys, bkg_xs, bkg_ys = self._integration.apply_background(xs, ys)
            except Exception:
                _log.exception("Background subtraction failed")
                self._view.set_integration_data(xs, ys, x_label)
                return
            self._last_sub_xs = sub_xs
            self._last_sub_ys = sub_ys
            self._last_bkg_xs = bkg_xs
            self._last_bkg_ys = bkg_ys

            if self._view.bg_inspect_active:
                # Show raw data + background curve + draggable ROI region
                self._view.set_integration_data(xs, ys, x_label)
                self._view.set_bkg_data(bkg_xs, bkg_ys)
                roi = self._integration._bkg_roi
                self._view.show_bkg_roi(*(roi if roi is not None else (float(xs[0]), float(xs[-1]))))
            else:
                self._view.set_integration_data(sub_xs, sub_ys, x_label)
                self._view.clear_bkg_data()
        else:
            self._last_sub_xs = None
            self._last_sub_ys = None
            self._last_bkg_xs = None
            self._last_bkg_ys = None
            self._view.set_integration_data(xs, ys, x_label)

    def _on_bg_changed(self, enabled: bool) -> None:
        """Enable or disable auto background subtraction."""
        if enabled:
            self._integration.enable_background()
        else:
            self._integration.disable_background()
            self._view.clear_bkg_data()
            self._view.hide_bkg_roi()
        current_frame = self._view.current_frame
        if current_frame is not None and self._integration.is_calibrated:
            self._run_integration(current_frame)

    def _on_bg_inspect_changed(self, enabled: bool) -> None:
        """Switch between raw+background overlay (I on) and background-subtracted display (I off)."""
        if not self._integration.has_background or self._last_xs is None:
            return
        if enabled:
            self._view.set_integration_data(self._last_xs, self._last_raw_ys, self._last_x_label)
            if self._last_bkg_xs is not None and self._last_bkg_ys is not None:
                self._view.set_bkg_data(self._last_bkg_xs, self._last_bkg_ys)
            roi = self._integration._bkg_roi
            self._view.show_bkg_roi(*(roi if roi is not None else (float(self._last_xs[0]), float(self._last_xs[-1]))))
        else:
            if self._last_sub_xs is not None and self._last_sub_ys is not None:
                self._view.set_integration_data(self._last_sub_xs, self._last_sub_ys, self._last_x_label)
            self._view.clear_bkg_data()
            self._view.hide_bkg_roi()

    def _on_bkg_roi_changed(self, x_min: float, x_max: float) -> None:
        """Update the background fitting ROI and re-integrate."""
        self._integration.set_bkg_roi(x_min, x_max)
        current_frame = self._view.current_frame
        if current_frame is not None and self._integration.is_calibrated:
            self._run_integration(current_frame)

    def _on_mask_toggle(self, enabled: bool) -> None:
        """Show or hide the mask overlay without changing the underlying mask."""
        self._overlay_visible = enabled
        frame = self._view.current_frame
        if frame is not None:
            self._submit_compute(frame)

    def _on_mask_changed(self, above: "float | None", below: "float | None") -> None:
        """Enable or disable the mask from the settings popup."""
        self._stored_mask_above = above
        self._stored_mask_below = below
        if above is not None or below is not None:
            self._mask_active = True
            self._overlay_visible = True
            self._view.set_mask_active(True)
            self._integration.set_mask_thresholds(above, below)
        else:
            self._mask_active = False
            self._overlay_visible = False
            self._view.set_mask_active(False)
            self._integration.set_mask_thresholds(None, None)
        frame = self._view.current_frame
        if frame is not None:
            if self._integration.is_calibrated and self._view.is_integration_plot_visible:
                self._run_integration(frame)
            self._submit_compute(frame)

    def _on_pixel_size_changed(self, _value: "float | None") -> None:
        """Recompute line length label when pixel size changes."""
        line = self._view.get_line_coords()
        if line is not None:
            self._on_line_changed(*line)

    def _on_poly_order_changed(self, order: int) -> None:
        """Update the Chebyshev polynomial order and re-integrate."""
        self._integration._bkg_cheb_order = order
        current_frame = self._view.current_frame
        if current_frame is not None and self._integration.is_calibrated and self._integration.has_background:
            self._run_integration(current_frame)

    def _on_load_file(self, filepath: Path) -> None:
        """Load an image file and display it; disable live updates on success."""
        suffix = filepath.suffix.lower()
        try:
            if suffix in (".h5", ".hdf5"):
                frame = self._image_loader.load_hdf5(filepath)
            else:
                FlatMessageDialog(self._view, f"Unsupported file format: {suffix}", "Error").ShowModal()
                return
        except ImportError as exc:
            FlatMessageDialog(self._view, str(exc), "Missing Dependency").ShowModal()
            return
        except Exception as exc:
            _log.exception("Failed to load image file %s", filepath)
            FlatMessageDialog(self._view, f"Error loading file:\n{exc}", "Error").ShowModal()
            return

        self._view.display_frame(frame)
        self._view.reset_view()
        self._view.set_live_updates(False)
        if self._integration.is_calibrated and self._view.is_integration_plot_visible:
            self._run_integration(frame)
        self._submit_compute(frame)

        frame_count = self._image_loader.frame_count
        self._view.set_frame_navigation(frame_count, 0)

    def _on_navigate_frame(self, index: int) -> None:
        """Load and display the requested frame index from the current HDF5 file."""
        try:
            frame = self._image_loader.load_hdf5_frame(index)
        except Exception as exc:
            _log.exception("Failed to load frame %d", index)
            FlatMessageDialog(self._view, f"Error loading frame {index}:\n{exc}", "Error").ShowModal()
            return
        self._view.display_frame(frame)
        if self._integration.is_calibrated and self._view.is_integration_plot_visible:
            self._run_integration(frame)
        self._submit_compute(frame)

    def _on_roi_changed(self, x1: int | None, y1: int | None, x2: int | None, y2: int | None) -> None:
        """React to an ROI draw or clear event from the canvas."""
        current_frame = self._view.current_frame
        if current_frame is None:
            self._view.clear_integration_plot()
            return
        if x1 is None or y1 is None or x2 is None or y2 is None:
            if self._integration.is_calibrated:
                self._run_integration(current_frame)
            self._submit_compute(current_frame)
            return
        if self._integration.is_calibrated:
            self._run_integration(current_frame)
        self._submit_compute(current_frame)

    def _on_line_changed(self, x1: int, y1: int, x2: int, y2: int) -> None:
        """React to a line ROI committed via Alt+click on the canvas."""
        current_frame = self._view.current_frame
        if current_frame is None:
            return
        if self._integration.is_calibrated:
            self._run_integration(current_frame)
        self._submit_compute(current_frame)
        pixel_size = self._view.pixel_size
        if pixel_size is not None and pixel_size > 0:
            length_px = float(np.hypot(x2 - x1, y2 - y1))
            length_um = length_px * pixel_size
            if length_um >= 1000:
                self._view.set_line_length_label(f"Line: {length_um / 1000:.3g} mm")
            else:
                self._view.set_line_length_label(f"Line: {length_um:.4g} µm")
        else:
            self._view.set_line_length_label(None)

    def _column_mean_masked(self, img: np.ndarray) -> np.ndarray:
        """Return per-column mean of unmasked pixels; masked columns become 0."""
        mask = self._integration.get_threshold_mask(img)
        if mask is None:
            return img.mean(axis=0)
        valid = ~mask.astype(bool)
        count = valid.sum(axis=0).astype(np.float64)
        safe_count = np.where(count > 0, count, 1.0)
        return np.where(count > 0, (img * valid).sum(axis=0) / safe_count, 0.0)

    def _submit_compute(self, frame: np.ndarray) -> None:
        """Post the latest frame for background integration + mask computation."""
        roi = self._view.get_roi_coords()
        line = self._view.get_line_coords()
        is_calibrated = self._integration.is_calibrated
        plot_visible = self._view.is_integration_plot_visible
        overlay_visible = self._overlay_visible
        with self._compute_lock:
            self._pending_compute_args = (frame, roi, line, is_calibrated, plot_visible, overlay_visible)
            if not self._compute_active:
                self._compute_active = True
                self._compute_pool.submit(self._compute_worker)

    def _compute_worker(self) -> None:
        """Background thread."""
        while True:
            with self._compute_lock:
                args = self._pending_compute_args
                self._pending_compute_args = None
                if args is None:
                    self._compute_active = False
                    return
            frame, roi, line, is_calibrated, plot_visible, overlay_visible = args
            try:
                integration: "tuple | None" = None
                if not is_calibrated and plot_visible:
                    if line is not None:
                        integration = self._bg_line_integration(frame, *line)
                    elif roi is not None:
                        integration = self._bg_roi_fallback(frame, *roi)
                    else:
                        integration = self._bg_full_image_fallback(frame)
                mask_rgba: "np.ndarray | None" = self._bg_mask_rgba(frame) if overlay_visible else None
            except Exception:
                _log.exception("Error in background compute")
                continue
            wx.CallAfter(self._apply_compute, integration, mask_rgba)

    def _apply_compute(
        self,
        integration: "tuple | None",
        mask_rgba: "np.ndarray | None",
    ) -> None:
        """Main thread: apply results from the background compute thread."""
        if integration is not None:
            xs, ys, label = integration
            self._view.set_integration_data(xs, ys, label)
        self._view.set_mask_overlay_rgba(mask_rgba)

    def _bg_full_image_fallback(self, frame: np.ndarray) -> tuple:
        h, w = frame.shape[:2]
        img = frame.mean(axis=2).astype(np.float64) if frame.ndim == 3 else frame.astype(np.float64)
        ys = self._column_mean_masked(img)
        return np.arange(w, dtype=np.float64), ys, "Pixel"

    def _bg_roi_fallback(self, frame: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> tuple:
        h, w = frame.shape[:2]
        x1c = max(0, min(x1, w - 1))
        x2c = max(x1c + 1, min(x2, w))
        y1c = max(0, min(y1, h - 1))
        y2c = max(y1c + 1, min(y2, h))
        roi = frame[y1c:y2c, x1c:x2c].astype(np.float64)
        if roi.ndim == 3:
            roi = roi.mean(axis=2)
        ys = self._column_mean_masked(roi)
        return np.arange(x1c, x1c + len(ys), dtype=np.float64), ys, "Pixel"

    def _bg_line_integration(self, frame: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> tuple:
        length = int(np.hypot(x2 - x1, y2 - y1))
        if length < 2:
            return np.array([0.0]), np.array([0.0]), "Pixel"
        xi = np.clip(np.linspace(x1, x2, length).astype(int), 0, frame.shape[1] - 1)
        yi = np.clip(np.linspace(y1, y2, length).astype(int), 0, frame.shape[0] - 1)
        profile = frame[yi, xi].astype(np.float64)
        return np.arange(length, dtype=np.float64), profile, "Pixel"

    def _bg_mask_rgba(self, frame: np.ndarray) -> "np.ndarray | None":
        """Compute the mask RGBA overlay buffer. Safe to call from a background thread."""
        img_2d = frame.mean(axis=2).astype(np.float64) if frame.ndim == 3 else frame.astype(np.float64)
        mask = self._integration.get_threshold_mask(img_2d)
        if mask is None or not np.any(mask):
            return None
        h, w = mask.shape
        rgba = np.zeros((h, w, 4), dtype=np.uint8)
        rgba[mask.astype(bool)] = [255, 89, 0, 140]
        return rgba
