#!/usr/bin/env python
"""
Color constants and schemes definitions used for the pva adviewer.
"""

import sys

import wx
from wxutils import ColorTheme, get_theme


theme = get_theme()

# Sizes
ICON_SIZE = 20
UNIT_BTN_W = 44
UNIT_BTN_H = 22
UNIT_BTN_GAP = 4
BG_BTN_W = 30
LIVE_W = 24
LIVE_H = 56

# Colors
BG_SURFACE = theme.background
BG_CARD = theme.black
BG_ELEVATED = theme.bright_black
FG_PRIMARY = theme.foreground
FG_SECONDARY = wx.Colour(140, 140, 150)
SEP_COLOUR = wx.Colour(55, 55, 60)
BTN_HOVER_BG = theme.white
BTN_PRESS_BG = wx.Colour(80, 80, 80)
POPUP_BG = BG_CARD
POPUP_FG = FG_PRIMARY
POPUP_BTN_BG = wx.Colour(45, 45, 50)
POPUP_BTN_HOVER = wx.Colour(62, 62, 70)
POPUP_BTN_PRESS = wx.Colour(85, 85, 95)
PONI_LOADED  = theme.green
PONI_MISSING = wx.Colour(110, 110, 120)
DANGER = theme.red
DANGER_HOVER = theme.bright_red
DISABLED_BG = wx.Colour(33, 33, 36)
DISABLED_FG = wx.Colour(90, 90, 96)
LIVE_OFF = wx.Colour(90, 90, 95)
LIVE_ON = DANGER
LIVE_ON_HOVER = DANGER_HOVER
LIVE_OFF_HOVER = wx.Colour(120, 120, 125)
LIVE_SCHEME = (LIVE_OFF, LIVE_OFF_HOVER, LIVE_ON, LIVE_ON_HOVER)
BG_BTN_SCHEME = (LIVE_OFF, LIVE_OFF_HOVER, PONI_LOADED, PONI_LOADED)
BTN_DISABLED = (DISABLED_BG, DISABLED_FG)
DEFAULT_SCHEME = (POPUP_BTN_BG, POPUP_BTN_HOVER, POPUP_BTN_PRESS, FG_PRIMARY, FG_PRIMARY)
TOGGLE_SCHEME = (POPUP_BTN_BG, POPUP_BTN_HOVER, PONI_LOADED, FG_SECONDARY)
TEXT_SCHEME = (BG_ELEVATED, FG_PRIMARY, FG_SECONDARY, DISABLED_BG, DISABLED_FG, wx.Colour(70, 28, 28))
COMBO_SCHEME = (BG_ELEVATED, BTN_HOVER_BG, FG_PRIMARY, SEP_COLOUR, FG_SECONDARY, DISABLED_BG, DISABLED_FG, POPUP_BG, POPUP_BTN_HOVER)


def icon_scheme(bg: wx.Colour) -> tuple:
    """Return an (idle_bg, hover_bg, press_bg) IconScheme for a given idle background."""
    return (bg, BTN_HOVER_BG, BTN_PRESS_BG)
