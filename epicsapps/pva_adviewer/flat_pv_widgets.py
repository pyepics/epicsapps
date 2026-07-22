#!/usr/bin/env python
"""
Flat-widget equivalents of the epics.wx PV controls.
"""

from contextlib import suppress

import wx
import numpy as np
from wxutils import FlatTextCtrl, FlatCombo, FlatButton, FlatPanel

from epicsapps.pva_adviewer.theme import get_theme

__all__ = ["FlatPVFloat", "FlatPVTextCtrl", "FlatPVDisplay", "FlatPVEnumButtons", "make_pv_enum", "make_pv_display", "make_pv_widget"]


def _pv_str(char_value=None, value=None) -> str:
    """Convert a PV callback value to a display string."""
    if isinstance(value, np.ndarray) and np.issubdtype(value.dtype, np.unsignedinteger):
        return value.tobytes().rstrip(b"\x00").decode("utf-8", errors="replace")

    if isinstance(value, (bytes, bytearray)):
        return value.rstrip(b"\x00").decode("utf-8", errors="replace")

    if not isinstance(value, (int, float, str, bool, type(None))):
        with suppress(TypeError):
            raw = bytes(value)
            return raw.rstrip(b"\x00").decode("utf-8", errors="replace")

    if char_value is not None and char_value != "":
        return str(char_value)

    if value is not None:
        return str(value)

    return ""


class FlatPVFloat(FlatTextCtrl):
    """FlatTextCtrl that monitors a numeric PV and puts on commit."""

    def __init__(self, parent: wx.Window, pv, size: wx.Size, font: wx.Font) -> None:
        super().__init__(parent, font=font, size=size)
        self._pv = pv
        pv.add_callback(self._on_pv_change)
        if pv.connected:
            self.SetValue(_pv_str(pv.char_value, pv.value))

    def _on_pv_change(self, pvname=None, char_value=None, value=None, **kws) -> None:
        text = _pv_str(char_value, value)
        def _update():
            if self and not self._editing:
                self.SetValue(text)
        wx.CallAfter(_update)

    def _commit(self, raw: str = "") -> None:
        val = (raw or self.GetValue()).strip()
        if not val:
            return
        with suppress(ValueError, TypeError):
            self._pv.put(float(val))


class FlatPVTextCtrl(FlatTextCtrl):
    """FlatTextCtrl that monitors a string PV and puts on commit."""

    def __init__(self, parent: wx.Window, pv, size: wx.Size, font: wx.Font) -> None:
        super().__init__(parent, font=font, size=size)
        self._pv = pv
        pv.add_callback(self._on_pv_change)
        if pv.connected:
            self.SetValue(_pv_str(pv.char_value, pv.value))

    def _on_pv_change(self, pvname=None, char_value=None, value=None, **kws) -> None:
        text = _pv_str(char_value, value)
        def _update():
            if self and not self._editing:
                self.SetValue(text)
        wx.CallAfter(_update)

    def _commit(self, raw: str = "") -> None:
        self._pv.put(raw or self.GetValue())


class FlatPVDisplay(FlatTextCtrl):
    """Read-only flat display that monitors a PV value."""

    def __init__(self, parent: wx.Window, pv, size: wx.Size, font: wx.Font) -> None:
        super().__init__(parent, font=font, size=size, centered=True)
        self.Unbind(wx.EVT_LEFT_DOWN)
        self._pv = pv
        pv.add_callback(self._on_pv_change)
        if pv.connected:
            self.SetValue(_pv_str(pv.char_value, pv.value))

    def _on_pv_change(self, pvname=None, char_value=None, value=None, **kws) -> None:
        text = _pv_str(char_value, value)
        wx.CallAfter(lambda: self and self.SetValue(text))

    def _commit(self, raw: str = "") -> None:
        pass


class FlatPVEnumButtons(FlatPanel):
    """A row of FlatButtons, one per enum choice, that put to the PV on click."""

    def __init__(self, parent: wx.Window, pv, size: wx.Size, font: wx.Font) -> None:
        super().__init__(parent, size=size)

        self._pv = pv
        self._buttons: list[FlatButton] = []
        self._active_idx = -1

        choices = list(pv.enum_strs or []) if pv.connected else ["---"]

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        for i, label in enumerate(choices):
            btn = FlatButton(self, label=label, font=font)
            btn.SetAction(lambda _e=None, idx=i: self._pv.put(idx))
            self._buttons.append(btn)
            gap = 2 if i < len(choices) - 1 else 0
            sizer.Add(btn, 1, wx.EXPAND | wx.RIGHT, gap)

        self.SetSizer(sizer)

        if pv.connected and pv.value is not None:
            with suppress(ValueError, TypeError):
                self._set_active(int(pv.value))

        pv.add_callback(self._on_pv_change)

    def _set_active(self, idx: int) -> None:
        self._active_idx = idx
        t = get_theme()
        active_scheme = (t.blue, t.bright_blue, t.blue, t.black, t.black)
        for i, btn in enumerate(self._buttons):
            btn.SetColorScheme(active_scheme if i == idx else None)

    def _on_dark_theme(self, is_dark: bool = True) -> None:
        super()._on_dark_theme(is_dark)
        # Re-apply active scheme so button colors are re-resolved from the new theme
        idx = self._active_idx
        wx.CallAfter(lambda: self and self._set_active(idx))

    def _on_pv_change(self, pvname=None, value=None, **kws) -> None:
        try:
            idx = int(value or 0)
        except (ValueError, TypeError):
            return
        wx.CallAfter(lambda: self and self._set_active(idx))


def make_pv_enum(parent: wx.Window, pv, size: wx.Size, font: wx.Font) -> FlatCombo:
    """FlatCombo that monitors an enum PV and puts on selection."""
    choices = list(pv.enum_strs or []) if pv.connected else []
    if not choices:
        choices = ["---"]

    sel = 0
    if pv.connected and pv.value is not None:
        try:
            sel = max(0, min(int(pv.value), len(choices) - 1))
        except (ValueError, TypeError):
            pass

    w = FlatCombo(parent, choices=choices, selection=sel, size=size, font=font)

    def _cb(pvname=None, value=None, **kws) -> None:
        def _update():
            if w:
                try:
                    w.SetSelection(max(0, min(int(value or 0), len(choices) - 1)))
                except (ValueError, TypeError):
                    pass
        wx.CallAfter(_update)

    pv.add_callback(_cb)
    w.SetAction(lambda s: pv.put(s))
    return w


def make_pv_display(parent: wx.Window, pv, size: wx.Size, font: wx.Font) -> FlatPVDisplay:
    """Flat read-only display that monitors a PV value."""
    return FlatPVDisplay(parent, pv, size, font)


def make_pv_widget(dtype: str, parent: wx.Window, pv, size: wx.Size, font: wx.Font) -> wx.Window:
    """Return the appropriate flat PV widget for the given type string."""
    if dtype == "pvfloat":
        return FlatPVFloat(parent, pv, size, font)

    if dtype == "pvtctrl":
        return FlatPVTextCtrl(parent, pv, size, font)

    if dtype == "pvenum":
        return make_pv_enum(parent, pv, size, font)

    if dtype == "pvenumbuttons":
        return FlatPVEnumButtons(parent, pv, size, font)

    return make_pv_display(parent, pv, size, font)

