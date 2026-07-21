#!/usr/bin/env python
"""
Model for pyFAI azimuthal integration and d-spacing computation.
"""

import logging
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

_log = logging.getLogger(__name__)

try:
    import pyFAI

    HAS_PYFAI = True
except ImportError:
    HAS_PYFAI = False

__all__ = ["IntegrationModel", "HAS_PYFAI"]


def _smooth_bruckner(y: np.ndarray, smooth_points: int, iterations: int) -> np.ndarray:
    """Iterative Bruckner background smoothing — pure numpy, no extra deps."""
    N = max(1, smooth_points)
    N_d = y.size
    yp = np.empty(N_d + 2 * N)
    yp[:N] = y[0]
    yp[N : N + N_d] = y
    yp[N + N_d :] = y[-1]
    y_avg = yp.mean()
    y_min = yp.min()
    yp[yp > y_avg + 2.0 * (y_avg - y_min)] = y_avg + 2.0 * (y_avg - y_min)
    wsize = float(2 * N + 1)
    for _ in range(iterations):
        win_avg = yp[: 2 * N + 1].mean()
        for i in range(N, N_d - N - 1):
            if yp[i] > win_avg:
                y_new = win_avg
                win_avg += ((win_avg - yp[i]) + (yp[i + N + 1] - yp[i - N])) / wsize
                yp[i] = y_new
            else:
                win_avg += (yp[i + N + 1] - yp[i - N]) / wsize
    return yp[N : N + N_d]

UNIT_LABELS: dict[str, str] = {
    "2th_deg": "2θ (°)",
    "q_nm^-1": "q (nm⁻¹)",
    "q_A^-1": "Q (Å⁻¹)",
    "d_A": "d (Å)",
}


@dataclass()
class IntegrationModel:
    """Handles pyFAI calibration loading, azimuthal integration, and d-spacing computation."""

    _ai: "pyFAI.AzimuthalIntegrator | None" = field(init=False, compare=False, repr=False, default=None)
    _poni_path: Path | None = field(init=False, compare=False, repr=False, default=None)
    _tth_rad_array: np.ndarray | None = field(init=False, compare=False, repr=False, default=None)
    _wavelength_angstrom: float | None = field(init=False, compare=False, repr=False, default=None)

    _bkg_enabled: bool = field(init=False, compare=False, repr=False, default=False)
    _bkg_smooth_width: float = field(init=False, compare=False, repr=False, default=0.1)
    _bkg_iterations: int = field(init=False, compare=False, repr=False, default=50)
    _bkg_cheb_order: int = field(init=False, compare=False, repr=False, default=50)
    _bkg_roi: "list[float] | None" = field(init=False, compare=False, repr=False, default=None)

    _mask_above: "float | None" = field(init=False, compare=False, repr=False, default=None)
    _mask_below: "float | None" = field(init=False, compare=False, repr=False, default=None)

    @property
    def is_calibrated(self) -> bool:
        """Returns True if a calibration file has been loaded."""
        return self._ai is not None

    @property
    def poni_path(self) -> Path | None:
        """Returns the path of the loaded .poni file, or None."""
        return self._poni_path

    def load_poni(self, poni_path: Path) -> None:
        """Loads a pyFAI .poni calibration file."""
        if not HAS_PYFAI:
            raise ImportError("pyFAI is not installed.")

        self._ai = pyFAI.load(str(poni_path))
        self._poni_path = poni_path
        self._tth_rad_array = np.ascontiguousarray(self._ai.center_array(unit="2th_rad"))
        self._wavelength_angstrom = float(self._ai.wavelength) * 1e10

    @property
    def has_background(self) -> bool:
        return self._bkg_enabled

    def enable_background(
        self,
        smooth_width: float = 0.1,
        iterations: int = 50,
        cheb_order: int = 50,
    ) -> None:
        self._bkg_enabled = True
        self._bkg_smooth_width = smooth_width
        self._bkg_iterations = iterations
        self._bkg_cheb_order = cheb_order

    def disable_background(self) -> None:
        self._bkg_enabled = False

    def set_bkg_roi(self, x_min: float, x_max: float) -> None:
        self._bkg_roi = [x_min, x_max]

    def clear_bkg_roi(self) -> None:
        self._bkg_roi = None

    def apply_background(
        self, xs: np.ndarray, ys: np.ndarray
    ) -> "tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]":
        """Return (sub_xs, sub_ys, bkg_xs, bkg_ys) after background subtraction.

        The background is computed within the ROI (full range if no ROI is set).
        """
        if self._bkg_roi is not None:
            x_min, x_max = self._bkg_roi
            mask = (xs >= x_min) & (xs <= x_max)
            xr = xs[mask]
            yr = ys[mask]
        else:
            xr, yr = xs.copy(), ys.copy()

        if len(xr) < 4:
            return xr, yr, xr, np.zeros_like(yr)

        dx = xr[1] - xr[0]
        smooth_points = max(1, int(abs(self._bkg_smooth_width) / dx)) if dx > 0 else 1
        y_smooth = _smooth_bruckner(yr, smooth_points, self._bkg_iterations)

        x_cheb = 2.0 * (xr - xr[0]) / (xr[-1] - xr[0]) - 1.0
        try:
            order = min(self._bkg_cheb_order, len(xr) - 1)
            cheb_params = np.polynomial.chebyshev.chebfit(x_cheb, y_smooth, order)
            bkg_ys = np.polynomial.chebyshev.chebval(x_cheb, cheb_params)
        except Exception:
            bkg_ys = y_smooth

        return xr, yr - bkg_ys, xr, bkg_ys

    def set_mask_thresholds(self, above: "float | None", below: "float | None") -> None:
        """Set pixel intensity thresholds for masking. None disables that threshold."""
        self._mask_above = above
        self._mask_below = below

    def apply_threshold_mask(self, frame_2d: np.ndarray) -> np.ndarray:
        """Zero out masked pixels in a 2D frame copy and return it. Returns original if no thresholds set."""
        if self._mask_above is None and self._mask_below is None:
            return frame_2d
        out = frame_2d.copy()
        if self._mask_above is not None:
            out[frame_2d >= self._mask_above] = 0
        if self._mask_below is not None:
            out[frame_2d <= self._mask_below] = 0
        return out

    def get_threshold_mask(self, frame_2d: np.ndarray) -> "np.ndarray | None":
        """Return uint8 mask (1=masked) for current thresholds on frame_2d, or None if no thresholds."""
        if self._mask_above is None and self._mask_below is None:
            return None
        mask = np.zeros(frame_2d.shape, dtype=np.uint8)
        if self._mask_above is not None:
            mask |= (frame_2d >= self._mask_above).astype(np.uint8)
        if self._mask_below is not None:
            mask |= (frame_2d <= self._mask_below).astype(np.uint8)
        return mask

    def _build_mask(self, frame: np.ndarray, roi: "tuple[int, int, int, int] | None") -> "np.ndarray | None":
        """Return a uint8 mask (1 = masked) combining threshold and ROI constraints, or None."""
        mask = None

        if self._mask_above is not None or self._mask_below is not None:
            mask = np.zeros(frame.shape, dtype=np.uint8)
            if self._mask_above is not None:
                mask |= (frame >= self._mask_above).astype(np.uint8)
            if self._mask_below is not None:
                mask |= (frame <= self._mask_below).astype(np.uint8)

        if roi is not None:
            x1, y1, x2, y2 = roi
            h, w = frame.shape
            roi_mask = np.ones(frame.shape, dtype=np.uint8)
            roi_mask[max(0, y1) : min(h, y2), max(0, x1) : min(w, x2)] = 0
            mask = roi_mask if mask is None else (mask | roi_mask)

        return mask

    def integrate1d(
        self,
        frame: np.ndarray,
        npt: int,
        unit: str,
        roi: tuple[int, int, int, int] | None = None,
    ) -> tuple[np.ndarray, np.ndarray, str]:
        """Runs pyFAI azimuthal integration."""
        if self._ai is None:
            raise RuntimeError("No calibration loaded. Call load_poni() first.")

        mask = self._build_mask(frame, roi)

        result = self._ai.integrate1d(
            frame.astype(np.float32),
            npt,
            mask=mask,
            unit=unit,
            correctSolidAngle=True,
        )

        xs = np.array(result.radial)
        ys = np.array(result.intensity)
        x_label = UNIT_LABELS.get(unit, unit)
        return xs, ys, x_label

    def integrate1d_line(
        self,
        frame: np.ndarray,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        unit: str = "2th_deg",
    ) -> tuple[np.ndarray, np.ndarray, str]:
        """Extracts the intensity profile along a line between two pixels."""
        h, w = frame.shape[:2]
        length = math.hypot(x2 - x1, y2 - y1)
        npt = max(2, int(round(length)))

        ts = np.linspace(0.0, 1.0, npt)
        xs_f = x1 + ts * (x2 - x1)
        ys_f = y1 + ts * (y2 - y1)

        xi = np.clip(xs_f, 0, w - 1)
        yi = np.clip(ys_f, 0, h - 1)

        xi0 = np.floor(xi).astype(int)
        yi0 = np.floor(yi).astype(int)
        xi1 = np.clip(xi0 + 1, 0, w - 1)
        yi1 = np.clip(yi0 + 1, 0, h - 1)
        fx = xi - xi0
        fy = yi - yi0

        img = frame.mean(axis=2).astype(np.float64) if frame.ndim == 3 else frame.astype(np.float64)
        wx_00 = (1 - fx) * (1 - fy)
        wx_10 = fx * (1 - fy)
        wx_01 = (1 - fx) * fy
        wx_11 = fx * fy
        intensities = (
            img[yi0, xi0] * wx_00
            + img[yi0, xi1] * wx_10
            + img[yi1, xi0] * wx_01
            + img[yi1, xi1] * wx_11
        )

        if self._ai is not None:
            try:
                radial_map = self._ai.center_array(unit=unit)
                radial_vals = (
                    radial_map[yi0, xi0] * wx_00
                    + radial_map[yi0, xi1] * wx_10
                    + radial_map[yi1, xi0] * wx_01
                    + radial_map[yi1, xi1] * wx_11
                )
                x_label = UNIT_LABELS.get(unit, unit)
                return radial_vals, intensities, x_label
            except Exception:
                _log.exception("Failed to map radial coordinates for unit=%s", unit)

        pixel_dist = ts * length
        return pixel_dist, intensities, "Pixel"

    def compute_two_theta(self, ix: int, iy: int) -> float | None:
        """Returns 2θ in degrees for a given image pixel, or None on error."""
        arr = self._tth_rad_array
        if arr is None:
            return None
        h, w = arr.shape
        if not (0 <= iy < h and 0 <= ix < w):
            return None
        tth_rad = arr[iy, ix]
        if tth_rad <= 0:
            return None
        return math.degrees(tth_rad)

    def compute_d_spacing(self, ix: int, iy: int) -> float | None:
        """Returns d-spacing in Angstroms for a given image pixel, or None on error."""
        arr = self._tth_rad_array
        wl = self._wavelength_angstrom
        if arr is None or wl is None:
            return None
        h, w = arr.shape
        if not (0 <= iy < h and 0 <= ix < w):
            return None
        tth = arr[iy, ix]
        if tth <= 0:
            return None
        return wl / (2.0 * math.sin(tth * 0.5))
