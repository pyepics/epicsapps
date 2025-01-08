#!/usr/bin/python
"""
Epics PV Logger Application, wx
"""
import os
import time
from threading import Thread
from pathlib import Path
from numpy import array, where
from functools import partial
from collections import namedtuple

from matplotlib.dates import date2num

import wx
import wx.lib.colourselect  as csel
import wx.lib.mixins.inspection
import wx.lib.filebrowsebutton as filebrowse
FileBrowserHist = filebrowse.FileBrowseButtonWithHistory

from epics import get_pv
from epics.wx import EpicsFunction, DelayedEpicsCallback

from wxutils import (GridPanel, SimpleText, MenuItem, OkCancel, Popup,
                     FileOpen, SavedParameterDialog, Font, FloatSpin,
                     HLine, SelectWorkdir, GUIColors, COLORS, Button,
                     Choice, FileSave, FileCheckList, LEFT, RIGHT, pack)

from pyshortcuts import debugtimer, uname
from epicsapps.utils import get_pvtypes, get_pvdesc, normalize_pvname


from .configfile import ConfigFile
from .logfile import read_logfile, read_logfolder

from wxmplot import PlotPanel, PlotFrame
from wxmplot.colors import hexcolor

from ..utils import (SelectWorkdir, get_icon,
                     get_configfolder,
                     get_default_configfile, load_yaml,
                     read_recents_file, write_recents_file)

CONFIG_FILE = 'pvlog.toml'
ICON_FILE = 'logging.ico'
FILECHARS = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_'
PlotWindowChoices = [f'Window {i+1}' for i in range(10)]
PLOT_COLORS = ('#1f77b4', '#d62728', '#2ca02c', '#ff7f0e', '#9467bd',
               '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf')


STY  = wx.GROW|wx.ALL
LSTY = wx.ALIGN_LEFT|wx.EXPAND|wx.ALL
CSTY = wx.ALIGN_CENTER
FRAME_STYLE = wx.DEFAULT_FRAME_STYLE|wx.TAB_TRAVERSAL

FONTSIZE = 10
FONTSIZE_FW = 10
if uname == 'win':
    FONTSIZE = 10
    FONTSIZE_FW = 11
elif uname == 'darwin':
    FONTSIZE = 11
    FONTSIZE_FW = 12


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

YAML_WILDCARD = 'PVLogger Config Files (*.yaml)|*.yaml|All files (*.*)|*.*'


class PVLoggerFrame(wx.Frame):
    default_colors = ((0, 0, 0), (0, 0, 255), (255, 0, 0),
                      (0, 0, 0), (255, 0, 255), (0, 125, 0))

    about_msg =  """Epics PV Logger
Matt Newville <newville@cars.uchicago.edu>
"""

    def __init__(self, configfile=None):

        self.parent = None
        wx.Frame.__init__(self, None, -1, 'Epics PV Logger Application',
                          style=FRAME_STYLE, size=(1000, 550))

        self.plot_windows = []
        self.pvdata = {}
        self.pvs = []
        self.wids = {}
        self.subframes = {}
        self.read_threads = {}
        self.log_folder = None
        self.create_frame()

    def create_frame(self,size=(1000, 550), **kwds):
        self.build_statusbar()
        self.build_menus()


        splitter = wx.SplitterWindow(self, style=wx.SP_LIVE_UPDATE)
        splitter.SetMinimumPaneSize(220)

        lpanel = wx.Panel(splitter)
        lpanel.SetMinSize((325, 400))

        rpanel = wx.Panel(splitter)
        rpanel.SetMinSize((550, 000))
        rpanel.SetSize((675, 450))

        # left panel
        ltop = wx.Panel(lpanel)
        sel_none = Button(ltop, 'Select None', size=(150, 30), action=self.onSelNone)
        sel_all  = Button(ltop, 'Select All',  size=(150, 30), action=self.onSelAll)

        ltsizer = wx.BoxSizer(wx.HORIZONTAL)
        ltsizer.Add(sel_all,  1, LEFT|wx.GROW, 1)
        ltsizer.Add(sel_none, 1, LEFT|wx.GROW, 1)
        pack(ltop, ltsizer)

        self.pvlist = FileCheckList(lpanel, main=self,
                                      select_action=self.onShowPV,
                                      remove_action=self.onRemovePV)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(ltop, 0, LEFT|wx.GROW, 1)
        sizer.Add(self.pvlist, 1, LEFT|wx.GROW|wx.ALL, 1)
        pack(lpanel, sizer)

        # right panel
        panel = GridPanel(rpanel, ncols=6, nrows=10, pad=3, itemstyle=LEFT)
        sizer = wx.GridBagSizer(3, 3)
        sizer.SetVGap(3)
        sizer.SetHGap(3)

        # self.font_fixedwidth = wx.Font(FONTSIZE_FW, wx.MODERN, wx.NORMAL, wx.BOLD)
        self.font = wx.Font(FONTSIZE, wx.MODERN, wx.NORMAL, wx.BOLD)
        self.SetFont(self.font)
        wids = self.wids
        title = SimpleText(panel, ' PV Logger Viewer', font=Font(FONTSIZE+2),
                           size=(550, -1),  colour=COLORS['title'], style=LEFT)

        wids['work_folder'] = SimpleText(panel, ' <no working folder> ',
                                         font=Font(FONTSIZE+1),
                                         size=(550, -1), style=LEFT)


        self.last_plot_type = 'one'
        opts = {'size': (150, -1)}
        wids['plotone'] = Button(panel, 'Plot PV 1 ', action=self.onPlotOne, **opts)
        wids['plotsel'] = Button(panel, 'Plot Selected ', action=self.onPlotSel, **opts)

        wids['plot_win']  = Choice(panel, choices=PlotWindowChoices, **opts)
        wids['plot_win'].SetStringSelection('1')

        wids['use_sel'] = Button(panel, ' Use Selected PVs ',
                                 action=self.onUseSelected, **opts)
        wids['clear_sel'] = Button(panel, ' Clear PVs 2, 3, 4 ',
                                   action=self.onClearSelected, **opts)

        wids['use_inst'] = Button(panel, 'Select These PVs ',
                                  action=self.onSelectInstPVs, **opts)
        opts['size'] = (300, -1)
        opts['choices'] = []
        wids['instruments'] = Choice(panel, action=self.onSelectInst, **opts)

        opts['action'] = self.onUpdatePlot
        for i in range(4):
            wids[f'pv{i+1}'] = Choice(panel, **opts)
            wids[f'col{i+1}'] = csel.ColourSelect(panel, -1, '',PLOT_COLORS[i],
                                                  size=(25, 25))
            wids[f'col{i+1}'].Bind(csel.EVT_COLOURSELECT,
                                   partial(self.onPVcolor, row=i+1))

        def slabel(txt):
            return wx.StaticText(panel, label=txt, size=(125, -1))

        panel.Add(title, style=LEFT, dcol=6)
        panel.Add(slabel(' Folder: '), dcol=1, newrow=True)
        panel.Add(wids['work_folder'], dcol=6)
        panel.Add((5, 5))
        panel.Add(HLine(panel, size=(650, 3)), dcol=6, newrow=True)
        panel.Add((5, 5))

        panel.Add(slabel(' Instruments: '), dcol=1, newrow=True)
        panel.Add(wids['instruments'], dcol=2)
        panel.Add(wids['use_inst'], dcol=1)

        panel.Add((5, 5))
        panel.Add(HLine(panel, size=(650, 3)), dcol=6, newrow=True)
        panel.Add((5, 5))
        panel.Add(slabel(' PVs: '), dcol=1, newrow=True)
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
        panel.Add(HLine(panel, size=(650, 3)), dcol=6, newrow=True)
        panel.Add((5, 5))
        panel.Add(slabel(' Plot: '), dcol=1, newrow=True)
        panel.Add(wids['plotone'], dcol=1)
        panel.Add(wids['plotsel'], dcol=1)
        panel.Add(wids['plot_win'])

        panel.pack()

        try:
            self.SetIcon(wx.Icon(get_icon('logging'), wx.BITMAP_TYPE_ICO))
        except:
            pass

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add((5, 5), 0, LEFT, 3)
        sizer.Add(panel, 0, LEFT, 3)
        sizer.Add((5, 5), 0, LEFT, 3)
        pack(rpanel, sizer)

        # rpanel.SetupScrolling()

        splitter.SplitVertically(lpanel, rpanel, 1)
        mainsizer = wx.BoxSizer(wx.VERTICAL)
        mainsizer.Add(splitter, 1, wx.GROW|wx.ALL, 5)
        pack(self, mainsizer)
        self.SetSize((1000, 550))
        self.read_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.onReadTimer, self.read_timer)

        display0 = wx.Display(0)
        client_area = display0.ClientArea
        xmin, ymin, xmax, ymax = client_area
        xpos = int((xmax-xmin)*0.02) + xmin
        ypos = int((ymax-ymin)*0.04) + ymin
        self.SetPosition((xpos, ypos))
        self.Show()
        self.Raise()
        self.read_timer.Start(1000)
        wx.CallAfter(self.ShowPlotWin1)

    def onReadTimer(self, event=None):
        if len(self.read_threads) > 0:
            dead = []
            for name, rthread in self.read_threads.items():
                if not rthread.is_alive():
                    dead.append(name)
            for name in dead:
                self.read_threads.pop(name)
        if len(self.read_threads) == 0 and self.log_folder is not None:
            n = 0
            for pvname in self.log_folder.pvs:
                if pvname not in self.pvdata:
                    n += 1
                    rthread = Thread(target=self.get_pvdata,
                                     args=(pvname,), name=pvname)
                    rthread.start()
                    self.read_threads[pvname] = rthread
                    if n >= 2:
                        break

    def build_statusbar(self):
        sbar = self.CreateStatusBar(2, wx.CAPTION)
        sfont = sbar.GetFont()
        sfont.SetWeight(wx.BOLD)
        sfont.SetPointSize(10)
        sbar.SetFont(sfont)
        self.SetStatusWidths([-5, -2])
        self.SetStatusText('', 0)

    def show_subframe(self, name, frameclass, **opts):
        shown = False
        if name in self.subframes:
            try:
                self.subframes[name].Raise()
                shown = True
            except:
                del self.subframes[name]
        if not shown:
            self.subframes[name] = frameclass(self, **opts)
            self.subframes[name].Raise()

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

    def onSelectInstPVs(self, event=None):
        iname = self.wids['instruments'].GetStringSelection()
        self.pvlist.select_none()
        self.pvlist.SetCheckedStrings(self.log_folder.instruments[iname])


    def onUpdatePlot(self, event=None):
        print("update plot ")

    def onSelNone(self, event=None):
        self.pvlist.select_none()

    def onSelAll(self, event=None):
        self.pvlist.select_all()


    def onRemovePV(self, dname=None, event=None):
        print("Remove PV")

    def onShowPV(self, event=None, label=None):
        name = event.GetString()
        self.wids['pv1'].SetStringSelection(name)

        if name in self.read_threads:
            rt = self.read_threads.pop(name)
            if rt.is_alive():
                rt.join()

        rthread = Thread(target=self.get_pvdata, args=(name,), name=name)
        rthread.start()
        self.read_threads[name] = rthread

    def get_pvdata(self, pvname, force=False):
        """get PVdata, caching until it changes"""
        if pvname not in self.pvdata:
            self.pvdata[pvname] = {'timestamp': 0, 'data': None}
        last_tstamp = self.pvdata[pvname]['timestamp']

        logfile = self.log_folder.pvs[pvname][0]
        this_tstamp = os.stat(logfile).st_mtime
        if force:
            last_tstamp = -1
        if this_tstamp > last_tstamp or self.pvdata[pvname]['data'] is None:
            try:
                print("  ... real read ... ", logfile)
                data = read_logfile(logfile)
            except OSError:
                print("OS ERROR ON READ?")
                data = None
            self.pvdata[pvname]['timestamp'] = this_tstamp
            self.pvdata[pvname]['data'] = data
        return self.pvdata[pvname]['data']

    def ShowPlotWin1(self, event=None):
        wname = 'Window 1'
        self.show_subframe(wname, PlotFrame, title=f'PVLogger Plot {wname}')

        xpos, ypos = self.GetPosition()
        xsiz, ysiz = self.GetSize()
        x = xpos + xsiz*1.025
        y = ypos + ysiz*0.025
        dlims = [0, 5000, 0, 5000]
        if y+0.75*ysiz > dlims[3]:
            y = 40+max(40, 40+ysiz*(off-0.5))
        if x+0.75*xsiz > dlims[1]:
            x = 20+max(10, 10+xpos+xsiz*(off-0.5))
        self.subframes[wname].SetPosition((int(x), int(y)))


    def onPlotOne(self, event=None):
        wname = self.wids['plot_win'].GetStringSelection()
        self.show_subframe(wname, PlotFrame, title=f'PVLogger Plot {wname}')

        pvname = self.wids['pv1'].GetStringSelection()
        info = self.log_folder.pvs[pvname]
        label = info[1]

        if pvname in self.read_threads:
            rt = self.read_threads.pop(pvname)
            if rt.is_alive():
                rt.join()

        data = self.get_pvdata(pvname)
        if data is None:
            data = self.get_pvdata(pvname, force=True)

        col   = self.wids['col1'].GetColour()
        hcol = hexcolor(col)

        opts = {'use_dates': True, 'show_legend': True,
                'yaxes':1, 'label': label, 'xlabel': 'time',
                'title':  self.log_folder.fullpath,
                'linewidth': 2.5, # 'marker': '+',
                'theme': 'white-background',
                'drawstyle': 'steps-post', 'colour':hcol,
                'ylabel': f'{label} ({pvname})' }
        print("Plot 1  start ", len(data.value), time.ctime())
        self.subframes[wname].plot(data.mpldates, data.value, **opts)
        print("Plot 1  done ", time.ctime())

        self.subframes[wname].Show()
        self.subframes[wname].Raise()


    def onPlotSel(self, event=None):
        wname = self.wids['plot_win'].GetStringSelection()
        self.show_subframe(wname, PlotFrame, title=f'PVLogger Plot {wname}')
        pframe = self.subframes[wname]
        yaxes = 0
        for i in range(4):
            pvname = self.wids[f'pv{i+1}'].GetStringSelection()
            if pvname == 'None':
                continue
            if pvname in self.read_threads:
                rt = self.read_threads.pop(pvname)
                if rt.is_alive():
                    rt.join()

            yaxes += 1
            info = self.log_folder.pvs[pvname]
            label = info[1]
            data = self.get_pvdata(pvname)
            if data is None:
                data = self.get_pvdata(pvname, force=True)


            col   = self.wids[f'col{i+1}'].GetColour()
            hcol = hexcolor(col)

            opts = {'use_dates': True, 'show_legend': True,
                    'yaxes_tracecolor': True,
                    'yaxes':yaxes, 'label': label, 'xlabel': 'time',
                    'title':  self.log_folder.fullpath,
                    'linewidth': 2.5, # 'marker': '+',
                    'theme': 'white-background',
                    'drawstyle': 'steps-post', 'colour':hcol}
            plot = pframe.oplot
            if yaxes == 1:
                plot = pframe.plot
                opts['ylabel'] = f'{label} ({pvname})'
            else:
                opts[f'y{yaxes}label'] = f'{label} ({pvname})'
            plot(data.mpldates, data.value, **opts)
        self.subframes[wname].Show()
        self.subframes[wname].Raise()



    def build_menus(self):
        mdata = wx.Menu()
        mcollect = wx.Menu()
        MenuItem(self, mdata, "&Open PVLogger Folder\tCtrl+O",
                 "Open PVLogger Folder", self.onLoadFolder)

        mdata.AppendSeparator()
        MenuItem(self, mdata, "Inspect", "WX Inspect", self.onWxInspect)


        MenuItem(self, mdata, "E&xit\tCtrl+X", "Exit PVLogger", self.onExit)
        self.Bind(wx.EVT_CLOSE, self.onExit)

        MenuItem(self, mcollect, "&Configure Data Collection\tCtrl+C",
                 "Configure Data Collection", self.onEditConfig)
        mcollect.AppendSeparator()
        MenuItem(self, mcollect, "&Run Data Collection\tCtrl+R",
                 "Start Data Collection", self.onCollect)

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
        self.wids['work_folder'].SetLabel(folder.fullpath)
        os.chdir(folder.fullpath)

        for pvname in self.log_folder.pvs:
            self.pvlist.Append(pvname)

        def update_choice(wid, values, default=0):
            cur = wid.GetStringSelection()
            wid.Clear()
            wid.SetItems(values)
            if cur in values:
                wid.SetStringSelection(cur)
            else:
                wid.SetSelection(default)

        pvnames = ['None',]
        pvnames.extend(self.log_folder.pvs)
        update_choice(self.wids['instruments'], list(self.log_folder.instruments))
        update_choice(self.wids['pv1'], pvnames, default=1)
        update_choice(self.wids['pv2'], pvnames)
        update_choice(self.wids['pv3'], pvnames)
        update_choice(self.wids['pv4'], pvnames)

    def onCollect(self, event=None):
        print("on Collect")

    def onEditConfig(self, event=None):
        print("on EditConfig")

    def onTraceColor(self, trace, color, **kws):
        irow = self.get_current_traces()[trace][0] - 1
        self.colorsels[irow].SetColour(color)

    def onSide(self, event=None, **kws):
        self.needs_update = True
        self.force_redraw  = True

    def onPVshow(self, event=None, row=0):
        if not event.IsChecked():
            trace = self.plotpanel.conf.get_mpl_line(row)
            trace.set_data([], [])
            self.plotpanel.canvas.draw()
        self.needs_refresh = True


    def onPVchoice(self, event=None, row=None, **kws):
        self.needs_refresh = True
        pvname = self.pvchoices[row].GetStringSelection()
        if pvname in self.pv_desc:
            self.pvlabels[row].SetValue(self.pv_desc[pvname])
        for i in range(len(self.pvlist)+1):
            try:
                trace = self.plotpanel.conf.get_mpl_line(row-1)
                trace.set_data([], [])
            except:
                pass
        self.plotpanel.conf.set_viewlimits()

    def onPVcolor(self, event=None, row=None, **kws):
        self.plotpanel.conf.set_trace_color(hexcolor(event.GetValue()),
                                            trace=row-1)
        self.needs_refresh = True

    def write_message(self, s, panel=0):
        """write a message to the Status Bar"""
        self.SetStatusText(s, panel)


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
        self.read_timer.Stop()
        for pv in self.pvs:
            pv.clear_callbacks()
            pv.disconnect()
            time.sleep(0.001)
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
