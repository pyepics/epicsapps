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

        mask = None
        if roi is not None:
            x1, y1, x2, y2 = roi
            h, w = frame.shape
            mask = np.ones(frame.shape, dtype=np.uint8)
            mask[max(0, y1) : min(h, y2), max(0, x1) : min(w, x2)] = 0

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
