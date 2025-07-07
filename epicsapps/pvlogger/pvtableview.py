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
FNB_STYLE = flat_nb.FNB_X_ON_TAB|flat_nb.FNB_SMART_TABS|flat_nb.FNB_NO_NAV_BUTTONS
PLOT_COLORS = ('#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf')
PlotWindowChoices = [f'Window {i+1}' for i in range(10)]

def dtformat(ts):
    dt = datetime.fromtimestamp(ts) # , tz=TZONE)
    return dt.isoformat(sep=' ', timespec='milliseconds')

class PVLogDataModel(dv.DataViewIndexListModel):
    def __init__(self, pvlogdata):
        dv.DataViewIndexListModel.__init__(self, 0)
        self.pvlog = pvlogdata  # PVLogData instance
        self.data = []
        self.mpldates = []
        self.ncols = 3
        self.read_data()

    def read_data(self):
        self.data = []
        self.mpldates = []
        dat = self.pvlog
        if dat.is_numeric and len(dat.events) > 0:
            for ts, cval in dat.events:
                self.mpldates.append(ts/86400.0)
                self.data.append([False, dtformat(ts), cval])
        else:
            for ts, cval in zip(dat.timestamps, dat.char_values):
                self.mpldates.append(ts/86400.0)
                self.data.append([False, dtformat(ts), cval])
        self.Reset(len(self.data))


    def SetValueByRow(self, value, row, col):
        if col == 0:
            self.data[row][col] = bool(value)
        return True

    def ClearAll(self):
        for row in self.data:
            row[0] = False
        self.Reset(len(self.data))

    def GetColumnType(self, col):
        return "bool" if cal == 0 else "string"

    def GetValueByRow(self, row, col):
        return self.data[row][col]

    def GetAttrByRow(self, row, col, attr):
        val = self.data[row][col]
        if col == 2 and '<CA_' in val:
            attr.SetColour('red')
            attr.SetBold(True)
            return True
        return False

    def GetColumnCount(self):
        return self.ncols

    def GetCount(self):
        return len(self.data)


class PVTablePanel(wx.Panel) :
    """View Table of PV Values"""
    def __init__(self, parent, pvlogdata, desc=None, npanel=0, size=(700, 400)):
        self.parent = parent
        self.pvlogdata = pvlogdata
        if desc is None:
            desc = pvlogdata.pvname
        self.desc = desc
        wx.Panel.__init__(self, parent, -1, size=size)

        spanel = scrolled.ScrolledPanel(self, size=size)
        self.dvc = dv.DataViewCtrl(spanel, style=DVSTYLE)
        self.model = PVLogDataModel(self.pvlogdata)
        self.dvc.AssociateModel(self.model)

        panel = GridPanel(spanel, ncols=4, nrows=4, pad=2, itemstyle=LEFT)
        ptitle = f"  {desc}  [{self.pvlogdata.pvname}]  {len(self.model.data)} events"

        self.btn_show  = Button(panel, label='Show Selected',
                                action=self.onShowSelected, size=(175, -1))
        self.btn_clear = Button(panel, label='Clear Selections',
                                action=self.onClearAll, size=(175, -1))

        npanel = npanel % len(PLOT_COLORS)
        self.btn_color = csel.ColourSelect(panel, -1, '', PLOT_COLORS[npanel],
                                               size=(25, 25))

        self.choose_pwin  = Choice(panel, choices=PlotWindowChoices, size=(175, -1))

        for icol, dat in enumerate((('Select', 75),
                                    ('Date/Time', 250),
                                    ('Value',     400))):
            title, width = dat
            kws = {'width': width}
            add_col = self.dvc.AppendTextColumn
            if icol == 0:
                add_col = self.dvc.AppendToggleColumn
                kws['mode'] = dv.DATAVIEW_CELL_ACTIVATABLE
            add_col(title, icol, **kws)
            col = self.dvc.Columns[icol]
            col.Alignment = wx.ALIGN_LEFT
            if icol == 1:
                col.Sortable = True
                col.SetSortOrder(1)
        self.dvc.EnsureVisible(self.model.GetItem(0))

        panel.Add(SimpleText(panel, label=ptitle), dcol=5)
        panel.Add(self.btn_show, newrow=True)
        panel.Add(self.btn_clear)
        panel.Add(SimpleText(panel, label='Show on Plot: '))
        panel.Add(self.choose_pwin)
        panel.Add(self.btn_color)
        panel.Add((5, 5))
        panel.Add(HLine(panel, size=(700, 3)), dcol=5, newrow=True)
        panel.Add((5, 5))
        panel.pack()

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(panel, 0, LEFT|wx.ALL, 5)
        sizer.Add(self.dvc, 1, LEFT|wx.ALL|wx.GROW)
        pack(spanel, sizer)

        mainsizer = wx.BoxSizer(wx.VERTICAL)
        mainsizer.Add(spanel, 1, wx.GROW|wx.ALL, 5)
        pack(self, mainsizer)

    def onShowSelected(self, event=None):
        plotwin = self.choose_pwin.GetStringSelection()
        color = hexcolor(self.btn_color.GetColour())

        if plotwin not in self.parent.subframes:
            plotwin = 'Window 1'
        pwin = self.parent.show_plotwin(plotwin)

        pdat = self.pvlogdata
        for i, row in enumerate(self.model.data):
            if row[0]:
                pwin.add_event({'desc': self.desc,
                                'name': pdat.pvname,
                                'color': color,
                                'datetime': row[1],
                                'value': row[2],
                                'mpldate': self.model.mpldates[i]})

    def onClearAll(self, event=None):
        self.model.ClearAll()

class PVTableFrame(wx.Frame) :
    """View Table of PV Values"""
    def __init__(self, parent=None, pvlogdata=None,
                     title='PVLogger Table View',
                     size=(750, 500)):
        self.parent = parent
        wx.Frame.__init__(self, parent, -1, title=title,
                          style=FRAMESTYLE, size=size)

        self.nb = flatnotebook(self, {}, style=FNB_STYLE)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.nb, 1, LEFT|wx.GROW|wx.EXPAND, 3)
        pack(self, sizer)
        self.Show()
        self.Raise()

    def add_pvpage(self, pvlogdata, desc):
        pages = self.get_panels()
        if desc in pages:
            self.nb.SetSelection(pages[desc])
        else:
            npanel = self.nb.GetPageCount()
            panel = PVTablePanel(parent=self.parent, npanel=npanel,
                                 pvlogdata=pvlogdata, desc=desc)
            self.nb.AddPage(panel, desc, True)
            self.nb.SetSelection(self.nb.GetPageCount()-1)

    def get_panels(self):
        out = {}
        for i in range(self.nb.GetPageCount()):
            out[self.nb.GetPageText(i)] = i
        return out
