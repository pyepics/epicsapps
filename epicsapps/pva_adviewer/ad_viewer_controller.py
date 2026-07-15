#!/usr/bin/env python
"""
Controller for the PVA adviewer.
"""

import logging
from pathlib import Path
from threading import Lock

import numpy as np
import wx

from epicsapps.pva_adviewer.ad_viewer_model import ADViewerModel, FrameModel
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

        self._view.bind_load_file(self._on_load_file)
        self._view.bind_load_poni(self._on_load_poni)
        self._view.bind_integration_settings_changed(self._on_integration_settings_changed)
        self._view.bind_roi_live_integration(self._on_roi_live_integration_changed)
        self._view.bind_roi_changed(self._on_roi_changed)
        self._view.bind_roi_cleared(self._on_roi_cleared)
        self._view.bind_line_changed(self._on_line_changed)
        self._view.bind_frame_navigation(self._on_navigate_frame)

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
            roi = self._view.get_roi_coords()
            line = self._view.get_line_coords()
            if self._integration.is_calibrated:
                self._run_integration(current_frame)
            elif line is not None:
                self._run_line_integration(current_frame, *line)
            elif roi is not None:
                self._run_roi_fallback(current_frame, *roi)
            else:
                self._run_full_image_fallback(current_frame)
        except Exception:
            _log.exception("Error in _on_new_frame_gui - this might cause frames to stop updating")

    def _on_load_poni(self, poni_path: Path) -> None:
        """Load a .poni calibration file and wire pixel-level d-spacing / 2θ overlays."""
        if not HAS_PYFAI:
            wx.MessageBox("pyFAI is not installed.", "Missing Dependency", wx.OK | wx.ICON_ERROR)
            return
        try:
            self._integration.load_poni(poni_path)
        except Exception as exc:
            _log.exception("Failed to load .poni file %s", poni_path)
            wx.MessageBox(f"Failed to load .poni file:\n{exc}", "Error", wx.OK | wx.ICON_ERROR)
            return

        self._view.set_poni_label(poni_path.name, success=True)
        self._view.set_d_spacing_func(self._integration.compute_d_spacing)
        self._view.set_two_theta_func(self._integration.compute_two_theta)

    def _on_roi_cleared(self) -> None:
        """Show the full-image plot when the ROI or line is cleared."""
        current_frame = self._view.current_frame
        if current_frame is None:
            return
        if self._integration.is_calibrated:
            self._run_integration(current_frame)
        else:
            self._run_full_image_fallback(current_frame)

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
        elif line is not None:
            self._run_line_integration(current_frame, *line)
        elif roi is not None:
            self._run_roi_fallback(current_frame, *roi)

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
        self._view.set_integration_data(xs, ys, x_label)

    def _on_load_file(self, filepath: Path) -> None:
        """Load an image file and display it; disable live updates on success."""
        suffix = filepath.suffix.lower()
        try:
            if suffix in (".h5", ".hdf5"):
                frame = self._image_loader.load_hdf5(filepath)
            else:
                wx.MessageBox(f"Unsupported file format: {suffix}", "Error", wx.OK | wx.ICON_ERROR)
                return
        except ImportError as exc:
            wx.MessageBox(str(exc), "Missing Dependency", wx.OK | wx.ICON_ERROR)
            return
        except Exception as exc:
            _log.exception("Failed to load image file %s", filepath)
            wx.MessageBox(f"Error loading file:\n{exc}", "Error", wx.OK | wx.ICON_ERROR)
            return

        self._view.display_frame(frame)
        self._view.reset_view()
        self._view.set_live_updates(False)
        self._run_full_frame_integration(frame)

        frame_count = self._image_loader.frame_count
        self._view.set_frame_navigation(frame_count, 0)

    def _on_navigate_frame(self, index: int) -> None:
        """Load and display the requested frame index from the current HDF5 file."""
        try:
            frame = self._image_loader.load_hdf5_frame(index)
        except Exception as exc:
            _log.exception("Failed to load frame %d", index)
            wx.MessageBox(f"Error loading frame {index}:\n{exc}", "Error", wx.OK | wx.ICON_ERROR)
            return
        self._view.display_frame(frame)
        self._run_full_frame_integration(frame)

    def _on_roi_changed(self, x1: int | None, y1: int | None, x2: int | None, y2: int | None) -> None:
        """React to an ROI draw or clear event from the canvas."""
        current_frame = self._view.current_frame
        if current_frame is None:
            self._view.clear_integration_plot()
            return
        if x1 is None or y1 is None or x2 is None or y2 is None:
            if self._integration.is_calibrated:
                self._run_integration(current_frame)
            else:
                self._run_full_image_fallback(current_frame)
            return
        if self._integration.is_calibrated:
            self._run_integration(current_frame)
        else:
            self._run_roi_fallback(current_frame, x1, y1, x2, y2)

    def _on_line_changed(self, x1: int, y1: int, x2: int, y2: int) -> None:
        """React to a line ROI committed via Alt+click on the canvas."""
        current_frame = self._view.current_frame
        if current_frame is None:
            return
        if self._integration.is_calibrated:
            self._run_integration(current_frame)
        else:
            self._run_line_integration(current_frame, x1, y1, x2, y2)

    def _run_full_frame_integration(self, frame: np.ndarray) -> None:
        """Integrate respecting any active ROI/line, or fall back to the full image."""
        roi = self._view.get_roi_coords()
        line = self._view.get_line_coords()
        if self._integration.is_calibrated:
            self._run_integration(frame)
        elif line is not None:
            self._run_line_integration(frame, *line)
        elif roi is not None:
            self._run_roi_fallback(frame, *roi)
        else:
            self._run_full_image_fallback(frame)

    def _run_full_image_fallback(self, frame: np.ndarray) -> None:
        """Column-sum the full image when no poni is loaded."""
        h, w = frame.shape[:2]
        img = frame.mean(axis=2) if frame.ndim == 3 else frame
        ys = img.sum(axis=0).astype(np.float64)
        xs = np.arange(w, dtype=np.float64)
        self._view.set_integration_data(xs, ys, "Pixel")

    def _run_roi_fallback(self, frame: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> None:
        """Compute column-sum integration over the ROI and push results to the view."""
        h, w = frame.shape[:2]
        x1c = max(0, min(x1, w - 1))
        x2c = max(x1c + 1, min(x2, w))
        y1c = max(0, min(y1, h - 1))
        y2c = max(y1c + 1, min(y2, h))
        roi = frame[y1c:y2c, x1c:x2c].astype(np.float64)
        if roi.ndim == 3:
            roi = roi.mean(axis=2)
        ys = roi.sum(axis=0)
        xs = np.arange(x1c, x1c + len(ys), dtype=np.float64)
        self._view.set_integration_data(xs, ys, "Pixel")

    def _run_line_integration(self, frame: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> None:
        """Extract a line profile along the given pixel coordinates."""
        length = int(np.hypot(x2 - x1, y2 - y1))
        if length < 2:
            return
        xs_px = np.linspace(x1, x2, length)
        ys_px = np.linspace(y1, y2, length)
        h, w = frame.shape[:2]
        xi = np.clip(xs_px.astype(int), 0, w - 1)
        yi = np.clip(ys_px.astype(int), 0, h - 1)
        profile = frame[yi, xi].astype(np.float64)
        xs = np.arange(length, dtype=np.float64)
        self._view.set_integration_data(xs, profile, "Pixel")
