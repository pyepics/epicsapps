#!/usr/bin/env python
"""
Provides a borderless settings popup for the PVA adviewer.
"""

from typing import Callable

import wx
from wxmplot.colors import get_colormap_names
from wxutils import FlatButton, FlatCheckBox, FlatTextCtrl, FlatCombo, FlatPanel, FlatLabel

from epicsapps.pva_adviewer.theme import AppTheme, get_theme

__all__ = ["ImageSettingsPopup"]

_SECTION_PAD = 14
_ROW_PAD = 8


class ImageSettingsPopup(wx.Frame):
    """Borderless settings popup that dismisses when focus is lost."""

    def __init__(
        self,
        parent: wx.Window,
        colormap: str,
        auto_scale: bool,
        filter_gaps: bool,
        contrast_min: float,
        contrast_max: float,
        bin_method: str,
        on_colormap_changed: Callable[[str], None],
        on_auto_scale_changed: Callable[[bool], None],
        on_filter_gaps_changed: Callable[[bool], None],
        on_levels_changed: Callable[[float, float], None],
        on_bin_method_changed: Callable[[str], None],
        on_reset_view: Callable[[], None],
        on_mask_changed: "Callable[[float | None, float | None], None]",
        mask_above: "float | None" = None,
        mask_below: "float | None" = None,
        pixel_size: "float | None" = None,
        on_pixel_size_changed: "Callable[[float | None], None] | None" = None,
        hist_norm: str = "linear",
        on_hist_norm_changed: "Callable[[str], None] | None" = None,
    ) -> None:
        super().__init__(
            parent,
            style=wx.FRAME_NO_TASKBAR | wx.NO_BORDER | wx.FRAME_FLOAT_ON_PARENT | wx.STAY_ON_TOP,
        )
        self._on_colormap_changed = on_colormap_changed
        self._on_auto_scale_changed = on_auto_scale_changed
        self._on_filter_gaps_changed = on_filter_gaps_changed
        self._on_levels_changed = on_levels_changed
        self._on_bin_method_changed = on_bin_method_changed
        self._on_reset_view = on_reset_view
        self._on_mask_changed = on_mask_changed
        self._on_pixel_size_changed = on_pixel_size_changed
        self._on_hist_norm_changed = on_hist_norm_changed

        self.SetBackgroundColour(get_theme().bright_black)

        panel = FlatPanel(self)

        sizer = wx.BoxSizer(wx.VERTICAL)

        self._build(
            panel, sizer,
            colormap, auto_scale, filter_gaps, contrast_min, contrast_max,
            bin_method, mask_above, mask_below, pixel_size, hist_norm,
        )

        sizer.AddSpacer(10)
        panel.SetSizer(sizer)
        sizer.Fit(panel)

        outer = wx.BoxSizer(wx.VERTICAL)
        outer.Add(panel, 0, wx.EXPAND | wx.ALL, 1)
        self.SetSizer(outer)
        self.Fit()

        self.Bind(wx.EVT_KILL_FOCUS, lambda e: e.Skip())
        self.Bind(wx.EVT_ACTIVATE, self._on_activate)
        self._dismiss_timer = wx.CallLater(150, self._check_dismiss)


    def _section_header(self, parent: wx.Window, sizer: wx.BoxSizer, title: str, first: bool = False) -> None:
        top_gap = 10 if first else _SECTION_PAD
        lbl = FlatLabel(parent, label=title, font=AppTheme.scaled_font(10, weight=wx.FONTWEIGHT_BOLD))
        lbl.SetForegroundColour(get_theme().foreground)
        sizer.Add(lbl, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, top_gap)
        line = wx.Panel(parent, size=(-1, 1))
        line.SetBackgroundColour(get_theme().bright_black)
        r, g, b = (
            get_theme().foreground.Red(),
            get_theme().foreground.Green(),
            get_theme().foreground.Blue(),
        )
        line.SetBackgroundColour(wx.Colour(r // 3, g // 3, b // 3))
        sizer.Add(line, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

    def _lbl(self, parent: wx.Window, text: str) -> FlatLabel:
        return FlatLabel(parent, label=text, font=AppTheme.scaled_font(12))

    def _build(
        self,
        parent: wx.Window,
        sizer: wx.BoxSizer,
        colormap: str,
        auto_scale: bool,
        filter_gaps: bool,
        contrast_min: float,
        contrast_max: float,
        bin_method: str,
        mask_above: "float | None",
        mask_below: "float | None",
        pixel_size: "float | None",
        hist_norm: str,
    ) -> None:
        self._build_display(parent, sizer, colormap, bin_method, hist_norm, first=True)
        self._build_range(parent, sizer, auto_scale, filter_gaps, contrast_min, contrast_max)
        self._build_mask(parent, sizer, mask_above, mask_below)
        self._build_detector(parent, sizer, pixel_size)
        self._build_actions(parent, sizer)

    def _build_display(
        self, parent, sizer, colormap: str, bin_method: str, hist_norm: str, first: bool = False
    ) -> None:
        self._section_header(parent, sizer, "DISPLAY", first=first)

        cmap_row = wx.BoxSizer(wx.HORIZONTAL)
        cmap_row.Add(self._lbl(parent, "Colormap"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        colormap_names = get_colormap_names()
        self._cmap_choice = FlatCombo(parent, choices=colormap_names)
        if colormap in colormap_names:
            self._cmap_choice.SetSelection(colormap_names.index(colormap))
        self._cmap_choice.Bind(wx.EVT_CHOICE, self._evt_colormap)
        cmap_row.Add(self._cmap_choice, 1, wx.EXPAND)
        sizer.Add(cmap_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, _ROW_PAD)

        scale_row = wx.BoxSizer(wx.HORIZONTAL)
        scale_row.Add(self._lbl(parent, "Scale"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        _norm_keys = ("linear", "sqrt", "log")
        _norm_labels = ("Linear", "√ Sqrt", "Log")
        self._hist_norm_choice = FlatCombo(parent, choices=list(_norm_labels))
        norm_idx = _norm_keys.index(hist_norm) if hist_norm in _norm_keys else 0
        self._hist_norm_choice.SetSelection(norm_idx)
        self._hist_norm_choice.Bind(wx.EVT_CHOICE, self._evt_hist_norm)
        scale_row.Add(self._hist_norm_choice, 1, wx.EXPAND)
        sizer.Add(scale_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, _ROW_PAD)

        bin_row = wx.BoxSizer(wx.HORIZONTAL)
        bin_row.Add(self._lbl(parent, "Binning"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self._bin_method_keys = [key for key, _ in AppTheme.bin_method_labels]
        bin_labels = [label for _, label in AppTheme.bin_method_labels]
        self._bin_choice = FlatCombo(parent, choices=bin_labels)
        if bin_method in self._bin_method_keys:
            self._bin_choice.SetSelection(self._bin_method_keys.index(bin_method))
        else:
            self._bin_choice.SetSelection(0)
        self._bin_choice.Bind(wx.EVT_CHOICE, self._evt_bin_method)
        bin_row.Add(self._bin_choice, 1, wx.EXPAND)
        sizer.Add(bin_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, _ROW_PAD)

    def _build_range(
        self, parent, sizer, auto_scale: bool, filter_gaps: bool, contrast_min: float, contrast_max: float
    ) -> None:
        self._section_header(parent, sizer, "RANGE")

        self._auto_scale_cb = FlatCheckBox(parent, label="Auto-scale", value=auto_scale)
        self._auto_scale_cb.SetAction(lambda v: self._evt_auto_scale(v))
        sizer.Add(self._auto_scale_cb, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, _ROW_PAD)

        self._filter_gaps_cb = FlatCheckBox(parent, label="Filter gaps (zeros)", value=filter_gaps)
        self._filter_gaps_cb.SetAction(lambda v: self._evt_filter_gaps(v))
        sizer.Add(self._filter_gaps_cb, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, _ROW_PAD)

        levels_row = wx.BoxSizer(wx.HORIZONTAL)
        levels_row.Add(self._lbl(parent, "Min"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self._min_ctrl = FlatTextCtrl(parent, value=f"{contrast_min:.6g}", size=wx.Size(-1, 28))
        self._min_ctrl.Bind(wx.EVT_KEY_DOWN, self._evt_levels_key)
        self._min_ctrl.Bind(wx.EVT_KILL_FOCUS, self._evt_levels)
        levels_row.Add(self._min_ctrl, 1, wx.EXPAND | wx.RIGHT, 8)
        levels_row.Add(self._lbl(parent, "Max"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self._max_ctrl = FlatTextCtrl(parent, value=f"{contrast_max:.6g}", size=wx.Size(-1, 28))
        self._max_ctrl.Bind(wx.EVT_KEY_DOWN, self._evt_levels_key)
        self._max_ctrl.Bind(wx.EVT_KILL_FOCUS, self._evt_levels)
        levels_row.Add(self._max_ctrl, 1, wx.EXPAND)
        sizer.Add(levels_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, _ROW_PAD)

    def _build_mask(self, parent, sizer, mask_above: "float | None", mask_below: "float | None") -> None:
        self._section_header(parent, sizer, "MASK")

        above_row = wx.BoxSizer(wx.HORIZONTAL)
        self._mask_above_cb = FlatCheckBox(parent, label="Above", value=mask_above is not None)
        self._mask_above_cb.SetAction(lambda _: self._evt_mask())
        above_row.Add(self._mask_above_cb, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self._mask_above_ctrl = FlatTextCtrl(
            parent, value=f"{mask_above:.6g}" if mask_above is not None else "",
            placeholder="threshold", size=wx.Size(-1, AppTheme.btn_h),
        )
        self._mask_above_ctrl.Bind(wx.EVT_TEXT_ENTER, lambda _: self._evt_mask())
        self._mask_above_ctrl.Bind(wx.EVT_KILL_FOCUS, lambda _: self._evt_mask())
        above_row.Add(self._mask_above_ctrl, 1, wx.EXPAND)
        sizer.Add(above_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, _ROW_PAD)

        below_row = wx.BoxSizer(wx.HORIZONTAL)
        self._mask_below_cb = FlatCheckBox(parent, label="Below", value=mask_below is not None)
        self._mask_below_cb.SetAction(lambda _: self._evt_mask())
        below_row.Add(self._mask_below_cb, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self._mask_below_ctrl = FlatTextCtrl(
            parent, value=f"{mask_below:.6g}" if mask_below is not None else "",
            placeholder="threshold", size=wx.Size(-1, AppTheme.btn_h),
        )
        self._mask_below_ctrl.Bind(wx.EVT_TEXT_ENTER, lambda _: self._evt_mask())
        self._mask_below_ctrl.Bind(wx.EVT_KILL_FOCUS, lambda _: self._evt_mask())
        below_row.Add(self._mask_below_ctrl, 1, wx.EXPAND)
        sizer.Add(below_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, _ROW_PAD)

    def _build_detector(self, parent, sizer, pixel_size: "float | None") -> None:
        self._section_header(parent, sizer, "DETECTOR")

        pixel_row = wx.BoxSizer(wx.HORIZONTAL)
        pixel_row.Add(self._lbl(parent, "Pixel size (µm)"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self._pixel_size_ctrl = FlatTextCtrl(
            parent, value=f"{pixel_size:.6g}" if pixel_size is not None else "",
            placeholder="e.g. 172", size=wx.Size(-1, AppTheme.btn_h),
        )
        self._pixel_size_ctrl.Bind(wx.EVT_TEXT_ENTER, lambda _: self._evt_pixel_size())
        self._pixel_size_ctrl.Bind(wx.EVT_KILL_FOCUS, lambda _: self._evt_pixel_size())
        pixel_row.Add(self._pixel_size_ctrl, 1, wx.EXPAND)
        sizer.Add(pixel_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, _ROW_PAD)

    def _build_actions(self, parent, sizer) -> None:
        reset_btn = FlatButton(parent, label="Reset View", font=AppTheme.btn_font())
        reset_btn.SetAction(self._evt_reset_view)
        sizer.Add(reset_btn, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, _SECTION_PAD)

    def Popup(self) -> None:
        self.Show()
        self.Raise()

    def Position(self, pt: wx.Point, size: tuple) -> None:
        self.SetPosition(pt)

    def _on_activate(self, event: wx.ActivateEvent) -> None:
        if not event.GetActive():
            self._dismiss_timer.Start(150)
        else:
            self._dismiss_timer.Stop()
        event.Skip()

    def _check_dismiss(self) -> None:
        if not self or not self.IsShown():
            return
        focused = wx.Window.FindFocus()
        if focused is None or not self.IsDescendant(focused):
            self._evt_mask()
            self.Hide()
            self.Destroy()

    def _evt_colormap(self, colormap: str) -> None:
        self._on_colormap_changed(colormap)

    def _evt_auto_scale(self, value: bool) -> None:
        self._on_auto_scale_changed(value)

    def _evt_filter_gaps(self, value: bool) -> None:
        self._on_filter_gaps_changed(value)

    def _evt_bin_method(self, label: str) -> None:
        for key, lbl in AppTheme.bin_method_labels:
            if lbl == label:
                self._on_bin_method_changed(key)
                return

    def _evt_hist_norm(self, label: str) -> None:
        _norm_map = {"Linear": "linear", "√ Sqrt": "sqrt", "Log": "log"}
        norm = _norm_map.get(label)
        if norm and self._on_hist_norm_changed:
            self._on_hist_norm_changed(norm)

    def _evt_levels_key(self, event: wx.KeyEvent) -> None:
        if event.GetKeyCode() in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            self._evt_levels(event)
        else:
            event.Skip()

    def _evt_levels(self, event: wx.Event) -> None:
        try:
            lo, hi = float(self._min_ctrl.GetValue()), float(self._max_ctrl.GetValue())
            if lo < hi:
                self._on_levels_changed(lo, hi)
        except ValueError:
            pass
        event.Skip()

    def _evt_mask(self) -> None:
        above = None
        if self._mask_above_cb.GetValue():
            try:
                above = float(self._mask_above_ctrl.GetValue())
            except ValueError:
                pass
        below = None
        if self._mask_below_cb.GetValue():
            try:
                below = float(self._mask_below_ctrl.GetValue())
            except ValueError:
                pass
        self._on_mask_changed(above, below)

    def _evt_pixel_size(self) -> None:
        if self._on_pixel_size_changed is None:
            return
        val = self._pixel_size_ctrl.GetValue().strip()
        try:
            self._on_pixel_size_changed(float(val) if val else None)
        except ValueError:
            pass

    def _evt_reset_view(self, _e=None) -> None:
        self._on_reset_view()
        self.Hide()
        self.Destroy()
