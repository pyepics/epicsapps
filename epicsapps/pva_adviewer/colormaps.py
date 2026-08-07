#!/usr/bin/env python
"""
Provides custom colormaps for the PVA adviewer.
"""

from vispy.color.colormap import Colormap
from wxmplot.colors import register_colormap

__all__ = ["register_colormaps"]


def register_colormaps() -> None:
    """Register custom colormaps with the wxmplot registry."""
    register_colormap("grays_reverse", Colormap(["white", "black"]))
