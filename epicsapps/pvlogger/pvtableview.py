import sys
import time
from datetime import datetime, timedelta
import wx
import wx.lib.scrolledpanel as scrolled
import wx.lib.agw.flatnotebook as flat_nb
import wx.dataview as dv

from collections import OrderedDict, namedtuple

from wxutils import (GridPanel, SimpleText, MenuItem, OkCancel, Popup,
                     FileOpen, SavedParameterDialog, Font, FloatSpin,
                     HLine, GUIColors, COLORS, Button, flatnotebook,
                     Choice, FileSave, FileCheckList, LEFT, RIGHT, pack,
                     FRAMESTYLE, LEFT)

DVSTYLE = dv.DV_SINGLE|dv.DV_VERT_RULES|dv.DV_ROW_LINES


FNB_STYLE = flat_nb.FNB_NO_X_BUTTON
FNB_STYLE |= flat_nb.FNB_SMART_TABS|flat_nb.FNB_NO_NAV_BUTTONS

PlotWindowChoices = [f'Window {i+1}' for i in range(10)]

class PVLogDataModel(dv.DataViewIndexListModel):
    def __init__(self, pvlogfile):
        dv.DataViewIndexListModel.__init__(self, 0)
        self.pvlog = pvlogfile  # PVLogFile instance
        self.data = []
        self.ncols = 3
        self.read_data()

    def read_data(self):
        self.data = []
        if (self.pvlog.data.datetimes is None or
            len(self.pvlog.data.datetimes) < 2):
            self.pvlog.get_datetimes()
        dat = self.pvlog.data
        for dt, cval in zip(dat.datetimes, dat.char_value):
            st = dt.isoformat(timespec='seconds', sep=' '),
            self.data.append([False, st, cval])
            
        self.data.reverse()
        self.Reset(len(self.data))

    def select_none(self):
        for datrow in self.data:
            datarow[0] = False

    def GetColumnType(self, col):
        return "string"

    def GetValueByRow(self, row, col):
        return self.data[row][col]

    def GetColumnCount(self):
        try:
            ncol = len(self.data[0])
        except:
            ncol = self.ncols
        return ncol

    def GetCount(self):
        return len(self.data)

class PVTablePanel(wx.Panel) :
    """View Table of PV Values"""
    def __init__(self, parent, pvlogfile, size=(700, 400)):
        self.parent = parent
        self.pvlogfile = pvlogfile
        
        wx.Panel.__init__(self, parent, -1, size=size)

        spanel = scrolled.ScrolledPanel(self, size=size)

        panel = GridPanel(spanel, ncols=6, nrows=10, pad=3, itemstyle=LEFT)
        ptitle = f"{self.pvlogfile.pvname}, {len(self.pvlogfile.data.timestamp)} points"
        

        self.btn_show  = Button(panel, label='Show Selected',
                                action=self.onShowSelected, size=(200, -1))
        self.btn_clear = Button(panel, label='Clear Selections',
                                action=self.onClearAll, size=(200, -1))

        self.choose_pwin  = Choice(panel, choices=PlotWindowChoices, size=(200, -1))
 
        self.dvc = dv.DataViewCtrl(spanel, style=DVSTYLE)
        self.model = PVLogDataModel(self.pvlogfile)        
        self.dvc.AssociateModel(self.model)

        for icol, dat in enumerate((('Select', 75), 
                                    ('Date/Time', 200), 
                                    ('Value',     300))):
            title, width = dat
            kws = {'width': width}
            add_col = self.dvc.AppendTextColumn
            if title.lower() == 'select':
                add_col = self.dvc.AppendToggleColumn
                kws['mode'] = dv.DATAVIEW_CELL_ACTIVATABLE
            add_col(title, icol, **kws)
            col = self.dvc.Columns[icol]
            col.Sortable = False
            col.Alignment = wx.ALIGN_LEFT
        self.dvc.EnsureVisible(self.model.GetItem(0))
        
        panel.Add(SimpleText(panel, label=ptitle), dcol=4, newrow=True)
        panel.Add(self.btn_show, newrow=True)        
        panel.Add(self.btn_clear)
        panel.Add(SimpleText(panel, label='Show on Plot: '))
        panel.Add(self.choose_pwin)
        panel.Add((5, 5))
        panel.Add(HLine(panel, size=(675, 3)), dcol=4, newrow=True)
        panel.Add((5, 5))
        panel.Add(self.dvc, dcol=4, newrow=True)
        panel.pack()

        spanel.SetupScrolling()        
        mainsizer = wx.BoxSizer(wx.VERTICAL)
        mainsizer.Add(spanel, 1, wx.GROW|wx.ALL, 5)
        pack(self, mainsizer)

    def onShowSelected(self, event=None):
        print(" show selected")
        print(" plot win: ", self.choose_pwin.GetStringSelection())
        
    def onClearAll(self, event=None):
        print(" clear all ")
   
class PVTableFrame(wx.Frame) :
    """View Table of PV Values"""
    def __init__(self, parent=None, pvlogfile=None, size=(950, 400)):
        self.parent = parent
        wx.Frame.__init__(self, parent, -1,
                          title='PVLogger Table View', 
                          style=FRAMESTYLE, size=size)

        panel = scrolled.ScrolledPanel(self, size=(850, 425))
        self.nb = flatnotebook(panel, {}, style=FNB_STYLE)
        self.pvnames = []
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add((5, 5), 0, LEFT, 3)
        sizer.Add(self.nb, 0, LEFT, 3)
        sizer.Add((5, 5), 0, LEFT, 3)
        pack(panel, sizer)
        panel.SetupScrolling()
        self.Show()
        self.Raise()

    def get_pvpage(self, pvname):
        "get nb page for a PV by name"
        name = name.lower().strip()
        for i in range(self.nb.GetPageCount()):
            text = self.nb.GetPageText(i).strip().lower()
            if name in text:
                return self.nb.GetPage(i)
        

    def add_pvpage(self, pvlogfile):
        print("Add PV Page")
        panel = PVTablePanel(self, pvlogfile=pvlogfile)
        pvname = pvlogfile.pvname
        self.nb.AddPage(panel, pvname, True)        
