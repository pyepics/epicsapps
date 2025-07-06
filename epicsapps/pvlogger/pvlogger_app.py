#!/usr/bin/python
"""
Epics PV Logger Application, wx
"""
import sys
import os
import time
from threading import Thread
from pathlib import Path
from subprocess import Popen

from numpy import array, where
from functools import partial
from collections import namedtuple
from datetime import datetime, timedelta
from matplotlib.dates import date2num
import yaml

import wx
import wx.adv
import wx.dataview as dv
import wx.lib.colourselect  as csel
import wx.lib.scrolledpanel as scrolled
import wx.lib.agw.flatnotebook as flat_nb
import wx.lib.mixins.inspection
import wx.lib.filebrowsebutton as filebrowse

FileBrowserHist = filebrowse.FileBrowseButtonWithHistory

from epics import get_pv

from wxutils import (GridPanel, SimpleText, TextCtrl, MenuItem,
                     OkCancel, Popup, FileOpen, SavedParameterDialog,
                     Font, FloatSpin, HLine, GUIColors, COLORS,
                     Button, flatnotebook, Choice, FileSave,
                     FileCheckList, LEFT, RIGHT, pack)

from wxmplot.colors import hexcolor
from pyshortcuts import debugtimer, uname

from epicsapps.utils import get_pvdesc, normalize_pvname
from epicsapps.stripchart import StripChartFrame

from pyshortcuts import isotime

from .configfile import PVLoggerConfig
from .logfile import read_logfolder, TZONE

from .plotter import PlotFrame
from .pvtableview import PVTableFrame
from .eventtableview import EventTableFrame

from ..utils import (SelectWorkdir, get_icon, get_configfolder,
                     get_default_configfile, load_yaml, read_recents_file,
                     write_recents_file)

from .pvlogger import get_instruments

DVSTYLE = dv.DV_VERT_RULES|dv.DV_ROW_LINES|dv.DV_MULTIPLE

PVLOG_FOLDER = 'pvlog'
CONFIG_FILE = 'pvlog.yaml'
ICON_FILE = 'logging.ico'
FILECHARS = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_'
PlotWindowChoices = [f'Window {i+1}' for i in range(10)]
PLOT_COLORS = ('#1f77b4', '#d62728', '#2ca02c', '#ff7f0e', '#9467bd',
               '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf')


STY  = wx.GROW|wx.ALL
LSTY = wx.ALIGN_LEFT|wx.EXPAND|wx.ALL
CSTY = wx.ALIGN_CENTER
FRAME_STYLE = wx.DEFAULT_FRAME_STYLE|wx.TAB_TRAVERSAL

FONTSIZE = 9
FONTSIZE_FW = 10
if uname == 'win':
    FONTSIZE = 10
    FONTSIZE_FW = 11
elif uname == 'darwin':
    FONTSIZE = 11
    FONTSIZE_FW = 11

FNB_STYLE = flat_nb.FNB_NO_X_BUTTON
FNB_STYLE |= flat_nb.FNB_SMART_TABS|flat_nb.FNB_NO_NAV_BUTTONS

YAML_WILDCARD = 'PVLogger Config Files (*.yaml)|*.yaml|All files (*.*)|*.*'


PLOTOPTS = {'use_dates': True, 'show_legend': True,
            'xlabel': 'time', 'linewidth': 2.5,
            'marker': '+', 'markersize': 2.5,
            'theme': '<auto>',
            'fullbox': False,
            'drawstyle': 'steps-post',
             'yaxes_tracecolor': True,
             'timezone': TZONE }

def update_choice(wid, values, default=0):
    cur = wid.GetStringSelection()
    wid.Clear()
    wid.SetItems(values)
    if cur in values:
        wid.SetStringSelection(cur)
    else:
        wid.SetSelection(default)

class InstrumentDataModel(dv.DataViewIndexListModel):
    def __init__(self):
        dv.DataViewIndexListModel.__init__(self, 0)
        self.data = []
        self.ncols = 3

    def set_data(self, insts, used):
        self.data = []
        for name in used:
            if name in insts:
                pvlist = insts[name]
                self.data.append([name, str(len(pvlist)), True])

        for name, pvlist in insts.items():
            if name not in used:
                self.data.append([name, str(len(pvlist)), False])
        self.Reset(len(self.data))

    def GetColumnType(self, col):
        out = 'string'
        if col == 2:
            out = 'bool'
        return out

    def GetValueByRow(self, row, col):
        return self.data[row][col]

    def SetValueByRow(self, value, row, col):
        name, npvs, use = self.data[row]
        if col == 2:
            val = bool(value)
        else:
            val = str(value)
        self.data[row][col] = value
        return True

    def GetColumnCount(self):
        try:
            ncol = len(self.data[0])
        except:
            ncol = self.ncols
        return ncol

    def GetCount(self):
        return len(self.data)

    def AddRow(self, value):
        self.data.append(value)
        self.RowAppended()


class PVDataModel(dv.DataViewIndexListModel):
    def __init__(self):
        dv.DataViewIndexListModel.__init__(self, 0)
        self.data = []
        self.ncols = 4

    def set_data(self, pvlist):
        self.data = pvlist
        for i in range(3):
            self.data.append(['', '<auto>', '<auto>', True])

        self.Reset(len(self.data))

    def add_rows(self, n=3):
        for i in range(n):
            self.data.append(['', '<auto>', '<auto>', True])
        self.Reset(len(self.data))

    def GetColumnType(self, col):
        return 'bool' if col == 2 else 'string'

    def GetValueByRow(self, row, col):
        return self.data[row][col]

    def SetValueByRow(self, value, row, col):
        name, desc, detlta, use = self.data[row]
        if col == 3:
            val = bool(value)
        else:
            val = str(value)
        self.data[row][col] = value
        return True

    def GetColumnCount(self):
        try:
            ncol = len(self.data[0])
        except:
            ncol = self.ncols
        return ncol

    def GetCount(self):
        return len(self.data)

    def AddRow(self, value):
        self.data.append(value)
        self.RowAppended()



class PVsConnectedDialog(wx.Dialog):
    def __init__(self, parent, pvdict, **kws):
        self.parent = parent
        npvs = len(pvdict)
        unconn = []
        time.sleep(0.01)
        for name, pv in pvdict.items():
            if not pv.connected:
                pv.wait_for_connection(timeout=0.001)
                if not pv.connected:
                    unconn.append(name)
        if len(unconn) > 0 and len(unconn) < 0.9*npvs: # some connected
            unconn = []
            time.sleep(0.05)
            for name, pv in pvdict.items():
                if not pv.connected:
                    pv.wait_for_connection(timeout=0.01)
                    if not pv.connected:
                        unconn.append(name)

        nunconn = len(unconn)
        nconn = npvs - nunconn

        wx.Dialog.__init__(self, parent, wx.ID_ANY, size=(450, 450),
                           title="Check Connected PVs")

        panel = GridPanel(self, ncols=3, nrows=4, pad=4, itemstyle=LEFT)

        def add_text(text, dcol=1, newrow=True):
            panel.Add(SimpleText(panel, text), dcol=dcol, newrow=newrow)

        panel.Add((5, 5))
        add_text(f' {npvs} Epics PVS selected, {nconn} connected.', newrow=True)
        panel.Add((5, 5))
        panel.Add(HLine(panel, size=(300, 3)), dcol=2, newrow=True)
        panel.Add((5, 5))
        if nunconn > 0:
            add_text(' These PVs are not currently connected: ')
            for name in unconn:
                add_text(f'   {name}')
            panel.Add(HLine(panel, size=(300, 3)), dcol=2, newrow=True)
            panel.Add((5, 5))
        panel.Add(OkCancel(panel), dcol=2, newrow=True)
        panel.pack()
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(panel, 1, LEFT, 5)
        pack(self, sizer)
        self.Fit()
        w0, h0 = self.GetSize()
        w1, h1 = self.GetBestSize()
        self.SetSize((max(w0, w1)+25, max(h0, h1)+25))

    def onDone(self, event=None):
        self.Destroy()


class PVLoggerFrame(wx.Frame):
    default_colors = ((0, 0, 0), (0, 0, 255), (255, 0, 0),
                      (0, 0, 0), (255, 0, 255), (0, 125, 0))

    about_msg =  """Epics PV Logger
Matt Newville <newville@cars.uchicago.edu>
"""

    def __init__(self, configfile=None):

        self.parent = None
        wx.Frame.__init__(self, None, -1, 'Epics PV Logger',
                          style=FRAME_STYLE, size=(1100, 650))

        self.plot_windows = []
        self.pvmap = {} # displayed description to pvname
        self.pvmap_r = {} # reverse map
        self.wids = {}
        self.subframes = {}
        self.config_file = CONFIG_FILE
        self.run_config = None
        self.log_folder = None
        self.collect_folder = None
        self.parse_thread = None
        self.live_pvs = {}
        self.pvs_connected = 'unknown'
        self.last_time_start = 0
        self.last_time_stop = 0
        self.save_inst_time = 0.0
        self.create_frame()

    def create_frame(self):
        self.build_statusbar()
        self.build_menus()

        splitter = wx.SplitterWindow(self, style=wx.SP_LIVE_UPDATE)
        splitter.SetMinimumPaneSize(200)

        lpanel = wx.Panel(splitter)
        lpanel.SetMinSize((275, 500))

        rpanel = scrolled.ScrolledPanel(splitter)
        rpanel.SetSize((775, 500))
        rpanel.SetMinSize((500, 500))

        # left panel
        ltop = wx.Panel(lpanel)
        sel_none = Button(ltop, 'Clear Selections', size=(250, 30), action=self.onSelNone)

        ltsizer = wx.BoxSizer(wx.HORIZONTAL)
        ltsizer.Add(sel_none, 1, LEFT|wx.GROW, 1)
        pack(ltop, ltsizer)

        self.pvlist = FileCheckList(lpanel, main=self,
                                    select_action=self.onShowPV)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(ltop, 0, LEFT|wx.GROW, 1)
        sizer.Add(self.pvlist, 1, LEFT|wx.GROW|wx.ALL, 1)
        pack(lpanel, sizer)

        # right panel
        self.wids = {}

        self.nb = flatnotebook(rpanel, {}, style=FNB_STYLE)
        self.nb.AddPage(self.make_view_panel(), ' View Log Folder', True)
        self.nb.AddPage(self.make_run_panel(),  ' Collect Data ', True)
        self.nb.SetSelection(0)

        try:
            self.SetIcon(wx.Icon(get_icon('logging'), wx.BITMAP_TYPE_ICO))
        except:
            pass

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add((5, 5), 0, LEFT, 3)
        sizer.Add(self.nb, 0, LEFT, 3)
        sizer.Add((5, 5), 0, LEFT, 3)
        pack(rpanel, sizer)
        rpanel.SetupScrolling()

        splitter.SplitVertically(lpanel, rpanel, 1)
        self.Raise()

    def make_live_panel(self):
        wids = self.wids
        panel = GridPanel(self.nb, ncols=6, nrows=10, pad=3, itemstyle=LEFT)

        title = SimpleText(panel, ' View Live PVs ', font=Font(FONTSIZE+2),
                           size=(550, -1),  colour=COLORS['title'], style=LEFT)

        panel.Add(HLine(panel, size=(675, 3)), dcol=6, newrow=True)
        panel.pack()
        return panel


    def make_run_panel(self):
        wids = self.wids
        panel = GridPanel(self.nb, ncols=6, nrows=10, pad=3, itemstyle=LEFT)

        title = SimpleText(panel, ' PV Logger Collection', font=Font(FONTSIZE+2),
                           size=(550, -1),  colour=COLORS['title'], style=LEFT)

        btn_data = Button(panel, 'Browse', size=(125, -1), style=wx.ALIGN_LEFT,
                          action=self.onSelectDataFolder)
        btn_check = Button(panel, 'Check PVs', size=(150, -1),
                          action=self.onCheckPVs)
        btn_start = Button(panel, 'Start Collection', size=(200, -1),
                           action=self.onStartCollection)
        btn_more  = Button(panel, 'Add More PV Rows', size=(200, -1),
                           action=self.onMorePVs)

        wids['end_date'] =  wx.adv.DatePickerCtrl(panel, size=(175, -1),
                                                  style=wx.adv.DP_DROPDOWN|wx.adv.DP_SHOWCENTURY)
        wids['end_time'] = wx.adv.TimePickerCtrl(panel, size=(175, -1))
        wids['end_date'].SetValue(wx.DateTime.Now() + wx.DateSpan.Week())
        wids['end_time'].SetTime(9, 0, 0)

        wids['config_file'] = wx.StaticText(panel, label='', size=(550, -1))
        wids['data_folder'] = wx.TextCtrl(panel, value='', size=(400, -1))

        wids['inst_table'] = dv.DataViewCtrl(panel, style=DVSTYLE)
        wids['inst_table'].SetMinSize((725, 200))
        wids['inst_model'] = InstrumentDataModel()
        wids['inst_table'].AssociateModel(wids['inst_model'])

        for icol, dat in enumerate((('Instrument Name', 325, 'text', ''),
                                   (' # PVs', 125, 'int', ''),
                                   (' Use?', 75, 'bool', False))):
            _title, width, mode, xval= dat
            kws = {'width': width}
            add_col = wids['inst_table'].AppendTextColumn
            if mode == 'bool':
                add_col = wids['inst_table'].AppendToggleColumn
                kws['mode'] = dv.DATAVIEW_CELL_ACTIVATABLE
            add_col(_title, icol, **kws)
            col = wids['inst_table'].Columns[icol]
            col.Sortable = False
            col.Alignment = wx.ALIGN_LEFT


        wids['pv_table'] = dv.DataViewCtrl(panel, style=DVSTYLE)
        wids['pv_table'].SetMinSize((725, 200))
        wids['pv_model'] = PVDataModel()
        wids['pv_table'].AssociateModel(wids['pv_model'])

        for icol, dat in enumerate((('PV Name', 325, 'text', ''),
                                   ('Description', 200, 'text', '<auto>'),
                                   ('Delta', 80, 'text', '<auto>'),
                                   (' Use?', 75, 'bool', False))):
            _title, width, mode, xval= dat
            kws = {'width': width}
            add_col = wids['pv_table'].AppendTextColumn
            if mode == 'text':
                kws['mode'] = dv.DATAVIEW_CELL_EDITABLE
            elif mode == 'bool':
                add_col = wids['pv_table'].AppendToggleColumn
                kws['mode'] = dv.DATAVIEW_CELL_ACTIVATABLE
            add_col(_title, icol, **kws)
            col = wids['pv_table'].Columns[icol]
            col.Sortable = False
            col.Alignment = wx.ALIGN_LEFT

        def slabel(txt, size=(175, -1)):
            return wx.StaticText(panel, label=txt, size=size)

        panel.Add((5, 5))
        panel.Add(title, style=LEFT, dcol=5, newrow=True)
        panel.Add(slabel(' Config File: ', size=(150, -1)), dcol=1, newrow=True)
        panel.Add(wids['config_file'], dcol=3)
        panel.Add((5, 5))
        panel.Add(slabel(' Data Folder: ', size=(150, -1)), dcol=1, newrow=True)
        panel.Add(wids['data_folder'], dcol=2)
        panel.Add(btn_data, dcol=1, newrow=False)
        panel.Add((5, 5))
        panel.Add(slabel(' End Date&Time: ', size=(150, -1)), dcol=1, newrow=True)
        panel.Add(wids['end_date'])
        panel.Add(wids['end_time'])

        panel.Add((5, 5))
        panel.Add(btn_check, dcol=1, newrow=True)
        panel.Add(btn_start, dcol=1)
        panel.Add((5, 5))
        panel.Add(HLine(panel, size=(675, 3)), dcol=6, newrow=True)
        panel.Add((5, 5))
        panel.Add(slabel(' PVs to Log: ', size=(200, -1)), dcol=3, newrow=True)
        panel.Add(wids['pv_table'], dcol=5, newrow=True)
        panel.Add((5, 5))
        panel.Add(btn_more, dcol=3, newrow=True)

        panel.Add(slabel(' Instruments to Log: ', size=(200, -1)), dcol=3, newrow=True)
        panel.Add(wids['inst_table'], dcol=6, newrow=True)

        panel.Add(HLine(panel, size=(675, 3)), dcol=6, newrow=True)
        panel.pack()
        return panel

    def make_view_panel(self):
        wids = self.wids
        panel = GridPanel(self.nb, ncols=6, nrows=10, pad=3, itemstyle=LEFT)

        wids = self.wids
        title = SimpleText(panel, ' PV Logger Viewer', font=Font(FONTSIZE+2),
                           size=(550, -1),  colour=COLORS['title'], style=LEFT)

        wids['work_folder'] = SimpleText(panel, ' <no working folder selected> ',
                                         font=Font(FONTSIZE+1),
                                         size=(550, -1), style=LEFT)


        self.last_plot_type = 'one'
        opts = {'size': (175, -1)}
        wids['plotone'] = Button(panel, 'Show PV 1 ', action=self.onPlotOne, **opts)
        wids['plotsel'] = Button(panel, 'Show PV 1 to 4', action=self.onPlotSel, **opts)

        wids['plot_win']  = Choice(panel, choices=PlotWindowChoices, **opts)
        wids['plot_win'].SetStringSelection('1')
        wids['plotlive_one'] = Button(panel, 'LivePlot PV 1',
                                   action=self.onPlotLiveOne,
                                   size=(175, -1))

        wids['plotlive_sel'] = Button(panel, 'LivePlot PV 1 to 4',
                                   action=self.onPlotLiveSel,
                                   size=(175, -1))

        wids['use_sel'] = Button(panel, ' Use Selected PVs ',
                                 action=self.onUseSelected, **opts)
        wids['clear_sel'] = Button(panel, ' Clear PVs 2, 3, 4 ',
                                   action=self.onClearSelected, **opts)

        wids['use_inst'] = Button(panel, 'Select These PVs ',
                                  action=self.onSelectInstPVs, **opts)
        opts['size'] = (350, -1)
        opts['choices'] = []
        wids['instruments'] = Choice(panel, action=self.onSelectInst, **opts)

        wids['save_inst'] = TextCtrl(panel, '', action=self.onSaveInst,
                                     size=(350, -1), act_on_losefocus=False)

        for i in range(4):
            wids[f'pv{i+1}'] = Choice(panel, **opts)
            wids[f'col{i+1}'] = csel.ColourSelect(panel, -1, '',PLOT_COLORS[i],
                                                  size=(25, 25))
            wids[f'col{i+1}'].Bind(csel.EVT_COLOURSELECT,
                                   partial(self.onPVcolor, row=i+1))

        wids['evt_date1'] =  wx.adv.DatePickerCtrl(panel, size=(175, -1),
                                                  style=wx.adv.DP_DROPDOWN|wx.adv.DP_SHOWCENTURY)
        wids['evt_time1'] = wx.adv.TimePickerCtrl(panel, size=(175, -1))
        wids['evt_date1'].SetValue(wx.DateTime.Now() - wx.DateSpan.Week())
        wids['evt_time1'].SetTime(9, 0, 0)

        wids['evt_date2'] =  wx.adv.DatePickerCtrl(panel, size=(175, -1),
                                                  style=wx.adv.DP_DROPDOWN|wx.adv.DP_SHOWCENTURY)
        wids['evt_time2'] = wx.adv.TimePickerCtrl(panel, size=(175, -1))
        wids['evt_date2'].SetValue(wx.DateTime.Now() )
        wids['evt_time2'].SetTime(9, 0, 0)

        wids['evt_button'] = Button(panel, 'Show Events for Selected PVs',
                                   action=self.onShowSelectedEvents,
                                   size=(300, -1))

        def slabel(txt, wid=175):
            return wx.StaticText(panel, label=txt, size=(wid, -1))

        panel.Add((5, 5))
        panel.Add(title, style=LEFT, dcol=6, newrow=True)
        panel.Add(slabel(' Folder: '), dcol=1, newrow=True)
        panel.Add(wids['work_folder'], dcol=6)
        panel.Add((5, 5))
        panel.Add(HLine(panel, size=(675, 3)), dcol=6, newrow=True)
        panel.Add((5, 5))

        panel.Add(slabel(' Instruments: '), dcol=1, newrow=True)
        panel.Add(wids['instruments'], dcol=2)
        panel.Add(wids['use_inst'], dcol=1)

        panel.Add((5, 5))
        panel.Add(HLine(panel, size=(675, 3)), dcol=6, newrow=True)
        panel.Add((5, 5))
        panel.Add(slabel(' Select PVs: '), dcol=1, newrow=True)
        panel.Add(wids['use_sel'], dcol=1)
        panel.Add(wids['clear_sel'], dcol=1)

        panel.Add(slabel(' PV 1: '), dcol=1, newrow=True)
        panel.Add(wids['pv1'], dcol=2)
        panel.Add(wids['col1'])
        panel.Add(slabel(' PV 2: '), dcol=1, newrow=True)
        panel.Add(wids['pv2'], dcol=2)
        panel.Add(wids['col2'])
        panel.Add(slabel(' PV 3: '), dcol=1, newrow=True)
        panel.Add(wids['pv3'], dcol=2)
        panel.Add(wids['col3'])
        panel.Add(slabel(' PV 4: '), dcol=1, newrow=True)
        panel.Add(wids['pv4'], dcol=2)
        panel.Add(wids['col4'])

        panel.Add((5, 5))
        panel.Add(slabel(' Save as Instrument: '), dcol=1, newrow=True)
        panel.Add(wids['save_inst'], dcol=3)
        panel.Add(slabel(' Plot/Show Table: '), dcol=1, newrow=True)
        panel.Add(wids['plotone'], dcol=1)
        panel.Add(wids['plotsel'], dcol=1)
        panel.Add(slabel(' Plot Window: '), dcol=1, newrow=True)
        panel.Add(wids['plot_win'])
        panel.Add((5, 5))
        panel.Add(HLine(panel, size=(675, 3)), dcol=6, newrow=True)
        panel.Add((5, 5))
        panel.Add(slabel(' Live Plots: '), dcol=1, newrow=True)
        panel.Add(wids['plotlive_one'])
        panel.Add(wids['plotlive_sel'])
        panel.Add((5, 5))
        panel.Add(HLine(panel, size=(675, 3)), dcol=6, newrow=True)
        panel.Add((5, 5))
        panel.Add(slabel(' View Event Table for Selected PVs: ', wid=400),
                      dcol=3, newrow=True)

        panel.Add(slabel(' Start Date/Time: '), dcol=1, newrow=True)
        panel.Add(wids['evt_date1'])
        panel.Add(wids['evt_time1'])
        panel.Add(slabel(' Stop Date/Time: '), dcol=1, newrow=True)
        panel.Add(wids['evt_date2'])
        panel.Add(wids['evt_time2'])
        panel.Add(slabel(' Show Table: '), dcol=1, newrow=True)
        panel.Add(wids['evt_button'], dcol=2)

        panel.pack()
        return panel

    def build_statusbar(self):
        sbar = self.CreateStatusBar(2, wx.CAPTION)
        sfont = sbar.GetFont()
        sfont.SetWeight(wx.BOLD)
        sfont.SetPointSize(10)
        sbar.SetFont(sfont)
        self.SetStatusWidths([-2, -4])
        self.SetStatusText('', 0)

    def show_subframe(self, name, frameclass, **opts):
        shown = False
        if name in self.subframes:
            try:
                self.subframes[name].Raise()
                shown = True
            except:
                f = self.subframes.pop(name)
                del f
                shown = False
        if not shown:
            self.subframes[name] = frameclass(self, **opts)
            self.subframes[name].Raise()
        return self.subframes[name]

    def show_plotwin(self, name, **opts):
        opts['title'] = f'Epics PV Logger Plot {name}'
        return self.show_subframe(name, PlotFrame, **opts)

    def onCheckPVs(self, event=None):
        instruments = get_instruments()
        pvs = {}
        for row in self.wids['pv_model'].data:
            name, desc, mdel, use = row
            if use and len(name.strip()) > 1 and name not in pvs:
                pvs[name] = get_pv(name)
                if name not in self.live_pvs:
                    self.live_pvs[name] = pvs[name]

        for row in self.wids['inst_model'].data:
            iname, npvs, use = row
            if use and iname in instruments:
                for name in instruments[iname]:
                    if name not in pvs:
                        pvs[name] = get_pv(name)
                    if name not in self.live_pvs:
                        self.live_pvs[name] = pvs[name]

        time.sleep(0.25)
        if len(pvs) > 0:
            self.check_pv_connections(pvs)
            PVsConnectedDialog(self, pvs).Show()

    def check_pv_connections(self, pvs=None, waittime=0.1):
        """check that PVs connect.  If the first 5 PVs tried
           do not connect, set 'self.pvs_connected' to False
           to stop looking for connected PVs
        """
        if pvs is None:
            pvs = self.live_pvs
        if self.pvs_connected == 'unknown':
            unconn = []
            for name, pv in pvs.items():
                if not pv.connected:
                    pv.wait_for_connection(timeout=waittime)
                    if pv.connected:
                        self.pvs_connected = True
                    else:
                        unconn.append(name)
            if len(unconn) == len(pvs) and len(pvs) > 5:
                self.pvs_connected = False

    def onSaveConfigFile(self, event=None):
        "save config file"
        wids = self.wids
        datadir =  wids['data_folder'].GetValue()
        dlg = wx.FileDialog(self,
                            message='Save PVLogger Configuration',
                            wildcard=YAML_WILDCARD,
                            defaultFile='pvlog.yaml',
                            defaultDir=datadir,
                        style=wx.FD_SAVE|wx.FD_CHANGE_DIR)
        output = None
        if dlg.ShowModal() == wx.ID_OK:
            output  = Path(dlg.GetPath()).absolute().as_posix()
        dlg.Destroy()
        if output is None:
            return

        ddate = wids['end_date'].GetValue()
        dtime = wids['end_time'].GetValue()
        dt = datetime(ddate.GetYear(), 1+ddate.GetMonth(), ddate.GetDay(),
                      dtime.GetHour(), dtime.GetMinute(), 0)

        pvs = []
        for row in self.wids['pv_model'].data:
            name, desc, mdel, use = row
            if len(name.strip()) > 0 and use:
                pvs.append(f'{name} | {desc} | {mdel}')

        insts = []
        for row in self.wids['inst_model'].data:
            iname, npvs, use = row
            if use:
                insts.append(iname)

        config = {'datadir': datadir,
                  'folder': 'pvlog',
                  'end_datetime': datetime.isoformat(dt, sep=' '),
                  'instruments': insts,
                  'pvs': pvs}

        with open(output, 'w') as fh:
            yaml.safe_dump(config, fh, default_flow_style=False, sort_keys=False)

        parent = Path(output).parent
        wids['data_folder'].SetValue(parent.as_posix())
        os.chdir(parent)
        # print("Set Folder to ", parent)

    def onStartCollection(self, event=None):
        root = Path(sys.executable).parent.as_posix()
        epicsapp = Path(root, 'epicsapps').as_posix()
        if uname == 'win':
            epicsapp = Path(root, 'scripts', 'epicsapps.exe').as_posix()

        datadir =  self.wids['data_folder'].GetValue()
        fname = Path(self.wids['config_file'].GetLabel()).name
        os.chdir(datadir)
        cmd = [epicsapp, 'pvlogger', fname]
        Popen(cmd)
        print(f"Starting Collection with {fname}")


    def onMorePVs(self, event=None):
        self.wids['pv_model'].add_rows(n=3)

    def onUseSelected(self, event=None):
        sel_pvs = self.pvlist.GetCheckedStrings()[:4]
        for i, pvn in enumerate(sel_pvs):
            w = f'pv{i+1}'
            self.wids[w].SetStringSelection(pvn)

    def onClearSelected(self, event=None):
        for i in range(3):
            w = f'pv{2+i}'
            self.wids[w].SetStringSelection('None')

    def onSelectInst(self, event=None):
        pass

    def onSelectDataFolder(self, event=None):
        if self.collect_folder is None:
            self.collect_folder = Path('.').absolute().as_posix()

        dlg = wx.DirDialog(self, 'Select Data Folder',
                           style=wx.DD_DEFAULT_STYLE)

        path = Path(os.curdir).absolute().as_posix()
        dlg.SetPath(path)
        if  dlg.ShowModal() == wx.ID_OK:
            path = Path(dlg.GetPath()).absolute().as_posix()
        dlg.Destroy()
        self.wids['data_folder'].SetValue(path)

    def onReadConfigFile(self, event=None):
        if self.config_file is None:
            self.config_file = CONFIG_FILE

        WILDCARDS = "Config Files|*.yaml|All files (*.*)|*.*"
        dlg = wx.FileDialog(self, wildcard=WILDCARDS,
                            message='Select PVLogger Configuration File',
                            defaultFile=self.config_file,
                            style=wx.FD_OPEN)
        path = None
        if dlg.ShowModal() == wx.ID_OK:
            path = Path(dlg.GetPath()).absolute()
        dlg.Destroy()
        if path is None:
            return
        os.chdir(path.parent)
        self.wids['config_file'].SetLabel(path.as_posix())
        self.config_file = path.as_posix()
        cfile = PVLoggerConfig(path)
        self.run_config = cfile.config
        wdir = Path(self.run_config.get('datair', '.'))
        folder = Path(self.run_config.get('folder', 'pvlog'))

        self.wids['data_folder'].SetValue(wdir.absolute().as_posix())

        insts = self.run_config.get('instruments', [])
        self.wids['inst_model'].set_data(get_instruments(), insts)

        pvlist = []
        for pvline in self.run_config.get('pvs', []):
            name = pvline.strip()
            desc = '<auto>'
            mdel = '<auto>'
            if '|' in pvline:
                words = [w.strip() for w in pvline.split('|')]
                name = words[0]
                if len(words) > 1:
                    desc = words[1]
                if len(words) > 2:
                    mdel = words[2]
                pvlist.append([name, desc, mdel, True])

        self.wids['pv_model'].set_data( pvlist)

        self.nb.SetSelection(1)

    def onSaveInst(self, value=None):
        if value is None:
            value = self.wids['save_inst'].GetValue().strip()
        if len(value) < 1 or (time.time() < (self.save_inst_time) + 2.0):
            return

        cur_insts = self.log_folder.instruments
        if value in cur_insts:
            ret = Popup(self, f"Overwrite Instrument '{value}'?\n",
                        'Verify Overwrite',
                        style=wx.YES_NO|wx.ICON_QUESTION)
            if ret != wx.ID_YES:
                return

        pvnames  = []
        for i in range(4):
            pvdesc = self.wids[f'pv{i+1}'].GetStringSelection()
            if pvdesc == 'None':
                continue
            pvnames.append(self.pvmap[pvdesc])
        if len(pvnames) < 1:
            return

        cur_insts[value] = pvnames

        update_choice(self.wids['instruments'], list(cur_insts.keys()))
        ifile = Path(self.log_folder.folder, '_PVLOG_instruments.txt').absolute()
        with open(ifile, 'w', encoding='utf-8') as fh:
            yaml.safe_dump(self.log_folder.instruments, fh,
                           default_flow_style=False, sort_keys=False)

        self.save_inst_time = int(time.time())
        time.sleep(0.05)
        wx.CallAfter(self.wids['save_inst'].SetValue, '')


    def onSelectInstPVs(self, event=None):
        iname = self.wids['instruments'].GetStringSelection()
        self.pvlist.select_none()
        for i in range(4):
            self.wids[f'pv{i+1}'].SetStringSelection('None')

        sel = []
        for name in self.log_folder.instruments[iname]:
            desc = self.pvmap_r.get(name, None)
            if desc is not None:
                sel.append(desc)
        self.pvlist.SetCheckedStrings(sel)
        self.onUseSelected()

    def onSelNone(self, event=None):
        self.pvlist.select_none()

    def onSelAll(self, event=None):
        self.pvlist.select_all()

    def onShowPV(self, event=None, label=None):
        pvdesc = event.GetString()
        pvname = self.pvmap[pvdesc]
        self.wids['pv1'].SetStringSelection(pvdesc)
        pvlog = self.log_folder.pvs.get(pvname, None)
        if pvlog is None:
            print("cannot show PV ", pvname)
        else:
            data = self.get_pvdata(pvname)

        #
        enable_live = self.pvs_connected in ('unknown', True)
        if enable_live:
            if pvname not in self.live_pvs:
                self.live_pvs[pvname] = get_pv(pvname)
                self.live_pvs[pvname].wait_for_connection(timeout=0.1)
                self.check_pv_connections(waittime=0.1)

        self.wids['plotlive_one'].Enable(enable_live)
        self.wids['plotlive_sel'].Enable(enable_live)


    def get_pvdata(self, pvname):
        """get PVdata, caching until it changes"""
        pvlog = self.log_folder.pvs.get(pvname, None)
        if pvlog is None:
            return None
        if pvlog.data is None:
            self.write_message(f'parsing data for {pvname} ... ', panel=1)
            pvlog.parse()
        pvlog.set_end_time(self.log_folder.time_stop)
        if pvlog.data.mpldates is None:
            pvlog.get_mpldates()
        self.write_message(f'got data for {pvname}', panel=1)
        if self.parse_thread is not None:
            time.sleep(0.1)

        if pvname in self.log_folder.motors:
            self.log_folder.read_motor_events(pvname)
        return pvlog.data


    def onShowSelectedEvents(self, event=None):
        ddate1 = self.wids['evt_date1'].GetValue()
        dtime1 = self.wids['evt_time1'].GetValue()
        ddate2 = self.wids['evt_date2'].GetValue()
        dtime2 = self.wids['evt_time2'].GetValue()
        dt1 = datetime(ddate1.GetYear(), 1+ddate1.GetMonth(), ddate1.GetDay(),
                        dtime1.GetHour(), dtime1.GetMinute(), 0)
        dt2 = datetime(ddate2.GetYear(), 1+ddate2.GetMonth(), ddate2.GetDay(),
                           dtime2.GetHour(), dtime2.GetMinute(), 0)
        dt1 = dt1 - timedelta(days=1)
        dt2 = dt2 + timedelta(minutes=1)
        event_data = {}
        for pvdesc in self.pvlist.GetCheckedStrings():
            pvname = self.pvmap[pvdesc]
            data = self.get_pvdata(pvname)
            if data is None:
                data = self.get_pvdata(pvname)
            event_data[pvdesc] = data
        self.show_subframe('event_table', EventTableFrame)
        self.subframes['event_table'].set_data(event_data, dt1, dt2)

    def onPlotLiveOne(self, event):
        liveplot = self.show_subframe('pvlive', StripChartFrame)
        pvdesc = self.wids['pv1'].GetStringSelection()
        pvname = self.pvmap[pvdesc]
        desc = self.log_folder.pvs[pvname].description
        liveplot.addPV(pvname, desc=desc)
        liveplot.Show()

    def onPlotLiveSel(self, event):
        liveplot = self.show_subframe('pvlive', StripChartFrame)
        for w in ('pv1', 'pv2', 'pv3', 'pv4'):
            pvdesc = self.wids[w].GetStringSelection()
            if pvdesc == 'None':
                continue
            pvname = self.pvmap[pvdesc]
            desc = self.log_folder.pvs[pvname].description
            liveplot.addPV(pvname, desc=desc)
        liveplot.Show()

    def onPlotOne(self, event=None):
        pvdesc = self.wids['pv1'].GetStringSelection()
        pvname = self.pvmap[pvdesc]

        label = self.log_folder.pvs[pvname].description
        data = self.get_pvdata(pvname)
        if data is None:
            data = self.get_pvdata(pvname)

        if not data.is_numeric or len(data.events) > 0:
            self.show_subframe('pvtable', PVTableFrame,
                               title=f'Epics PV Logger Table')
            self.subframes['pvtable'].add_pvpage(data, pvdesc)
        if data.is_numeric:
            wname = self.wids['plot_win'].GetStringSelection()
            pwin = self.show_plotwin(wname)

            col   = self.wids['col1'].GetColour()
            hcol = hexcolor(col)
            ppath = Path(self.log_folder.fullpath)
            title = Path(ppath.parent.stem, ppath.stem).as_posix()

            opts = {'yaxes':1,  'label': label, 'title': title,
                    'colour':hcol, 'ylabel': f'{label} ({pvname})'}

            opts.update(PLOTOPTS)
            pwin.plot(data.mpldates, data.values, **opts)
            enum_strs = data.attrs.get('enum_strs', None)
            if enum_strs is not None:
                pwin.panel.set_ytick_labels(enum_strs, yaxes=1)
                pwin.panel.draw()
            pwin.Show()
            pwin.Raise()

    def onPlotSel(self, event=None):
        wname = self.wids['plot_win'].GetStringSelection()
        pframe = self.show_plotwin(wname)
        yaxes = 0
        tmin = None
        tmax = None
        plotted = False
        for i in range(4):
            pvdesc = self.wids[f'pv{i+1}'].GetStringSelection()
            if pvdesc == 'None':
                continue
            pvname = self.pvmap[pvdesc]
            data = self.get_pvdata(pvname)
            if data is None:
                data = self.get_pvdata(pvname)

            if not data.is_numeric or len(data.events) > 0:
                self.show_subframe('pvtable', PVTableFrame,
                            title=f'Epics PV Logger Table')
                self.subframes['pvtable'].add_pvpage(data, pvdesc)
            if data.is_numeric:
                yaxes += 1
                label = self.log_folder.pvs[pvname].description
                if len(label) < 1:
                    label = pvname
                    ylabel = pvname
                else:
                    ylabel = f'{label} ({pvname})'

                col   = self.wids[f'col{i+1}'].GetColour()
                hcol = hexcolor(col)
                ppath = Path(self.log_folder.fullpath)
                title = Path(ppath.parent.stem, ppath.stem).as_posix()

                opts = {'colour':hcol, 'yaxes':yaxes,
                        'label': label, 'title':  title}
                opts.update(PLOTOPTS)
                plot = pframe.oplot

                if yaxes == 1:
                    plot = pframe.plot
                    opts['ylabel'] = ylabel
                    tmin = min(data.mpldates)
                    tmax = max(data.mpldates)
                else:
                    opts[f'y{yaxes}label'] = ylabel
                    tmin = min(tmin, min(data.mpldates))
                    tmax = max(tmax, max(data.mpldates))

                plot(data.mpldates, data.values, **opts)
                enum_strs = data.attrs.get('enum_strs', None)
                if enum_strs is not None:
                    pframe.panel.set_ytick_labels(enum_strs, yaxes=yaxes)
                plotted = True
        if plotted:
            pframe.panel.draw()
            pframe.Show()
            pframe.Raise()

    def build_menus(self):
        mdata = wx.Menu()
        mcollect = wx.Menu()
        MenuItem(self, mdata, "&Open PVLogger Folder\tCtrl+O",
                 "Open PVLogger Folder", self.onLoadFolder)

        mdata.AppendSeparator()
        # MenuItem(self, mdata, "Inspect",
        #            "WX Inspect", self.onWxInspect)

        MenuItem(self, mdata, "E&xit\tCtrl+X", "Exit PVLogger", self.onExit)
        self.Bind(wx.EVT_CLOSE, self.onExit)

        MenuItem(self, mcollect, "&Read Configuration File\tCtrl+R",
                 "Read PVLogger Configuration File for Data Collection",
                 self.onReadConfigFile)

        MenuItem(self, mcollect, "&Save Configuration File\tCtrl+S",
                 "Saved PVLogger Configuration File for Data Collection",
                 self.onSaveConfigFile)

        mbar = wx.MenuBar()
        mbar.Append(mdata, "File")
        mbar.Append(mcollect, "Collection")
        self.SetMenuBar(mbar)

    def onWxInspect(self, event=None):
        wx.GetApp().ShowInspectionTool()

    def onLoadFolder(self, event=None):
        path = Path(os.curdir).absolute().as_posix()
        dlg = wx.DirDialog(self, 'Select PV Logger Data Folder',
                       style=wx.DD_DEFAULT_STYLE|wx.DD_CHANGE_DIR)
        dlg.SetPath(path)
        if  dlg.ShowModal() == wx.ID_OK:
            path = Path(dlg.GetPath()).absolute()
        else:
            path = None
        dlg.Destroy()
        if path is None or not path.exists():
            return
        self.nb.SetSelection(0)
        self.pvlist.Clear()
        folder = None
        try:
            folder = read_logfolder(path)
        except ValueError:
            folder = None
        if folder is None:
            Popup(self, f"""The Folder:
    {path.as_posix()}
is not a valid PV Logger Data Folder""",
          "Not a valid PV Logger Data Folder")
        else:
            self.use_logfolder(folder)

    def use_logfolder(self, folder):
        self.log_folder = folder
        self.log_folder.on_read = self.onReadDataFile
        self.wids['work_folder'].SetLabel(folder.fullpath)
        os.chdir(folder.fullpath)
        self.pvmap = {}
        self.pvmap_r = {}
        for pvname, logfile in self.log_folder.pvs.items():
            desc = logfile.description[:]
            if len(desc) < 1:
                desc = pvname
            if desc in self.pvmap:
                desc = f'{desc} ({pvname})'
            self.pvmap[desc] = pvname
            self.pvmap_r[pvname] = desc
            self.pvlist.Append(desc)

        pvnames = ['None',]
        pvnames.extend(list(self.pvmap.keys()))
        update_choice(self.wids['instruments'], list(self.log_folder.instruments))

        update_choice(self.wids['pv1'], pvnames, default=1)
        update_choice(self.wids['pv2'], pvnames)
        update_choice(self.wids['pv3'], pvnames)
        update_choice(self.wids['pv4'], pvnames)

        self.write_message(f'reading data for {len(self.log_folder.pvs)} PVs', panel=1)
        wx.CallAfter(self.read_folder)

    def onReadDataFile(self, pvname=None, npvs=None, nproc=1, tstart=None, **kws):
        message = ''
        if pvname is not None:
            message = f"Read data for '{pvname}'"
        if npvs is not None:
            message = f"{message}, {npvs} remaining ({nproc} processes)"
            if npvs == 0:
                message = "Read complete"
        if len(message) > 0:
            self.write_message(message, panel=1)
        wx.CallAfter(self.set_event_times)

    def set_event_times(self):
        if self.log_folder.time_start is not None:
            if abs(self.last_time_start - self.log_folder.time_start) > 2:
                t0  = self.last_time_start = self.log_folder.time_start
                dt = datetime.fromtimestamp(t0)
                dt = dt - timedelta(days=1)
                wt = wx.DateTime.Now()
                wt.SetYear(dt.year)
                wt.SetMonth(dt.month-1)
                wt.SetDay(dt.day)
                self.wids['evt_date1'].SetValue(wt)
                self.wids['evt_time1'].SetTime(dt.hour, dt.minute, 0)

        if self.log_folder.time_stop is not None:
            if abs(self.last_time_stop - self.log_folder.time_stop) > 2:
                t0  = self.last_time_stop = self.log_folder.time_stop
                dt = datetime.fromtimestamp(t0)
                dt = dt + timedelta(minutes=1)
                wt = wx.DateTime.Now()
                wt.SetYear(dt.year)
                wt.SetMonth(dt.month-1)
                wt.SetDay(dt.day)
                self.wids['evt_date2'].SetValue(wt)
                self.wids['evt_time2'].SetTime(dt.hour, dt.minute, 0)

    def read_folder(self):
        self.write_message(f'reading folder data....')
        self.log_folder.read_all_logs_text()
        self.write_message('ready')
        self.write_message(' ', panel=1)
        self.parse_thread = Thread(target=self.log_folder.parse_logfiles,
                                   kwargs={'verbose': True, 'nproc': 8})
        self.parse_thread.start()


    def onEditConfig(self, event=None):
        print("on EditConfig")

    def onTraceColor(self, trace, color, **kws):
        irow = self.get_current_traces()[trace][0] - 1
        self.colorsels[irow].SetColour(color)

    def onSide(self, event=None, **kws):
        self.needs_update = True
        self.force_redraw  = True

    def get_plotpanel(self):
        wname = self.wids['plot_win'].GetStringSelection()
        pframe = self.show_plotwin(wname)
        return pframe.panel

    def onPVshow(self, event=None, row=0):
        if not event.IsChecked():
            plotpanel = self.get_plotpanel()
            trace = plotpanel.conf.get_mpl_line(row)
            trace.set_data([], [])
            plotpanel.canvas.draw()
        self.needs_refresh = True

    def onPVchoice(self, event=None, row=None, **kws):
        self.needs_refresh = True
        pvname = self.pvchoices[row].GetStringSelection()
        if pvname in self.pv_desc:
            self.pvlabels[row].SetValue(self.pv_desc[pvname])
        plotpanel = self.get_plotpanel()
        for i in range(len(self.pvlist)+1):
            try:
                trace = plotpanel.conf.get_mpl_line(row-1)
                trace.set_data([], [])
            except:
                pass
        plotpanel.conf.set_viewlimits()

    def onPVcolor(self, event=None, row=None, **kws):
        plotpanel = self.get_plotpanel()
        plotpanel.conf.set_trace_color(hexcolor(event.GetValue()),
                                       trace=row-1)
        self.needs_refresh = True

    def write_message(self, s, panel=0):
        """write a message to the Status Bar"""
        try:
            self.SetStatusText(s, panel)
        except:
            pass


    def onAbout(self, event=None):
        dlg = wx.MessageDialog(self, self.about_msg,
                               "About PV Logger",
                               wx.OK | wx.ICON_INFORMATION)
        dlg.ShowModal()
        dlg.Destroy()

    def onHelp(self, event=None):
        dlg = wx.MessageDialog(self, self.help_msg, "PV Logger",
                               wx.OK | wx.ICON_INFORMATION)
        dlg.ShowModal()
        dlg.Destroy()

    def onExit(self, event=None):
        for pvname, pv in self.live_pvs.items():
            pv.clear_callbacks()
            pv.disconnect()
            time.sleep(0.001)

        for name, frame in self.subframes.items():
            try:
                frame.Destroy()
            except:
                pass

        self.Destroy()

class PVLoggerApp(wx.App, wx.lib.mixins.inspection.InspectionMixin):
    def __init__(self, configfile=None, prompt=True, with_inspect=False, **kws):
        self.configfile = configfile
        self.prompt = prompt
        self.with_inspect = with_inspect
        wx.App.__init__(self, **kws)

    def createApp(self):
        self.frame = PVLoggerFrame()
        self.frame.Show()
        self.SetTopWindow(self.frame)
        return True

    def OnInit(self):
        self.createApp()
        if self.with_inspect:
            self.ShowInspectionTool()
        return True
