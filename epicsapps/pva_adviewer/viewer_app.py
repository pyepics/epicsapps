#!/usr/bin/env python
"""
wx.App for the PVA adviewer.
"""

import logging
import sys
from typing import Optional

import wx
from wxutils import ColorTheme

from epicsapps.pva_adviewer.ad_viewer_controller import ADViewerController
from epicsapps.pva_adviewer.ad_viewer_model import ADViewerModel
from epicsapps.pva_adviewer.ad_viewer_view import ADViewerView
from epicsapps.pva_adviewer.image_loader_model import ImageLoaderModel
from epicsapps.pva_adviewer.theme import AppTheme

__all__ = ["PVAViewerApp"]

_log = logging.getLogger(__name__)


class _PVAViewerFrame(wx.Frame):
    """Top-level frame that hosts the ADViewerView panel."""

    def __init__(self, pv_name: str = "") -> None:
        super().__init__(None, title="PVA Viewer", size=(1200, 800))

        self._ad_model = ADViewerModel()
        self._image_loader = ImageLoaderModel()
        self._view = ADViewerView(self)
        self._controller = ADViewerController(
            ad_model=self._ad_model,
            image_loader=self._image_loader,
            view=self._view,
        )

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self._view, 1, wx.EXPAND)
        self.SetSizer(sizer)
        self.SetBackgroundColour(wx.BLACK)

        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.Show()

        if pv_name:
            self._controller.subscribe(pv_name)

    def _on_close(self, event: wx.CloseEvent) -> None:
        """Tear down PVA resources before the frame is destroyed."""
        self._controller.shutdown()
        event.Skip()


class PVAViewerApp(wx.App):
    """Standalone wx.App for the PVA Viewer."""

    def __init__(self, pv_name: str = "", dark: Optional[ColorTheme] = None, light: Optional[ColorTheme] = None) -> None:
        self._pv_name = pv_name
        self._dark = dark
        self._light = light
        super().__init__(False)

    def OnInit(self) -> bool:
        """Initialise wx, apply theme, prompt for PV name, then show the viewer frame."""
        AppTheme(dark=self._dark, light=self._light)
        pv_name = self._pv_name
        if not pv_name:
            dlg = wx.TextEntryDialog(
                None,
                "Enter PVA image PV name or detector prefix:\n(e.g., '13EIG2_9M:Pva1:Image' or just '13EIG2_9M:')",
                "PVA Viewer",
            )
            if dlg.ShowModal() == wx.ID_OK:
                pv_name = dlg.GetValue().strip()
            dlg.Destroy()
        
        # If user entered just a prefix (ends with :), auto-append Pva1:Image
        if pv_name and pv_name.endswith(":") and not pv_name.endswith(":Image"):
            pv_name = f"{pv_name}Pva1:Image"
            _log.info(f"Auto-expanded detector prefix to full PV name: {pv_name}")
        
        _PVAViewerFrame(pv_name=pv_name)
        return True


def run_pvaviewer(pv_name: str = "", dark: Optional[ColorTheme] = None, light: Optional[ColorTheme] = None) -> None:
    """Entry point called by the epicsapps CLI dispatcher."""
    if sys.platform == "win32":
        try:
            wx.App.SetDPIAwareness(wx.DPI_AWARENESS_CTX_PER_MONITOR_AWARE_V2)
        except AttributeError:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(2)

    app = PVAViewerApp(pv_name=pv_name, dark=dark, light=light)
    app.MainLoop()
