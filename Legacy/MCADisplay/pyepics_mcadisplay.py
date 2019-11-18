#!/usr/bin/env python

import wx
import sys

# if (len(sys.argv) > 1 and sys.argv[1].startswith('-d')):
from lib.mcadisplay import MCADisplay
#else:
#    from epicsapps.mcadisplay import MCADisplay

if __name__ == '__main__':
    app = wx.App()
    MCADisplay().Show(True)
    app.MainLoop()
