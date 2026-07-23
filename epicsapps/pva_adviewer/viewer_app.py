#!/usr/bin/env python
"""
wx.App for the PVA adviewer.
"""

import logging
import sys
from contextlib import suppress
from pathlib import Path
from typing import Optional

import wx
from wxutils import ColorTheme, FlatMenuBar, FlatMessageDialog

from epicsapps.utils import get_configfolder, read_recents_file, write_recents_file
from epicsapps.pva_adviewer.ad_viewer_controller import ADViewerController
from epicsapps.pva_adviewer.ad_viewer_model import ADViewerModel
from epicsapps.pva_adviewer.ad_viewer_view import ADViewerView
from epicsapps.pva_adviewer.connect_dialog import PVAConnectDialog
from epicsapps.pva_adviewer.image_loader_model import ImageLoaderModel
from epicsapps.pva_adviewer.pva_config import PVAConfig, CONFFILE, RECENT_PREFIXES_FILE, RECENT_CONFIGS_FILE
from epicsapps.pva_adviewer.theme import AppTheme

__all__ = ["PVAViewerApp"]

_log = logging.getLogger(__name__)

_DEFAULT_PVA_SUFFIX = "Pva1:Image"


def _build_pva_pv(prefix: str, pva_suffix: str = _DEFAULT_PVA_SUFFIX) -> str:
    """Combine detector prefix and PVA suffix into a full PV name."""
    if not prefix.endswith(":"):
        prefix = prefix + ":"
    return prefix + pva_suffix


class _PVAViewerFrame(wx.Frame):
    """Top-level frame that hosts the ADViewerView panel."""

    def __init__(self, pv_name: str = "", config: "PVAConfig | None" = None) -> None:
        cfg = config.config if config is not None else {}
        title = cfg.get("title") or "PVA Viewer"
        super().__init__(None, title=title, size=(1200, 800))

        self._ad_model = ADViewerModel()
        self._image_loader = ImageLoaderModel()
        self._view = ADViewerView(self)
        self._controller = ADViewerController(
            ad_model=self._ad_model,
            image_loader=self._image_loader,
            view=self._view,
        )

        self._menu_check_integration = None
        self._menu_check_controls = None
        self._menu_check_fps = None
        flat_menubar = self._build_menu()

        sizer = wx.BoxSizer(wx.VERTICAL)
        if flat_menubar is not None:
            sizer.Add(flat_menubar, 0, wx.EXPAND)
        sizer.Add(self._view, 1, wx.EXPAND)
        self.SetSizer(sizer)
        self.SetBackgroundColour(wx.BLACK)

        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.Show()

        self._current_pv_name = pv_name
        self._apply_config(cfg)

        if pv_name:
            self._controller.subscribe(pv_name)

    def _build_menu(self) -> "FlatMenuBar | None":
        """Build the menu bar. Returns a FlatMenuBar to add to the sizer, or None on macOS (native menubar used)."""
        import sys
        if sys.platform == "darwin":
            menubar = wx.MenuBar()
            file_menu = wx.Menu()
            load_item = file_menu.Append(wx.ID_ANY, "Load Config File…\tCtrl+O")
            save_item = file_menu.Append(wx.ID_ANY, "Save Image…\tCtrl+S")
            copy_item = file_menu.Append(wx.ID_ANY, "Copy Image\tCtrl+C")
            menubar.Append(file_menu, "&File")
            view_menu = wx.Menu()
            self._menu_check_integration = view_menu.AppendCheckItem(wx.ID_ANY, "Show Integration Plot\tCtrl+I")
            self._menu_check_integration.Check(True)
            self._menu_check_controls = view_menu.AppendCheckItem(wx.ID_ANY, "Show PV Controls\tCtrl+K")
            self._menu_check_controls.Check(True)
            self._menu_check_fps = view_menu.AppendCheckItem(wx.ID_ANY, "Show FPS\tCtrl+F")
            self._menu_check_fps.Check(False)
            menubar.Append(view_menu, "&View")
            self.SetMenuBar(menubar)
            self.Bind(wx.EVT_MENU, lambda _e: self._on_load_config(), load_item)
            self.Bind(wx.EVT_MENU, lambda _e: self._on_save_image(), save_item)
            self.Bind(wx.EVT_MENU, lambda _e: self._on_copy_image(), copy_item)
            self.Bind(wx.EVT_MENU, lambda _e: self._on_toggle_integration_plot(), self._menu_check_integration)
            self.Bind(wx.EVT_MENU, lambda _e: self._on_toggle_pv_controls(), self._menu_check_controls)
            self.Bind(wx.EVT_MENU, lambda _e: self._on_toggle_fps(), self._menu_check_fps)
            return None

        bar = FlatMenuBar(self)
        bar.AppendMenu(
            title="File",
            items=["Load Config File…", "Save Image…", "Copy Image"],
            shortcuts=["Ctrl+O", "Ctrl+S", "Ctrl+C"],
            callbacks=[self._on_load_config, self._on_save_image, self._on_copy_image],
        )
        bar.AppendMenu(
            title="View",
            items=["Toggle Integration Plot", "Toggle PV Controls", "Toggle FPS"],
            shortcuts=["Ctrl+I", "Ctrl+K", "Ctrl+F"],
            callbacks=[self._on_toggle_integration_plot, self._on_toggle_pv_controls, self._on_toggle_fps],
        )
        # FlatMenuBar shows shortcut hints but doesn't bind keys
        _load_id = wx.NewIdRef()
        _save_id = wx.NewIdRef()
        _copy_id = wx.NewIdRef()
        _toggle_id = wx.NewIdRef()
        _controls_id = wx.NewIdRef()
        _fps_id = wx.NewIdRef()
        self.Bind(wx.EVT_MENU, lambda _e: self._on_load_config(), _load_id)
        self.Bind(wx.EVT_MENU, lambda _e: self._on_save_image(), _save_id)
        self.Bind(wx.EVT_MENU, lambda _e: self._on_copy_image(), _copy_id)
        self.Bind(wx.EVT_MENU, lambda _e: self._on_toggle_integration_plot(), _toggle_id)
        self.Bind(wx.EVT_MENU, lambda _e: self._on_toggle_pv_controls(), _controls_id)
        self.Bind(wx.EVT_MENU, lambda _e: self._on_toggle_fps(), _fps_id)
        self.SetAcceleratorTable(wx.AcceleratorTable([
            wx.AcceleratorEntry(wx.ACCEL_CTRL, ord('O'), _load_id),
            wx.AcceleratorEntry(wx.ACCEL_CTRL, ord('S'), _save_id),
            wx.AcceleratorEntry(wx.ACCEL_CTRL, ord('C'), _copy_id),
            wx.AcceleratorEntry(wx.ACCEL_CTRL, ord('I'), _toggle_id),
            wx.AcceleratorEntry(wx.ACCEL_CTRL, ord('K'), _controls_id),
            wx.AcceleratorEntry(wx.ACCEL_CTRL, ord('F'), _fps_id),
        ]))
        return bar

    def _apply_config(self, cfg: dict) -> None:
        show_plot = bool(cfg.get("show_integration_plot", True))
        if self._menu_check_integration is not None:
            self._menu_check_integration.Check(show_plot)
        self._view.set_integration_plot_visible(show_plot)

        show_controls = bool(cfg.get("show_pv_controls", True))
        if self._menu_check_controls is not None:
            self._menu_check_controls.Check(show_controls)
        self._view.set_pv_controls_visible(show_controls)

        pixel_size = cfg.get("pixel_size")
        if pixel_size is not None:
            try:
                self._view._apply_pixel_size(float(pixel_size))
            except (ValueError, TypeError):
                pass

        colormap = cfg.get("colormap")
        if colormap:
            try:
                self._view._apply_colormap(colormap)
            except Exception:
                pass

        poni_file = cfg.get("poni_file")
        if poni_file:
            path = Path(poni_file)
            if path.exists():
                wx.CallAfter(self._controller._on_load_poni, path)

        prefix = cfg.get("prefix", "")
        controls = cfg.get("epics_controls") or []
        if prefix and controls:
            default_width = int(cfg.get("control_width") or 140)
            default_fontsize = int(cfg.get("control_fontsize") or 12)
            columns = max(1, int(cfg.get("control_columns") or 1))
            wx.CallAfter(self._view.set_pv_controls, prefix, controls, default_width, default_fontsize, columns)

    def _on_save_image(self) -> None:
        wildcard = "PNG files (*.png)|*.png|TIFF files (*.tiff;*.tif)|*.tiff;*.tif"
        with wx.FileDialog(
            self,
            "Save image",
            wildcard=wildcard,
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
            defaultFile="pvaviewer_capture.png",
        ) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            path = Path(dlg.GetPath())

        ext = path.suffix.lower()
        if ext in (".tiff", ".tif"):
            bmp_type = wx.BITMAP_TYPE_TIFF
        else:
            if path.suffix == "":
                path = path.with_suffix(".png")
            bmp_type = wx.BITMAP_TYPE_PNG

        bmp = self._view.capture()
        if not bmp.SaveFile(str(path), bmp_type):
            FlatMessageDialog(self, f"Failed to save image to:\n{path}", "Save Error").ShowModal()

    def _on_copy_image(self) -> None:
        bmp = self._view.capture()
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.BitmapDataObject(bmp))
            wx.TheClipboard.Close()

    def _on_load_config(self) -> None:
        with wx.FileDialog(
            self,
            "Load PVA Viewer config file",
            wildcard="YAML files (*.yaml)|*.yaml|All files (*.*)|*.*",
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dlg:
            if dlg.ShowModal() != wx.ID_OK:
                return
            config_file = dlg.GetPath()

        config = PVAConfig(config_file)
        cfg = config.config

        prefix = cfg.get("prefix", "")
        pva_suffix = cfg.get("pva_suffix") or _DEFAULT_PVA_SUFFIX
        new_pv_name = _build_pva_pv(prefix, pva_suffix) if prefix else ""

        title = cfg.get("title") or "PVA Viewer"
        self.SetTitle(title)

        self._apply_config(cfg)

        if new_pv_name and new_pv_name != self._current_pv_name:
            self._controller.unsubscribe()
            self._controller.subscribe(new_pv_name)
            self._current_pv_name = new_pv_name

    def _on_toggle_integration_plot(self) -> None:
        if self._menu_check_integration is not None:
            visible = self._menu_check_integration.IsChecked()
        else:
            visible = not self._view._integration_plot_visible
        self._view.set_integration_plot_visible(visible)

    def _on_toggle_pv_controls(self) -> None:
        if self._menu_check_controls is not None:
            visible = self._menu_check_controls.IsChecked()
        else:
            visible = not self._view._pv_controls_visible
        self._view.set_pv_controls_visible(visible)

    def _on_toggle_fps(self) -> None:
        if self._menu_check_fps is not None:
            visible = self._menu_check_fps.IsChecked()
        else:
            visible = not self._view._show_fps
        self._view.set_fps_visible(visible)

    def _on_close(self, event: wx.CloseEvent) -> None:
        """Tear down PVA resources before the frame is destroyed."""
        self._controller.shutdown()
        event.Skip()


class PVAViewerApp(wx.App):
    """Standalone wx.App for the PVA Viewer."""

    def __init__(
        self,
        prefix: str = "",
        pv_name: str = "",
        config_file: str = "",
        dark: Optional[ColorTheme] = None,
        light: Optional[ColorTheme] = None,
    ) -> None:
        # Accept either a raw prefix or a full pv_name for backwards compat
        self._prefix = prefix
        self._pv_name = pv_name
        self._config_file = config_file
        self._dark = dark
        self._light = light
        super().__init__(False)

    def OnInit(self) -> bool:
        self.SetAppDisplayName("PVA Viewer")

        if sys.platform == "darwin":
            with suppress(Exception):
                from Foundation import NSBundle
                info = NSBundle.mainBundle().infoDictionary()
                if info is not None:
                    info["CFBundleName"] = "PVA Viewer"

        AppTheme(dark=self._dark, light=self._light)

        pv_name = self._pv_name
        config: PVAConfig | None = None

        if pv_name or self._prefix:
            # Programmatic path (e.g. crystalsweep): skip dialog, use defaults
            if not pv_name:
                pv_name = _build_pva_pv(self._prefix)
            if self._config_file:
                config = PVAConfig(self._config_file)
        else:
            pv_name, config = self._run_connect_dialog()
            if pv_name is None:
                return False

        _PVAViewerFrame(pv_name=pv_name, config=config)
        return True

    def _run_connect_dialog(self) -> "tuple[str | None, PVAConfig | None]":
        recent_prefixes = read_recents_file(RECENT_PREFIXES_FILE)
        recent_configs = read_recents_file(RECENT_CONFIGS_FILE)

        dlg = PVAConnectDialog(parent=None, recent_prefixes=recent_prefixes, recent_configs=recent_configs)
        response = dlg.get_response()
        dlg.Destroy()

        if not response.ok:
            return None, None

        if response.mode == "prefix":
            prefix = response.prefix
            if not prefix.endswith(":"):
                prefix = prefix + ":"
            pva_suffix = _DEFAULT_PVA_SUFFIX
            pv_name = prefix + pva_suffix

            safe = prefix.rstrip(":").replace(":", "_").replace("/", "_")
            config_path = Path(get_configfolder()) / f"pvaviewer_{safe}.yaml"
            if not config_path.exists():
                config = PVAConfig()
                config.config["prefix"] = prefix
                config.write(str(config_path))
            else:
                config = PVAConfig(str(config_path))

            _update_recents(RECENT_PREFIXES_FILE, recent_prefixes, prefix)
            _update_recents(RECENT_CONFIGS_FILE, recent_configs, str(config_path))
            return pv_name, config

        else:
            config_file = response.config_file
            if not config_file or not Path(config_file).exists():
                FlatMessageDialog(None, "Config file not found.", "Error").ShowModal()
                return None, None

            config = PVAConfig(config_file)
            cfg = config.config
            prefix = cfg.get("prefix", "")
            if not prefix:
                FlatMessageDialog(None, "Config file does not specify a prefix.", "Error").ShowModal()
                return None, None

            pva_suffix = cfg.get("pva_suffix") or _DEFAULT_PVA_SUFFIX
            pv_name = _build_pva_pv(prefix, pva_suffix)

            _update_recents(RECENT_CONFIGS_FILE, recent_configs, config_file)
            return pv_name, config


def _update_recents(fname: str, current: list[str], new_entry: str) -> None:
    updated = [new_entry] + [x for x in current if x != new_entry]
    write_recents_file(fname, updated[:20])


def run_pvaviewer(
    prefix: str = "",
    pv_name: str = "",
    config_file: str = "",
    dark: Optional[ColorTheme] = None,
    light: Optional[ColorTheme] = None,
) -> None:
    """Entry point called by the epicsapps CLI dispatcher."""
    if sys.platform == "win32":
        try:
            wx.App.SetDPIAwareness(wx.DPI_AWARENESS_CTX_PER_MONITOR_AWARE_V2)
        except AttributeError:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(2)

    app = PVAViewerApp(prefix=prefix, pv_name=pv_name, config_file=config_file, dark=dark, light=light)
    app.MainLoop()
