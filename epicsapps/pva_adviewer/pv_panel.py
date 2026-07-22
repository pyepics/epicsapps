#!/usr/bin/env python
"""
EPICS PV control panel built from YAML config, styled with AppTheme.
"""

import wx
from epics import get_pv

from wxutils import FlatLabel, FlatPanel

from epicsapps.pva_adviewer.flat_pv_widgets import make_pv_widget
from epicsapps.pva_adviewer.theme import AppTheme

__all__ = ["PVControlPanel"]



def _parse_entry(entry: list, default_width: int, default_fontsize: int) -> tuple:
    """Unpack a control entry."""
    label = entry[0]
    pvname = entry[1]
    use_prefix = entry[2]
    dtype = entry[3]
    rsuff = entry[4] if len(entry) > 4 else False
    width = int(entry[5]) if len(entry) > 5 else default_width
    fontsize = int(entry[6]) if len(entry) > 6 else default_fontsize
    return label, pvname, use_prefix, dtype, rsuff, width, fontsize


class PVControlPanel(FlatPanel):
    """Rows of EPICS PV controls built from a list of config entries."""

    def __init__(
        self,
        parent: wx.Window,
        prefix: str,
        controls: list,
        default_width: int = 140,
        default_fontsize: int = 12,
        columns: int = 1,
    ) -> None:
        super().__init__(parent)  # FlatPanel handles background + darkdetect

        columns = max(1, columns)
        # Each column group is: label | control | readback
        sizer = wx.FlexGridSizer(cols=columns * 3, vgap=4, hgap=8)
        for col in range(columns):
            sizer.AddGrowableCol(col * 3 + 1, 1)

        for i, entry in enumerate(controls):
            label, pvname, use_prefix, dtype, rsuff, width, fontsize = _parse_entry(
                entry, default_width, default_fontsize
            )
            if use_prefix:
                pvname = prefix + pvname

            font = AppTheme.scaled_font(fontsize)
            pv = get_pv(pvname)
            ctrl_size = wx.Size(width, AppTheme.btn_h)

            lbl_w = FlatLabel(self, label=f"  {label}", font=font)

            ctrl = make_pv_widget(dtype, self, pv, ctrl_size, font)

            sizer.Add(lbl_w, 0, wx.ALIGN_CENTER_VERTICAL)
            sizer.Add(ctrl, 0, wx.ALIGN_CENTER_VERTICAL | wx.EXPAND)

            if rsuff and dtype not in ("pvenum", "pvenumbuttons", "pvfloat", "pvtctrl"):
                rbk_pv = get_pv(pvname + rsuff)
                rbk = make_pv_widget("pvtext", self, rbk_pv, ctrl_size, font)
                sizer.Add(rbk, 0, wx.ALIGN_CENTER_VERTICAL)
            else:
                sizer.Add((0, 0))

        # Pad remaining cells in the last row so the grid is complete
        remainder = len(controls) % columns
        if remainder:
            for _ in range(columns - remainder):
                sizer.Add((0, 0))
                sizer.Add((0, 0))
                sizer.Add((0, 0))

        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(sizer, 0, wx.EXPAND | wx.ALL, 6)
        self.SetSizer(outer)
        self.Fit()

