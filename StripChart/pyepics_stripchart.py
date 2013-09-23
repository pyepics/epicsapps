#!/usr/bin/env python

import wx
import sys

if (len(sys.argv) > 1 and sys.argv[1].startswith('-d')):
    from lib import StripChart
else:
    from epicsapps.stripchart import StripChart

if __name__ == '__main__':
    app = wx.App()
    StripChart().Show(True)
    app.MainLoop()
