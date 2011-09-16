#!/usr/bin/env python

import wx
import sys

if (len(sys.argv) > 1 and sys.argv[1].startswith('-d')):
    from lib import InstrumentFrame
else:
    from epicsapps.instruments import InstrumentFrame

if __name__ == '__main__':
    app = wx.PySimpleApp()
    frame = InstrumentFrame(conf=None, dbname=None)
    if frame.db is not None:
        frame.Show()
        app.MainLoop()
