#!/usr/bin/env python
"""
Model for loading detector images from HDF5, TIFF, CBF, and common image files.
"""

from dataclasses import dataclass, field
from pathlib import Path
import os

import numpy as np

# Suppress h5py plugin path errors on macOS when using wheels with hardcoded build paths
os.environ.setdefault('HDF5_PLUGIN_PATH', '')

try:
    import h5py
    HAS_H5PY = True
except ImportError:
    HAS_H5PY = False

# Import hdf5plugin to enable compression codecs (blosc, lz4, bz2, etc.)
try:
    import hdf5plugin  # noqa: F401
    HAS_HDF5PLUGIN = True
except ImportError:
    HAS_HDF5PLUGIN = False

try:
    import fabio
    HAS_FABIO = True
except ImportError:
    HAS_FABIO = False

try:
    from PIL import Image as _PilImage
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

__all__ = ["ImageLoaderModel", "HAS_H5PY", "HAS_FABIO", "HAS_PIL"]

_FABIO_SUFFIXES = {".tif", ".tiff", ".cbf", ".edf", ".img", ".mar3450", ".mar2300"}
_PIL_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp"}


@dataclass()
class ImageLoaderModel:
    """Handles loading detector images from HDF5, fabio, and common image files."""

    _loaded_file: Path | None = field(init=False, compare=False, repr=False, default=None)
    _frame_type: str = field(init=False, compare=False, repr=False, default="none")
    _frame_count: int = field(init=False, compare=False, repr=False, default=0)

    # HDF5-specific
    _hdf5_dataset_path: str | None = field(init=False, compare=False, repr=False, default=None)
    _hdf5_filepath: Path | None = field(init=False, compare=False, repr=False, default=None)

    # fabio-specific
    _fabio_filepath: Path | None = field(init=False, compare=False, repr=False, default=None)

    @property
    def frame_count(self) -> int:
        """Number of navigable frames in the current file (0 for single-frame files)."""
        return self._frame_count

    @property
    def loaded_file(self) -> Path | None:
        """Returns the path of the currently loaded file."""
        return self._loaded_file

    def load_hdf5(self, filepath: Path) -> np.ndarray:
        """Loads the first 2D image from an HDF5 file and caches multi-frame metadata."""
        if not HAS_H5PY:
            raise ImportError("h5py is not installed. Cannot load HDF5 files.")

        self._frame_count = 0
        self._hdf5_dataset_path = None
        self._hdf5_filepath = None

        f = None
        try:
            f = h5py.File(filepath, "r")
            dataset = self._find_dataset(f)

            if dataset is None:
                raise ValueError(
                    "Could not find image data in HDF5 file.\n\nTried common dataset paths: data, images, entry/data/data, exchange/data, entry/instrument/detector/data"
                )

            if len(dataset.shape) == 2:
                frame = dataset[:]
            elif len(dataset.shape) == 3:
                self._frame_count = dataset.shape[0]
                self._hdf5_dataset_path = dataset.name
                self._hdf5_filepath = filepath
                frame = dataset[0]
            else:
                raise ValueError(f"Unsupported data shape: {dataset.shape}\n\nExpected 2D or 3D array.")
        except OSError as e:
            error_msg = str(e).lower()
            if "can't find plugin" in error_msg or "plugin" in error_msg:
                raise ImportError(
                    f"HDF5 file may use compression requiring additional packages.\n\n"
                    f"Try installing: pip install hdf5plugin\n\n"
                    f"Original error: {e}"
                ) from e
            raise
        finally:
            if f is not None:
                try:
                    f.close()
                except Exception:
                    pass

        self._loaded_file = filepath
        self._frame_type = "hdf5"
        return frame.astype(np.float32)

    def load_hdf5_frame(self, index: int) -> np.ndarray:
        """Loads a specific frame by index from the currently open HDF5 file."""
        if self._hdf5_filepath is None or self._hdf5_dataset_path is None:
            raise ValueError("No multi-frame HDF5 file is currently loaded.")
        if not (0 <= index < self._frame_count):
            raise ValueError(f"Frame index {index} out of range [0, {self._frame_count}).")

        f = None
        try:
            f = h5py.File(self._hdf5_filepath, "r")
            frame = f[self._hdf5_dataset_path][index]
        except OSError as e:
            error_msg = str(e).lower()
            if "can't find plugin" in error_msg or "plugin" in error_msg:
                raise ImportError(
                    f"HDF5 file may use compression requiring additional packages.\n\n"
                    f"Try installing: pip install hdf5plugin\n\n"
                    f"Original error: {e}"
                ) from e
            raise
        finally:
            if f is not None:
                try:
                    f.close()
                except Exception:
                    pass

        return frame.astype(np.float32)


    def load_fabio(self, filepath: Path) -> np.ndarray:
        """Load a detector image using fabio (TIFF, CBF, EDF, etc.)."""
        if not HAS_FABIO:
            raise ImportError(
                "fabio is not installed. Cannot load this file format.\n\n"
                "Try: pip install fabio"
            )
        img = fabio.open(str(filepath))
        try:
            n = img.nframes
            frame = img.data
        finally:
            img.close()

        self._loaded_file = filepath
        self._frame_type = "fabio"
        self._fabio_filepath = filepath
        self._frame_count = n if n > 1 else 0
        return np.asarray(frame, dtype=np.float32)

    def load_fabio_frame(self, index: int) -> np.ndarray:
        """Load a specific frame by index from the current fabio file."""
        if self._fabio_filepath is None:
            raise ValueError("No fabio file is currently loaded.")
        if not (0 <= index < self._frame_count):
            raise ValueError(f"Frame index {index} out of range [0, {self._frame_count}).")
        img = fabio.open(str(self._fabio_filepath))
        try:
            frame = img.getframe(index).data
        finally:
            img.close()
        return np.asarray(frame, dtype=np.float32)

    def load_pillow(self, filepath: Path) -> np.ndarray:
        """Load a common image file (JPEG, PNG, BMP) using Pillow."""
        if not HAS_PIL:
            raise ImportError(
                "Pillow is not installed. Cannot load this file format.\n\n"
                "Try: pip install Pillow"
            )
        with _PilImage.open(filepath) as img:
            arr = np.array(img)
        self._loaded_file = filepath
        self._frame_type = "single"
        self._frame_count = 0
        return arr.astype(np.float32)

    def load_frame(self, index: int) -> np.ndarray:
        """Load a frame by index from whatever multi-frame file is currently open."""
        if self._frame_type == "hdf5":
            return self.load_hdf5_frame(index)
        if self._frame_type == "fabio":
            return self.load_fabio_frame(index)
        raise ValueError("No multi-frame file is currently loaded.")

    @staticmethod
    def _find_dataset(f: "h5py.File") -> "h5py.Dataset | None":
        """Searches an HDF5 file for the first suitable 2D+ dataset."""
        common_paths = [
            "data",
            "images",
            "entry/data/data",
            "exchange/data",
            "entry/instrument/detector/data",
        ]

        for name in common_paths:
            if name in f:
                return f[name]

        for key in f.keys():
            obj = f[key]
            if isinstance(obj, h5py.Dataset) and len(obj.shape) >= 2:
                return obj
            if isinstance(obj, h5py.Group):
                for subkey in obj.keys():
                    subobj = obj[subkey]
                    if isinstance(subobj, h5py.Dataset) and len(subobj.shape) >= 2:
                        return subobj

        return None
