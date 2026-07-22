#!/usr/bin/env python
"""
Startup connect dialog for the PVA Viewer.
"""

from collections import namedtuple
from pathlib import Path

import wx
from wxutils import FlatButton, FlatRadioButton, FlatTextCtrl, FlatCombo, FlatPanel, FlatLabel

from epicsapps.pva_adviewer.theme import AppTheme, get_theme

__all__ = ["PVAConnectDialog"]

_YAML_WILDCARD = "YAML files (*.yaml)|*.yaml|All files (*.*)|*.*"

PVAConnectResponse = namedtuple("PVAConnectResponse", ("ok", "mode", "prefix", "config_file"))


def _lbl(parent: wx.Window, text: str, pt: int = 12) -> FlatLabel:
    return FlatLabel(parent, label=text, font=AppTheme.scaled_font(pt))


class PVAConnectDialog(wx.Dialog):
    """Startup dialog: connect by detector prefix or load a YAML config file."""

    def __init__(
        self,
        parent=None,
        recent_prefixes: "list[str] | None" = None,
        recent_configs: "list[str] | None" = None,
    ) -> None:
        super().__init__(parent, title="Connect to PVA Viewer", style=wx.DEFAULT_DIALOG_STYLE)

        self._mode = "prefix"
        self._recent_prefixes = [p for p in (recent_prefixes or []) if p]
        self._recent_configs = [c for c in (recent_configs or []) if Path(c).exists()]

        t = get_theme()
        self.SetBackgroundColour(t.background)

        panel = FlatPanel(self)

        self._rb_prefix = FlatRadioButton(panel, value=True)
        self._rb_file = FlatRadioButton(panel, value=False)
        self._rb_prefix.SetAction(lambda: self._set_mode("prefix"))
        self._rb_file.SetAction(lambda: self._set_mode("conffile"))

        mode_row = wx.BoxSizer(wx.HORIZONTAL)
        mode_row.Add(self._rb_prefix, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        mode_row.Add(_lbl(panel, "Detector Prefix"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 20)
        mode_row.Add(self._rb_file, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        mode_row.Add(_lbl(panel, "Config File"), 0, wx.ALIGN_CENTER_VERTICAL)

        self._prefix_panel = FlatPanel(panel)

        self._prefix_ctrl = FlatTextCtrl(
            self._prefix_panel,
            value=self._recent_prefixes[0] if self._recent_prefixes else "",
            placeholder="e.g. 13IDD_PG3:",
            size=wx.Size(380, AppTheme.btn_h),
        )

        prefix_sizer = wx.BoxSizer(wx.VERTICAL)
        prefix_sizer.Add(_lbl(self._prefix_panel, "Detector Prefix"), 0, wx.BOTTOM, 4)
        prefix_sizer.Add(self._prefix_ctrl, 0, wx.EXPAND | wx.BOTTOM, 4)

        if len(self._recent_prefixes) > 1:
            self._prefix_recent = FlatCombo(
                self._prefix_panel,
                choices=self._recent_prefixes[1:],
                size=wx.Size(380, AppTheme.btn_h),
            )
            self._prefix_recent.SetAction(lambda s: self._prefix_ctrl.SetValue(s))
            recent_row = wx.BoxSizer(wx.HORIZONTAL)
            recent_row.Add(_lbl(self._prefix_panel, "Recent:", pt=10), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
            recent_row.Add(self._prefix_recent, 1, wx.EXPAND)
            prefix_sizer.Add(recent_row, 0, wx.EXPAND)

        self._prefix_panel.SetSizer(prefix_sizer)

        self._file_panel = FlatPanel(panel)

        self._conf_ctrl = FlatTextCtrl(
            self._file_panel,
            value=self._recent_configs[0] if self._recent_configs else "",
            placeholder="path/to/config.yaml",
            size=wx.Size(300, AppTheme.btn_h),
        )
        browse_btn = FlatButton(self._file_panel, label="Browse…", font=AppTheme.btn_font())
        browse_btn.SetAction(self._on_browse)

        conf_input_row = wx.BoxSizer(wx.HORIZONTAL)
        conf_input_row.Add(self._conf_ctrl, 1, wx.EXPAND | wx.RIGHT, 8)
        conf_input_row.Add(browse_btn, 0, wx.ALIGN_CENTER_VERTICAL)

        file_sizer = wx.BoxSizer(wx.VERTICAL)
        file_sizer.Add(_lbl(self._file_panel, "Config File"), 0, wx.BOTTOM, 4)
        file_sizer.Add(conf_input_row, 0, wx.EXPAND | wx.BOTTOM, 4)

        if len(self._recent_configs) > 1:
            self._conf_recent = FlatCombo(
                self._file_panel,
                choices=self._recent_configs[1:],
                size=wx.Size(380, AppTheme.btn_h),
            )
            self._conf_recent.SetAction(lambda s: self._conf_ctrl.SetValue(s))
            recent_conf_row = wx.BoxSizer(wx.HORIZONTAL)
            recent_conf_row.Add(_lbl(self._file_panel, "Recent:", pt=10), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
            recent_conf_row.Add(self._conf_recent, 1, wx.EXPAND)
            file_sizer.Add(recent_conf_row, 0, wx.EXPAND)

        self._file_panel.SetSizer(file_sizer)
        self._file_panel.Show(False)

        connect_btn = FlatButton(panel, label="Connect", font=AppTheme.btn_font())
        connect_btn.SetAction(lambda _e=None: self.EndModal(wx.ID_OK))
        cancel_btn = FlatButton(panel, label="Cancel", font=AppTheme.btn_font())
        cancel_btn.SetAction(lambda _e=None: self.EndModal(wx.ID_CANCEL))

        btn_row = wx.BoxSizer(wx.HORIZONTAL)
        btn_row.AddStretchSpacer()
        btn_row.Add(connect_btn, 0, wx.RIGHT, 8)
        btn_row.Add(cancel_btn, 0)

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        main_sizer.Add(mode_row, 0, wx.ALL, 12)
        main_sizer.Add(wx.StaticLine(panel), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
        main_sizer.Add(self._prefix_panel, 0, wx.EXPAND | wx.ALL, 12)
        main_sizer.Add(self._file_panel, 0, wx.EXPAND | wx.ALL, 12)
        main_sizer.Add(wx.StaticLine(panel), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 8)
        main_sizer.Add(btn_row, 0, wx.EXPAND | wx.ALL, 10)
        panel.SetSizer(main_sizer)

        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(panel, 1, wx.EXPAND | wx.ALL, 1)
        self.SetSizer(outer)
        self.Fit()
        self.SetMinSize(self.GetSize())

    def _set_mode(self, mode: str) -> None:
        self._mode = mode
        use_prefix = mode == "prefix"
        self._rb_prefix.SetValue(use_prefix)
        self._rb_file.SetValue(not use_prefix)
        self._prefix_panel.Show(use_prefix)
        self._file_panel.Show(not use_prefix)
        self.Layout()
        self.Fit()

    def _on_browse(self, _e=None) -> None:
        with wx.FileDialog(
            self,
            "Open PVA Viewer config file",
            wildcard=_YAML_WILDCARD,
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dlg:
            if dlg.ShowModal() == wx.ID_OK:
                self._conf_ctrl.SetValue(dlg.GetPath())
                self._set_mode("conffile")

    def get_response(self) -> PVAConnectResponse:
        self.CentreOnScreen()
        ok = self.ShowModal() == wx.ID_OK
        prefix = self._prefix_ctrl.GetValue().strip()
        config_file = self._conf_ctrl.GetValue().strip()
        self.Destroy()
        if not ok:
            return PVAConnectResponse(ok=False, mode="prefix", prefix="", config_file="")
        return PVAConnectResponse(ok=True, mode=self._mode, prefix=prefix, config_file=config_file)

