#!/usr/bin/python
"""
Epics Strip Chart application
"""
import os
import sys
import time
import shutil
from collections import namedtuple

import numpy as np

from numpy import array, where
from functools import partial
from pathlib import Path

from datetime import datetime, timezone
import pytz
import wx
import wx.lib.colourselect  as csel

from epics import get_pv
from epics.wx import EpicsFunction, DelayedEpicsCallback

from wxutils import (GridPanel, SimpleText, MenuItem, OkCancel, Popup,
                     FileOpen, SavedParameterDialog, Font, FloatSpin,
                     FloatCtrl, Choice, YesNo, TextCtrl, pack,
                     Check, LEFT, HLine, Button)

from wxmplot.plotpanel import PlotPanel
from wxmplot.colors import hexcolor

from ..utils import SelectWorkdir, get_icon, ConfigFile, load_yaml

TZONE = str(datetime.now(timezone.utc).astimezone().tzinfo)
if os.environ.get('TZ', None) is not None:
    TZONE = pytz.timezone(os.environ.get('TZ', TZONE))

CONFFILE = 'stripchart.yaml'
FILECHARS = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_'

BGCOL  = (250, 250, 240)

POLLTIME = 80
NPVS = 4
STY  = wx.GROW|wx.ALL
LSTY = wx.ALIGN_LEFT|wx.EXPAND|wx.ALL
CSTY = wx.ALIGN_CENTER

PLOT_COLORS = ('#1f77b4', '#d62728', '#2ca02c', '#ff7f0e', '#9467bd',
               '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf')

# Each recorded value uses 2 doubles (time, value)
# With NMAX_DEFAULT of 2**23, 8M, each PV will use up to
# (2**23)*2*8 bytes of data == 128 MB.
#
# For events at 10 Hz, 2**23 values will hold
# 233 hours or 9 days, 17  hours worth of data.
NMAX_DEFAULT = 2**23
NTRIM_DEFAULT = NMAX_DEFAULT/32


_configtext = """
##   pvname, pvdesc, use_log, ymin, ymax
pvs:
   - ['S:SRcurrentAI.VAL', 'Storage Ring Current', 0, '', '']
"""

class StripChartConfig(ConfigFile):
    def __init__(self, fname=CONFFILE):
        dconf = load_yaml(_configtext)
        ConfigFile.__init__(self, fname, default_config=dconf)

def get_bound(val):
    "return float value of input string or None"
    val = val.strip()
    if len(val) == 0 or val is None:
        return None
    try:
        val = float(val)
    except:
        val = None
    return val

class PVSelectDialog(wx.Dialog):
    def __init__(self, parent, pvs=None, **kws):
        self.parent = parent
        self.pvs = pvs
        wx.Dialog.__init__(self, parent, wx.ID_ANY, size=(550, 450),
                           title="Select Starting PVs for StripChart")

        panel = GridPanel(self, ncols=3, nrows=4, pad=4, itemstyle=LEFT)
        self.wids = wids = {}
        def add_text(text, dcol=1, newrow=True):
            panel.Add(SimpleText(panel, text), dcol=dcol, newrow=newrow)

        wids['sel_all'] = Button(panel, 'Select All ', size=(175, -1),
                                 action=self.onSelAll)
        wids['sel_none'] = Button(panel, 'Select None ', size=(175, -1),
                                  action=self.onSelNone)

        add_text(' Select Recently Used PVs for StripChart ', newrow=True, dcol=4)
        panel.Add(wids['sel_all'], newrow=True)
        panel.Add(wids['sel_none'])
        add_text(' PV Name ', newrow=True)
        add_text(' Description ', newrow=False)
        add_text(' Use?  ', newrow=False)
        panel.Add(HLine(panel, size=(500, 3)), dcol=4, newrow=True)
        i = 0
        for pvname, desc, uselog, ymin, ymax in pvs:
            add_text(pvname, newrow=True)
            add_text(desc, newrow=False)
            w = wids[f'use_{i}'] = Check(panel, default=False, label='')
            panel.Add(w)
            i += 1

        panel.Add(HLine(panel, size=(500, 3)), dcol=4, newrow=True)
        panel.Add(OkCancel(panel), dcol=2, newrow=True)
        panel.pack()

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(panel, 1, LEFT, 5)
        pack(self, sizer)
        self.Fit()
        w0, h0 = self.GetSize()
        w1, h1 = self.GetBestSize()
        self.SetSize((max(w0, w1, 500)+25, max(h0, h1, 250)+25))


    def onSelAll(self, event=None):
        for wname, wid in self.wids.items():
            if wname.startswith('use'):
                wid.SetValue(1)

    def onSelNone(self, event=None):
        for wname, wid in self.wids.items():
            if wname.startswith('use'):
                wid.SetValue(0)

    def GetResponse(self):
        self.Raise()
        response = namedtuple('PVSelection', ('ok', 'pvs'))
        ok, use_pvs = False, []
        if self.ShowModal() == wx.ID_OK:
            use_pvs = []
            ok = True
            for wname, wid in self.wids.items():
                if wname.startswith('use'):
                    i = int(wname.replace('use_', ''))
                    if wid.IsChecked():
                        use_pvs.append(self.pvs[i])
        return response(ok, use_pvs)

class StripChartFrame(wx.Frame):
    help_msg =  """Quick help:

 Left-Click:   to display X,Y coordinates
 Left-Drag:    to zoom in on plot region
 Right-Click:  display popup menu with choices:
                Zoom out 1 level
                Zoom all the way out
                --------------------
                Configure
                Save Image

Also, these key bindings can be used
(For Mac OSX, replace 'Ctrl' with 'Apple'):

  Ctrl-S:     save plot image to file
  Ctrl-C:     copy plot image to clipboard
  Ctrl-K:     Configure Plot
  Ctrl-Q:     quit

"""

    about_msg =  """Epics PV Strip Chart  version 0.1
Matt Newville <newville@cars.uchicago.edu>
"""
    def __init__(self, parent=None, configfile=None, prompt=False, nmax=None, ntrim=None):
        self.pvdata = {}
        self.pvs = {}
        self.pv_opts = {}
        self.wids = {}
        self.nplot = 0
        self.configfile = None
        self.pvlist = ['-']
        self.plotted_pvs = {i: None for i in range(NPVS)}
        self.needs_refresh = False
        self.force_replot = False
        self.paused = False
        self.nmax = nmax
        self.ntrim = ntrim
        if self.nmax is None:
            self.nmax = NMAX_DEFAULT
        if self.ntrim is None:
            self.ntrim = NTRIM_DEFAULT
        self.timelabel = 'seconds'

        self.create_frame(parent)

        ret = SelectWorkdir(self)
        self.config = {'pvs': []}
        self.onImportPVs(configfile)

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.onUpdatePlot, self.timer)
        self.timer.Start(POLLTIME)

    def onReadConfig(self, event=None):
        wcard = 'StripChart Config Files (*.yaml)|*.yaml|All files (*.*)|*.*'
        cfile = FileOpen(self.parent, "Read StripChart Configuration File",
                              default_file=CONFFILE, wildcard=wcard)
        if cfile is not None:
            self.onImportPVs(cfile)

    def onImportPVs(self, conffile):
        if conffile is None:
            conffile = CONFFILE
        if Path(conffile).exists():
            self.read_config(conffile)

        if len(self.config['pvs']) > 0:
            dlg = PVSelectDialog(self, self.config['pvs'])
            res = dlg.GetResponse()
            dlg.Destroy()
            if res.ok:
                for name, desc, uselog, ymin, ymax in res.pvs:
                    self.addPV(name, desc=desc, uselog=uselog, ymin=ymin, ymax=ymax)


    def read_config(self, fname=None):
        "read config file"
        self.configfile = StripChartConfig(fname=fname)
        self.config = {'pvs': []}
        nconf = getattr(self.configfile, 'config', {})
        self.config.update(nconf)

    def create_frame(self, parent, size=(950, 450), **kwds):
        self.parent = parent

        kwds['style'] = wx.DEFAULT_FRAME_STYLE|wx.TAB_TRAVERSAL
        kwds['size']  = size
        wx.Frame.__init__(self, parent, -1, 'Epics PV Strip Chart', **kwds)

        self.build_statusbar()

        self.plotpanel = PlotPanel(self)
        self.plotpanel.messenger = self.write_message

        pvpanel = self.build_pvpanel()
        self.build_btnpanel()
        self.build_menus()
        self.SetBackgroundColour(wx.Colour(*BGCOL))

        mainsizer = wx.BoxSizer(wx.VERTICAL)

        p1 = wx.Panel(self)
        p1.SetBackgroundColour(wx.Colour(*BGCOL))
        label = SimpleText(p1, ' Add PV:')
        self.pvname = TextCtrl(p1, '', size=(250, -1), action=self.onPVname)
        self.pvmsg = SimpleText(p1, '  ',  minsize=(75, -1), style=LSTY|wx.EXPAND)
        self.save_pvconf  = Button(p1, label='Save PV Options',  size=(200, 30),
                                   action=self.onSavePVSettings)
        s1 = wx.BoxSizer(wx.HORIZONTAL)

        s1.Add(label,       0,  wx.ALIGN_LEFT|wx.ALIGN_CENTER, 10)
        s1.Add(self.pvname, 0,  wx.ALIGN_LEFT|wx.ALIGN_CENTER, 10)
        s1.Add(self.pvmsg, 1,  wx.ALIGN_LEFT|wx.ALIGN_CENTER, 10)
        s1.Add(self.save_pvconf, 0,  wx.ALIGN_LEFT|wx.ALIGN_CENTER, 10)
        p1.SetAutoLayout(True)
        p1.SetSizer(s1)
        s1.Fit(p1)

        mainsizer.Add(p1,             0, wx.GROW|wx.EXPAND, 5)
        mainsizer.Add(wx.StaticLine(self, size=(250, -1),
                                    style=wx.LI_HORIZONTAL),
                      0, wx.EXPAND|wx.GROW, 8)
        mainsizer.Add(pvpanel,   0, wx.EXPAND, 5)
        mainsizer.Add(wx.StaticLine(self, size=(250, -1),
                                    style=wx.LI_HORIZONTAL),
                      0, wx.EXPAND|wx.GROW, 8)
        mainsizer.Add(self.btnpanel,  0, wx.EXPAND, 5)
        mainsizer.Add(self.plotpanel, 1, wx.EXPAND, 5)
        self.SetAutoLayout(True)
        self.SetSizer(mainsizer)
        self.Fit()

        try:
            self.SetIcon(wx.Icon(get_icon('stripchart'), wx.BITMAP_TYPE_ICO))
        except:
            pass

        self.Refresh()

    def build_statusbar(self):
        sbar = self.CreateStatusBar(2, wx.CAPTION)
        sfont = sbar.GetFont()
        sfont.SetWeight(wx.BOLD)
        sfont.SetPointSize(10)
        sbar.SetFont(sfont)
        self.SetStatusWidths([-5, -2])
        self.SetStatusText('', 0)

    def build_pvpanel(self):
        panel = GridPanel(self, ncols=3, nrows=4, pad=2, itemstyle=LEFT)
        def txt(label, wid=80):
            return SimpleText(panel, label, size=(wid, -1), style=LSTY)

        panel.Add(txt(' Side  '))
        panel.Add(txt(' PV    '))
        panel.Add(txt(' Color '))
        panel.Add(txt(' Log?  '))
        panel.Add(txt(' Y Min  '))
        panel.Add(txt(' Y Max  '))
        panel.Add(txt(' Label  '))

        wids =self.wids = {}
        sides = (' Left: ' , ' Right: ', ' Right2: ', ' Right3: ')
        for i in range(NPVS):
            wids[f'pv{i}'] = Choice(panel, choices=self.pvlist, size=(250, -1),
                                    action = partial(self.onPVchoice, row=i))
            wids[f'pv{i}'].SetSelection(0)

            wids[f'uselog{i}'] = Choice(panel, choices=('No', 'Yes'), size=(65, -1),
                                     action=self.onPVLogwid)
            wids[f'uselog{i}'].SetSelection(0)
            wids[f'ymin{i}'] = wx.TextCtrl(panel, -1, '', size=(75, -1),
                                           style=wx.TE_PROCESS_ENTER)
            wids[f'ymin{i}'].Bind(wx.EVT_TEXT_ENTER,  self.onPVwid)
            wids[f'ymax{i}'] = wx.TextCtrl(panel, -1, '', size=(75, -1),
                                           style=wx.TE_PROCESS_ENTER)

            wids[f'ymin{i}'].Bind(wx.EVT_CHOICE,   self.onPVwid)
            wids[f'ymax{i}'].Bind(wx.EVT_TEXT_ENTER,  self.onPVwid)

            wids[f'col{i}'] =  csel.ColourSelect(panel, -1, '', PLOT_COLORS[i])
            wids[f'col{i}'].Bind(csel.EVT_COLOURSELECT, partial(self.onPVcolor, row=i))
            wids[f'desc{i}'] = wx.TextCtrl(panel, -1, '', size=(250, -1))

            panel.Add(txt(sides[i]), newrow=True)
            panel.Add(wids[f'pv{i}'])
            panel.Add(wids[f'col{i}'])
            panel.Add(wids[f'uselog{i}'])
            panel.Add(wids[f'ymin{i}'])
            panel.Add(wids[f'ymax{i}'])
            panel.Add(wids[f'desc{i}'])

        panel.pack()
        return panel


    def build_btnpanel(self):
        panel = self.btnpanel = wx.Panel(self, )
        panel.SetBackgroundColour(wx.Colour(*BGCOL))

        btnsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.pause_btn  = wx.Button(panel, label='Pause',  size=(100, 30))
        self.resume_btn = wx.Button(panel, label='Resume', size=(100, 30))
        self.resume_btn.Disable()

        self.pause_btn.Bind(wx.EVT_BUTTON, self.onPause)
        self.resume_btn.Bind(wx.EVT_BUTTON, self.onPause)

        self.time_choice = Choice(panel, size=(120, -1),
                                  choices=('seconds', 'minutes', 'hours'),
                                  action=self.onTimeChoice)

        self.time_choice.SetStringSelection(self.timelabel)
        self.time_ctrl  = FloatCtrl(panel, value=60.0, precision=1,
                                    size=(90, -1), action=self.onDisplayTimeVal)
        time_label = SimpleText(panel, '    Time Range: ',  minsize=(85, -1),
                                style=LSTY)

        btnsizer.Add(self.pause_btn,   0, wx.ALIGN_LEFT, 2)
        btnsizer.Add(self.resume_btn,  0, wx.ALIGN_LEFT, 2)
        btnsizer.Add(time_label,       1, wx.ALIGN_LEFT, 2)
        btnsizer.Add(self.time_ctrl,   0, wx.ALIGN_LEFT, 2)
        btnsizer.Add(self.time_choice, 0, wx.ALIGN_LEFT, 2)

        panel.SetAutoLayout(True)
        panel.SetSizer(btnsizer)
        btnsizer.Fit(panel)

    def build_menus(self):
        mbar = wx.MenuBar()
        mfile = wx.Menu()
        pp = self.plotpanel
        MenuItem(self, mfile, "&Read Configuration\tCtrl+R",
                 "Read Configuration File", self.onReadConfig)

        MenuItem(self, mfile, "&Save Data\tCtrl+S",
                 "Save Text File of Data", self.onSaveData)

        MenuItem(self, mfile, "Save Plot Image\t",
                 "Save PNG Image of Plot", pp.save_figure)

        MenuItem(self, mfile, "&Copy Image to Clipboard\tCtrl+C",
                 "Copy Plot Image to Clipboard", pp.canvas.Copy_to_Clipboard)
        mfile.AppendSeparator()


        MenuItem(self, mfile, 'Page Setup...', 'Printer Setup',
                 pp.PrintSetup)

        MenuItem(self, mfile, 'Print Preview...', 'Print Preview',
                 pp.PrintPreview)

        MenuItem(self, mfile, "&Print\tCtrl+P", "Print Plot",
                 pp.Print)
        mfile.AppendSeparator()

        MenuItem(self, mfile, "E&xit\tCtrl+Q",
                 "Exit StripChart", self.onExit)
        self.Bind(wx.EVT_CLOSE, self.onExit)

        mopt = wx.Menu()
        MenuItem(self, mopt, "Configure Plot\tCtrl+K",
                 "Configure Plot", pp.configure)
        mopt.AppendSeparator()
        MenuItem(self, mopt, "Zoom Out\tCtrl+Z",
                 "Zoom out to full data range", pp.unzoom_all)


        mhelp = wx.Menu()
        MenuItem(self, mhelp, "Quick Reference",
                 "Quick Reference ", self.onHelp)
        MenuItem(self, mhelp, "About", "About Stripchart", self.onAbout)

        mbar.Append(mfile, "File")
        mbar.Append(mopt, "Options")
        mbar.Append(mhelp, "&Help")
        self.SetMenuBar(mbar)

    def onPVshow(self, event=None, row=0):
        if not event.IsChecked():
            trace = self.plotpanel.conf.get_mpl_line(row)
            trace.set_data([], [])
            self.plotpanel.canvas.draw()
        self.needs_refresh = True

    def onPVname(self, event=None):
        self.addPV(self.pvname.GetValue())

    @EpicsFunction
    def addPV(self, name, desc=None, uselog=0, ymin=None, ymax=None):
        if name is not None and name not in self.pvlist:
            basename = str(name)
            if len(basename) < 2:
                return
            pv = get_pv(basename, callback=self.onPVChange)
            pv.get()
            self.pvs[basename] = pv
            conn = False
            if pv is not None:
                if not pv.connected:
                    pv.wait_for_connection()
                conn = pv.connected

            msg = 'PV not found: %s' % name
            if conn:
                msg = 'PV found: %s' % name
            self.pvmsg.SetLabel(msg)
            if not conn:
                return

            self.pvlist.append(name)
            self.pvdata[name] = [(time.time(), pv.get())]

            if basename.endswith('.VAL'):
                basename = basename[:-4]
            if desc is None:
                descname = basename + '.DESC'
                descpv = get_pv(descname)
                desc =  descpv.get(timeout=1.0)
            if desc is None or len(desc) < 1:
                desc = basename
            self.pv_opts[name] = (desc, uselog, ymin, ymax)

            inew = len(self.pvdata)
            new_shown = False
            for i in range(NPVS):
                choice =  self.wids[f'pv{i}']
                cur = choice.GetSelection()
                choice.Clear()
                choice.SetItems(self.pvlist)
                choice.SetSelection(cur)
                if cur == 0 and not new_shown:
                    choice.SetSelection(inew)
                    new_shown = True
                    if desc is not None:
                        self.wids[f'desc{i}'].SetValue(desc)
                    if ymin in (None, 'None'):
                        ymin = ''
                    if ymax in (None, 'None'):
                        ymax = ''
                    self.wids[f'ymin{i}'].SetValue(f"{ymin}")
                    self.wids[f'ymax{i}'].SetValue(f"{ymax}")
                    self.wids[f'uselog{i}'].SetSelection(1 if uselog else 0)

            self.needs_refresh = True

    @DelayedEpicsCallback
    def onPVChange(self, pvname=None, value=None, timestamp=None, **kw):
        if timestamp is None:
            timestamp = time.time()
        self.pvdata[pvname].append((timestamp, value))
        self.needs_refresh = True
        if len(self.pvdata[pvname]) > self.nmax:
            self.pvdata[pvname] = self.pvdata[pvname][self.ntrim:]

    def onPVchoice(self, event=None, row=0, **kws):
        pvname = self.wids[f'pv{row}'].GetStringSelection()
        if pvname in self.pv_opts:
            desc, uselog, ymin, ymax = self.pv_opts[pvname]
            if ymin in (None, 'None'):
                ymin = ''
            if ymax in (None, 'None'):
                ymax = ''
            self.wids[f'desc{row}'].SetValue(desc)
            self.wids[f'uselog{row}'].SetSelection(uselog)
            self.wids[f'ymin{row}'].SetValue(f"{ymin}")
            self.wids[f'ymax{row}'].SetValue(f"{ymax}")
        else:
            self.wids[f'desc{row}'].SetValue('')
            self.wids[f'uselog{row}'].SetSelection(0)
            self.wids[f'ymin{row}'].SetValue('')
            self.wids[f'ymax{row}'].SetValue('')
        self.needs_refresh = True
        self.force_replot = True


    def onSavePVSettings(self, event=None):
        for i in range(NPVS):
            pvname =  self.wids[f'pv{i}'].GetStringSelection()
            if pvname in (None, 'None', '-') or len(pvname) < 2:
                continue

            desc = self.wids[f'desc{i}'].GetValue()
            uselog = (1 == self.wids[f'uselog{i}'].GetSelection())
            ymin = get_bound(self.wids[f'ymin{i}'].GetValue())
            ymax = get_bound(self.wids[f'ymax{i}'].GetValue())
            color = hexcolor(self.wids[f'col{i}'].GetColour())
            if ymin in (None, 'None'):
                ymin = ''
            if ymax in (None, 'None'):
                ymax = ''
            self.pv_opts[pvname] = (desc, uselog, ymin, ymax)
        
    def onPVcolor(self, event=None, row=None, **kws):
        self.plotpanel.conf.set_trace_color(hexcolor(event.GetValue()),
                                            trace=row)
        self.needs_refresh = True

    def onPVLogwid(self, event=None, row=None, **kws):
        self.force_replot = True
        self.needs_refresh = True

    def onPVwid(self, event=None, row=None, **kws):
        self.needs_refresh = True

    def onDisplayTimeVal(self, event=None, value=None, **kws):
        new  = min(0.1, abs(value))
        self.needs_refresh = True

    def onTimeChoice(self, event=None, **kws):
        new_timelabel = event.GetString()
        curr = self.time_ctrl.GetValue()
        if self.timelabel != new_timelabel:
            denom = num = 1.0
            if self.timelabel == 'hours':
                denom = 3600.
            elif self.timelabel == 'minutes':
                denom = 60.0
            if new_timelabel == 'hours':
                num = 3600.
            elif new_timelabel == 'minutes':
                num = 60.0
            factor = denom/num
            self.timelabel = new_timelabel
            timeval = self.time_ctrl.GetValue()
            self.time_ctrl.SetValue(max(0.1, timeval*denom/num))
        self.needs_refresh = True

    def onPause(self, event=None):
        if self.paused:
            self.pause_btn.Enable()
            self.resume_btn.Disable()
        else:
            self.pause_btn.Disable()
            self.resume_btn.Enable()
        self.paused = not self.paused

    def write_message(self, s, panel=0):
        """write a message to the Status Bar"""
        self.SetStatusText(s, panel)

    def onSaveData(self, event=None):
        dlg = wx.FileDialog(self, message='Save Data to File...',
                            defaultDir = os.getcwd(),
                            defaultFile='PVStripChart.dat',
                            style=wx.FD_SAVE|wx.FD_CHANGE_DIR)
        if dlg.ShowModal() == wx.ID_OK:
            path = dlg.GetPath()
            self.SaveDataFiles(path)
            self.write_message(f'Saved data to {path}')
        dlg.Destroy()

    def SaveDataFiles(self, path):
        basename, ext = os.path.splitext(path)
        if len(ext) < 2:
            ext = '.dat'
        if ext.startswith('.'):
            ext = ext[1:]

        for pvname, data in self.pvdata.items():
            tnow = time.time()
            tmin = data[0][0]
            fname = []
            for s in pvname:
                if s not in FILECHARS:
                    s = '_'
                fname.append(s)
            fname = os.path.join("%s_%s.%s" % (basename, ''.join(fname), ext))

            buff = ["# Epics PV Strip Chart Data for PV: %s " % pvname]
            buff.append("# Current Time  = %s " % time.ctime(tnow))
            buff.append("# Earliest Time = %s " % time.ctime(tmin))
            buff.append("#------------------------------")
            buff.append("#  Timestamp         Value       Time-Current_Time(s)")
            for tx, yval in data:
                buff.append("  %.3f %16g     %.3f"  % (tx, yval, tx-tnow))

            fout = open(fname, 'w', encoding='utf-8')
            fout.write("\n".join(buff))
            fout.close()
            #dat = tnow, func(tnow)

    def onAbout(self, event=None):
        dlg = wx.MessageDialog(self, self.about_msg,
                               "About Epics PV Strip Chart",
                               wx.OK | wx.ICON_INFORMATION)
        dlg.ShowModal()
        dlg.Destroy()

    def onHelp(self, event=None):
        dlg = wx.MessageDialog(self, self.help_msg, "Epics PV Strip Chart Help",
                               wx.OK | wx.ICON_INFORMATION)
        dlg.ShowModal()
        dlg.Destroy()

    def onExit(self, event=None):
        self.timer.Stop()
        conf_pvs = []
        for pvname, dat in self.pv_opts.items():
            desc, uselog, ymin, ymax = dat
            conf_pvs.append([pvname, desc, uselog, ymin, ymax])

        if len(conf_pvs) > 0:
            self.config['pvs'] = conf_pvs
            if self.configfile is None:
                self.configfile = StripChartConfig()

            cfname = getattr(self.configfile, 'filename', None)
            if cfname is None:
                cfname = self.configfile.filename = CONFFILE

            # save a backup config file
            if Path(cfname).exists():
                nfile = cfname.replace('.yaml', '_bak.yaml')
                try:
                    shutil.copy(cfname, nfile)
                except:
                    pass

            self.configfile.write(config=self.config)

        for pv in self.pvs.values():
            pv.clear_callbacks()
            pv.disconnect()
            time.sleep(0.001)

        time.sleep(0.1)
        self.Destroy()

    def onUpdatePlot(self, event=None):
        if self.paused or not self.needs_refresh:
            return
        tnow = time.time()

        # set timescale sec/min/hour
        timescale = 1.0
        if self.time_choice.GetSelection() == 1:
            timescale  = 60
        elif self.time_choice.GetSelection() == 2:
            timescale = 3600

        tmin = self.time_ctrl.GetValue() * timescale
        tmin = tnow - tmin

        ppan = self.plotpanel

        xmin = -1
        xmax = 0
        traces = []
        nselected = 0
        for i in range(NPVS):
            pvname =  self.wids[f'pv{i}'].GetStringSelection()
            if pvname in (None, 'None', '-') or len(pvname) < 2:
                continue
            nselected += 1

        use_update = True
        if nselected < self.nplot:
            ppan.clear()
            use_update = False

        self.nplot = 0
        yaxes = 0
        for i in range(NPVS):
            pvname =  self.wids[f'pv{i}'].GetStringSelection()
            if pvname in (None, 'None', '-') or len(pvname) < 2:
                continue
            if pvname not in self.pvdata:
                continue
            yaxes = yaxes+1
            self.nplot += 1
            desc = self.wids[f'desc{i}'].GetValue()
            uselog = (1 == self.wids[f'uselog{i}'].GetSelection())
            ymin = get_bound(self.wids[f'ymin{i}'].GetValue())
            ymax = get_bound(self.wids[f'ymax{i}'].GetValue())
            color = hexcolor(self.wids[f'col{i}'].GetColour())

            if len(desc.strip()) < 1:
                desc = pvname

            dat_t  = [i[0] for i in self.pvdata[pvname]]
            dat_y  = [i[1] for i in self.pvdata[pvname]]
            if dat_t[-1] < (tnow - 30.): # value has not update for 30 second
                self.pvdata[pvname].append([tnow, dat_y[-1]])
                dat_t  = [i[0] for i in self.pvdata[pvname]]
                dat_y  = [i[1] for i in self.pvdata[pvname]]

            if len(dat_t)  < 2:
                continue

            tdat = np.array(dat_t)
            ydat = np.array(dat_y)
            mask = where(tdat > (tmin-10))
            tdat = tdat[mask]/86400.0 # convert to mpldates
            ydat = ydat[mask]

            if len(tdat)  < 2:
                continue

            yrange = max((max(ydat) - min(ydat)), 1.e-8)
            if ymin is None:
                ymin = min(ydat) - yrange*0.02
            if ymax is None:
                ymax = max(ydat) + yrange*0.02

            ylabel = 'ylabel'
            logscale = 'ylog_scale'
            if yaxes > 1:
                ylabel = f'y{yaxes}label'
                logscale = f'y{yaxes}log_scale'

            tspan = tnow - tmin
            tmin = (tmin - tspan*0.02)
            tmax = (tnow + tspan*0.02)
            use_update = pvname in self.plotted_pvs.values()
            xmin = tmin/86400.0
            xmax = tmax/86400.0
            # print(" I ", pvname, pvname in self.plotted_pvs.values(), len(tdat), len(ydat), use_update)
            if use_update and not self.force_replot:
                try:
                    ppan.update_line(yaxes-1, tdat, ydat, draw=False, yaxes=yaxes)
                    ppan.set_xylims((xmin, xmax, ymin, ymax), yaxes=yaxes)
                    ppan.conf.set_trace_color(color, trace=yaxes-1, delay_draw=True)
                    setattr(ppan.conf, ylabel, desc)
                except:
                    use_update = False

            if not use_update or self.force_replot:
                opts = {'show_legend': False, 'xlabel': 'Date / Time',
                        'drawstyle': 'steps-post',
                        'delay_draw': True, 'yaxes_tracecolor': True,
                        'use_dates': True, 'timezone': TZONE}
                opts[ylabel] = desc
                opts[logscale] = uselog and min(ydat) > 0
                plot = ppan.plot if yaxes==1 else ppan.oplot
                plot(tdat, ydat, yaxes=yaxes, color=color,
                     ymin=ymin, ymax=ymax, label=desc, **opts)
                self.plotted_pvs[i] = pvname

        snow = time.strftime("%Y-%b-%d %H:%M:%S", time.localtime())
        self.plotpanel.set_title(snow, delay_draw=True)
        self.plotpanel.canvas.draw()
        self.force_replot = False
        self.needs_refresh = False
        return

class StripChartApp(wx.App):
    def __init__(self, configfile=None, prompt=True, debug=False, **kws):
        self.configfile = configfile
        self.prompt = prompt
        self.debug = debug
        wx.App.__init__(self, **kws)

    def createApp(self):
        self.frame = StripChartFrame()
        self.frame.Show()
        self.SetTopWindow(self.frame)

    def OnInit(self):
        self.createApp()
        if self.debug:
            self.ShowInspectionTool()
        return True
