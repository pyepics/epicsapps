#!/usr/bin/env python

import wx
import sys
import sqlalchemy


debug = True # (len(sys.argv) > 1 and sys.argv[1].startswith('-d'))
    
# if not debug:
#     try:
#         from epicsapps.instruments import InstrumentFrame
#     except:
#         debug = True
# ;
from lib import InstrumentFrame

print 'SQLAlchemy : ', sqlalchemy.__version__

if __name__ == '__main__':
    app = wx.PySimpleApp()
    frame = InstrumentFrame(conf=None, dbname=None)
    if frame.db is not None:
        frame.Show()
        app.MainLoop()
