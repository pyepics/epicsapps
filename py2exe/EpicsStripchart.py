#!/usr/bin/env python

import wx
import sys


from epicsapps.stripchart import StripChart

if __name__ == '__main__':
    app = wx.PySimpleApp()
    StripChart().Show(True)
    app.MainLoop()
