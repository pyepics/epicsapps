import sys
import time
from datetime import datetime

import wx
import wx.lib.scrolledpanel as scrolled
import wx.lib.agw.flatnotebook as flat_nb
import wx.lib.colourselect as csel
import wx.dataview as dv

from wxutils import (GridPanel, SimpleText, MenuItem, OkCancel, Popup,
                     FileOpen, SavedParameterDialog, Font, FloatSpin,
                     HLine, GUIColors, COLORS, Button, flatnotebook,
                     Choice, FileSave, FileCheckList, LEFT, RIGHT, pack,
                     FRAMESTYLE, LEFT)

from wxmplot.colors import hexcolor

from .logfile import TZONE

DVSTYLE = dv.DV_SINGLE|dv.DV_VERT_RULES|dv.DV_ROW_LINES


FNB_STYLE = flat_nb.FNB_NO_X_BUTTON
FNB_STYLE |= flat_nb.FNB_SMART_TABS|flat_nb.FNB_NO_NAV_BUTTONS

COLORS = ('#1f77b4', '#d62728', '#2ca02c', '#ff7f0e', '#9467bd',
          '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf')

def dtformat(ts):
    dt = datetime.fromtimestamp(ts)
    return dt.isoformat(sep=' ', timespec='milliseconds')

class EventDataModel(dv.DataViewIndexListModel):
    def __init__(self, event_data=None, dt1=None, dt2=None):
        dv.DataViewIndexListModel.__init__(self, 0)
        self.event_data = event_data
        self.pvcolors = {}
        self.dt1 = dt1
        self.dt2 = dt2
        self.set_data()

    def set_data(self, event_data=None, dt1=None, dt2=None):
        if event_data is not None:
            self.event_data = event_data
        if dt1 is not None:
            self.dt1 = dt1
        if dt2 is not None:
            self.dt2 = dt2
        self.data = []
        self.pvcolors = {}
        if self.event_data is None or self.dt1 is None or self.dt2 is None:
            return
        tmin = self.dt1.timestamp()
        tmax = self.dt2.timestamp()
        ipv = 0
        for pvdesc, dat in self.event_data.items():
            if pvdesc not in self.pvcolors:
                self.pvcolors[pvdesc] = COLORS[ipv]
                ipv  = (ipv+1) % len(COLORS)
            for ts, cval in dat.events:
                if ts >= tmin and ts <= tmax:
                    self.data.append([pvdesc, dat.pvname, dtformat(ts), cval])
        self.data = sorted(self.data, key=lambda x: x[2])
        self.Reset(len(self.data))

    def ClearAll(self):
        for row in self.data:
            row[0] = False
        self.Reset(len(self.data))

    def GetColumnType(self, col):
        return "string"

    def GetValueByRow(self, row, col):
        return self.data[row][col]

    def GetAttrByRow(self, row, col, attr):
        colour = self.pvcolors[self.data[row][0]]
        attr.SetColour(colour)
        return True

    def GetColumnCount(self):
        return self.ncols

    def GetCount(self):
        return len(self.data)


class EventTablePanel(wx.Panel) :
    """View Table of Events for Multiple PVs"""
    def __init__(self, parent,  size=(850, 400)):
        self.parent = parent
        wx.Panel.__init__(self, parent, -1, size=size)

        spanel = scrolled.ScrolledPanel(self, size=size)
        self.dvc = dv.DataViewCtrl(spanel, style=DVSTYLE)
        self.model = EventDataModel()
        self.dvc.AssociateModel(self.model)

        for icol, dat in enumerate((('PV Description ', 200),
                                    ('PV Name ', 175),
                                    ('Date/Time', 250),
                                    ('Value',     350))):
            title, width = dat
            self.dvc.AppendTextColumn(title, icol, width=width)
            col = self.dvc.Columns[icol]
            col.Alignment = wx.ALIGN_LEFT
            col.Sortable = True
            col.SetSortOrder(1)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.dvc, 1, LEFT|wx.ALL|wx.GROW)
        pack(spanel, sizer)

        mainsizer = wx.BoxSizer(wx.VERTICAL)
        mainsizer.Add(spanel, 1, wx.GROW|wx.ALL, 5)
        pack(self, mainsizer)

    def set_data(self, event_data, dt1, dt2):
        self.model.set_data(event_data, dt1, dt2)

    def onClearAll(self, event=None):
        self.model.ClearAll()

class EventTableFrame(wx.Frame) :
    """View Table of PV Values"""
    def __init__(self, parent=None, title='PVLogger Event Table View',
                     size=(850, 500)):
        self.parent = parent
        wx.Frame.__init__(self, parent, -1, title=title,
                          style=FRAMESTYLE, size=size)

        self.panel = EventTablePanel(parent=self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.panel, 1, LEFT|wx.GROW|wx.EXPAND, 3)
        pack(self, sizer)
        self.Show()
        self.Raise()

    def set_data(self, event_data, dt1, dt2):
        self.panel.set_data(event_data, dt1, dt2)
