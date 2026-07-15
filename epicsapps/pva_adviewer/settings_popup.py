#!/usr/bin/env python
"""
Provides a borderless settings popup for the PVA adviewer.
"""

from typing import Callable

import wx
from wxmplot.colors import get_colormap_names
from wxutils import FlatButton, FlatCheckBox, FlatTextCtrl, FlatCombo

from epicsapps.pva_adviewer.theme import FG_SECONDARY, POPUP_BG, POPUP_FG, SEP_COLOUR, COMBO_SCHEME, BTN_DISABLED, DEFAULT_SCHEME, TEXT_SCHEME, TOGGLE_SCHEME
from epicsapps.pva_adviewer.fonts import btn_font, scaled_font, BIN_METHOD_LABELS

__all__ = ["ImageSettingsPopup"]


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

        self.SetBackgroundColour(SEP_COLOUR)

        panel = wx.Panel(self)
        panel.SetBackgroundColour(POPUP_BG)
        panel.SetForegroundColour(POPUP_FG)

        sizer = wx.BoxSizer(wx.VERTICAL)
        self._build_section(panel, sizer, colormap, auto_scale, filter_gaps, contrast_min, contrast_max, bin_method)
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

    def Popup(self) -> None:
        self.Show()
        self.Raise()

    def Position(self, pt: wx.Point, size: tuple) -> None:
        self.SetPosition(pt)

    def _on_activate(self, event: wx.ActivateEvent) -> None:
        """Schedule a deferred dismiss check when the frame loses activation."""
        if not event.GetActive():
            self._dismiss_timer.Start(150)
        else:
            self._dismiss_timer.Stop()
        event.Skip()

    def _check_dismiss(self) -> None:
        """Dismiss the popup only if focus is genuinely outside this frame and all its children."""
        if not self or not self.IsShown():
            return
        focused = wx.Window.FindFocus()
        if focused is None or not self.IsDescendant(focused):
            self.Hide()
            self.Destroy()

    def _build_section(
        self,
        parent: wx.Panel,
        sizer: wx.BoxSizer,
        colormap: str,
        auto_scale: bool,
        filter_gaps: bool,
        contrast_min: float,
        contrast_max: float,
        bin_method: str,
    ) -> None:
        font = scaled_font(12)

        def _lbl(text: str) -> wx.StaticText:
            w = wx.StaticText(parent, label=text)
            w.SetBackgroundColour(POPUP_BG)
            w.SetForegroundColour(FG_SECONDARY)
            w.SetFont(font)
            return w

        cmap_row = wx.BoxSizer(wx.HORIZONTAL)
        cmap_row.Add(_lbl("Colormap"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        colormap_names = get_colormap_names()
        self._cmap_choice = FlatCombo(parent, choices=colormap_names, combo_scheme=COMBO_SCHEME)
        if colormap in colormap_names:
            self._cmap_choice.SetSelection(colormap_names.index(colormap))
        self._cmap_choice.Bind(wx.EVT_CHOICE, self._evt_colormap)
        cmap_row.Add(self._cmap_choice, 1, wx.EXPAND)
        sizer.Add(cmap_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

        levels_row = wx.BoxSizer(wx.HORIZONTAL)
        levels_row.Add(_lbl("Min"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self._min_ctrl = FlatTextCtrl(parent, value=f"{contrast_min:.6g}", text_scheme=TEXT_SCHEME)
        self._min_ctrl.Bind(wx.EVT_KEY_DOWN, self._evt_levels_key)
        self._min_ctrl.Bind(wx.EVT_KILL_FOCUS, self._evt_levels)
        levels_row.Add(self._min_ctrl, 1, wx.EXPAND | wx.RIGHT, 8)
        levels_row.Add(_lbl("Max"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)
        self._max_ctrl = FlatTextCtrl(parent, value=f"{contrast_max:.6g}", text_scheme=TEXT_SCHEME)
        self._max_ctrl.Bind(wx.EVT_KEY_DOWN, self._evt_levels_key)
        self._max_ctrl.Bind(wx.EVT_KILL_FOCUS, self._evt_levels)
        levels_row.Add(self._max_ctrl, 1, wx.EXPAND)
        sizer.Add(levels_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

        self._auto_scale_cb = FlatCheckBox(parent, label="Auto-scale contrast", value=auto_scale, check_scheme=TOGGLE_SCHEME, disabled_scheme=BTN_DISABLED)
        self._auto_scale_cb.SetAction(lambda v: self._evt_auto_scale(v))
        sizer.Add(self._auto_scale_cb, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

        self._filter_gaps_cb = FlatCheckBox(parent, label="Filter gaps (zeros)", value=filter_gaps, check_scheme=TOGGLE_SCHEME, disabled_scheme=BTN_DISABLED)
        self._filter_gaps_cb.SetAction(lambda v: self._evt_filter_gaps(v))
        sizer.Add(self._filter_gaps_cb, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

        bin_row = wx.BoxSizer(wx.HORIZONTAL)
        bin_row.Add(_lbl("Live binning"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        self._bin_method_keys = [key for key, _ in BIN_METHOD_LABELS]
        bin_labels = [label for _, label in BIN_METHOD_LABELS]
        self._bin_choice = FlatCombo(parent, choices=bin_labels, combo_scheme=COMBO_SCHEME)
        if bin_method in self._bin_method_keys:
            self._bin_choice.SetSelection(self._bin_method_keys.index(bin_method))
        else:
            self._bin_choice.SetSelection(0)
        self._bin_choice.Bind(wx.EVT_CHOICE, self._evt_bin_method)
        bin_row.Add(self._bin_choice, 1, wx.EXPAND)
        sizer.Add(bin_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

        reset_btn = FlatButton(parent, label="Reset View", color_scheme=DEFAULT_SCHEME, disabled_scheme=BTN_DISABLED, font=btn_font())
        reset_btn.SetAction(self._evt_reset_view)
        sizer.Add(reset_btn, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)

    def _evt_colormap(self, colormap: str) -> None:
        self._on_colormap_changed(colormap)

    def _evt_auto_scale(self, value: bool) -> None:
        self._on_auto_scale_changed(value)

    def _evt_filter_gaps(self, value: bool) -> None:
        self._on_filter_gaps_changed(value)

    def _evt_bin_method(self, label: str) -> None:
        for key, lbl in BIN_METHOD_LABELS:
            if lbl == label:
                self._on_bin_method_changed(key)
                return

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

    def _evt_reset_view(self, _e=None) -> None:
        self._on_reset_view()
        self.Hide()
        self.Destroy()
