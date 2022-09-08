#!/usr/bin/python
"""
Epics Strip Chart application
"""
import os
import time
from numpy import array, where
from functools import partial

import wx
import wx.lib.colourselect  as csel

from epics import get_pv
from epics.wx import EpicsFunction, DelayedEpicsCallback

from wxutils import (GridPanel, SimpleText, MenuItem, OkCancel, Popup,
                     FileOpen, SavedParameterDialog, Font, FloatSpin,
                     FloatCtrl, Choice, YesNo, TextCtrl)

from wxmplot.plotpanel import PlotPanel
from wxmplot.colors import hexcolor

from ..utils import SelectWorkdir, get_icon
ICON_FILE = 'stripchart.ico'
FILECHARS = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_'

BGCOL  = (250, 250, 240)

POLLTIME = 50

STY  = wx.GROW|wx.ALL
LSTY = wx.ALIGN_LEFT|wx.EXPAND|wx.ALL
CSTY = wx.ALIGN_CENTER

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


class StripChartFrame(wx.Frame):
    default_colors = ((0, 0, 0), (0, 0, 255), (255, 0, 0),
                      (0, 0, 0), (255, 0, 255), (0, 125, 0))

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

    def __init__(self, parent=None):
        self.pvdata = {}
        self.pvs = []
        self.pvlist = [' -- ']
        self.pvwids = [None]
        self.pvchoices = [None]
        self.pvlabels  = [None]
        self.pv_desc   = {}
        self.colorsels = []
        self.plots_drawn = [False]*10
        self.needs_refresh = False
        self.force_redraw  = False
        self.paused = False

        self.tmin = -60.0
        self.timelabel = 'seconds'

        self.create_frame(parent)

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.onUpdatePlot, self.timer)
        self.timer.Start(POLLTIME)

    def create_frame(self, parent, size=(750, 450), **kwds):
        self.parent = parent

        kwds['style'] = wx.DEFAULT_FRAME_STYLE|wx.TAB_TRAVERSAL
        kwds['size']  = size
        wx.Frame.__init__(self, parent, -1, 'Epics PV Strip Chart', **kwds)

        self.build_statusbar()

        self.plotpanel = PlotPanel(self, trace_color_callback=self.onTraceColor)
        self.plotpanel.messenger = self.write_message

        self.build_pvpanel()
        self.build_btnpanel()
        self.build_menus()
        self.SetBackgroundColour(wx.Colour(*BGCOL))

        mainsizer = wx.BoxSizer(wx.VERTICAL)

        p1 = wx.Panel(self)
        p1.SetBackgroundColour(wx.Colour(*BGCOL))
        s1 = wx.BoxSizer(wx.HORIZONTAL)
        label = SimpleText(p1, ' Add PV:')
        self.pvname = TextCtrl(p1, '', size=(250, -1), action=self.onPVname)
        self.pvmsg = SimpleText(p1, '   ',  minsize=(75, -1),
                                style=LSTY|wx.EXPAND)
        s1.Add(label,      0,  wx.ALIGN_LEFT|wx.ALIGN_CENTER, 10)
        s1.Add(self.pvname, 0,  wx.ALIGN_LEFT|wx.ALIGN_CENTER, 10)
        s1.Add(self.pvmsg, 1,  wx.ALIGN_LEFT|wx.ALIGN_CENTER, 10)
        p1.SetAutoLayout(True)
        p1.SetSizer(s1)
        s1.Fit(p1)

        mainsizer.Add(p1,             0, wx.GROW|wx.EXPAND, 5)
        mainsizer.Add(wx.StaticLine(self, size=(250, -1),
                                    style=wx.LI_HORIZONTAL),
                      0, wx.EXPAND|wx.GROW, 8)
        mainsizer.Add(self.pvpanel,   0, wx.EXPAND, 5)
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
        panel = self.pvpanel = wx.Panel(self)
        panel.SetBackgroundColour(wx.Colour(*BGCOL))
        sizer = self.pvsizer = wx.GridBagSizer(4, 5)

        name = SimpleText(panel, ' PV:  ',    minsize=(65, -1), style=LSTY)
        colr = SimpleText(panel, ' Color ',   minsize=(50, -1), style=LSTY)
        logs = SimpleText(panel, ' Log? ',    minsize=(50, -1), style=LSTY)
        ymin = SimpleText(panel, ' Y Min ',   minsize=(85, -1), style=LSTY)
        ymax = SimpleText(panel, ' Y Max ',   minsize=(85, -1), style=LSTY)
        desc = SimpleText(panel, ' Label ',   minsize=(85, -1), style=LSTY)
        side = SimpleText(panel, ' Side  ',   minsize=(85, -1), style=LSTY)

        sizer.Add(name, (0, 0), (1, 1), LSTY|wx.EXPAND, 2)
        sizer.Add(colr, (0, 1), (1, 1), LSTY, 1)
        sizer.Add(logs, (0, 2), (1, 1), LSTY, 1)
        sizer.Add(ymin, (0, 3), (1, 1), LSTY, 1)
        sizer.Add(ymax, (0, 4), (1, 1), LSTY, 1)
        sizer.Add(desc, (0, 5), (1, 1), LSTY, 1)
        sizer.Add(side, (0, 6), (1, 1), LSTY, 1)

        self.npv_rows = 0
        for i in range(4):
            self.AddPV_row()

        panel.SetAutoLayout(True)
        panel.SetSizer(sizer)
        sizer.Fit(panel)

    def build_btnpanel(self):
        panel = self.btnpanel = wx.Panel(self, )
        panel.SetBackgroundColour(wx.Colour(*BGCOL))

        btnsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.pause_btn  = wx.Button(panel, label='Pause',  size=(100, 30))
        self.resume_btn = wx.Button(panel, label='Resume', size=(100, 30))
        self.resume_btn.Disable()

        self.pause_btn.Bind(wx.EVT_BUTTON, self.onPause)
        self.resume_btn.Bind(wx.EVT_BUTTON, self.onPause)

        time_label = SimpleText(panel, '    Time Range: ',  minsize=(85, -1),
                                style=LSTY)
        self.time_choice = Choice(panel, size=(120, -1),
                                  choices=('seconds', 'minutes', 'hours'),
                                  action=self.onTimeChoice)
        self.time_choice.SetStringSelection(self.timelabel)

        self.time_ctrl  = FloatCtrl(panel, value=-self.tmin, precision=2,
                                    size=(90, -1), action=self.onDisplayTimeVal)
        
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
        MenuItem(self, mfile, "&Save Data\tCtrl+S",
                 "Save PNG Image of Plot", self.onSaveData)

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

    def AddPV_row(self):
        i = self.npv_rows = self.npv_rows + 1

        panel = self.pvpanel
        sizer = self.pvsizer
        pvchoice = Choice(panel, choices=self.pvlist, size=(150, -1))
        pvchoice.SetSelection(0)
        logs = Choice(panel, choices=('No', 'Yes'), size=(50, -1))
        logs.SetSelection(0)
        ymin = wx.TextCtrl(panel, -1, '', size=(75, -1), style=wx.TE_PROCESS_ENTER)
        ymax = wx.TextCtrl(panel, -1, '', size=(75, -1), style=wx.TE_PROCESS_ENTER)
        desc = wx.TextCtrl(panel, -1, '', size=(150, -1))
        side = Choice(panel, choices=('left', 'right'),
                      action=self.onSide, size=(80, -1))
        side.SetSelection(0) # (i-1)%2)

        if i > 2:
            logs.Disable()
            ymin.Disable()
            ymax.Disable()
            desc.Disable()
            side.Disable()

        colval = (0, 0, 0)
        if i < len(self.default_colors):
            colval = self.default_colors[i]
        colr = csel.ColourSelect(panel, -1, '', colval)
        self.colorsels.append(colr)

        sizer.Add(pvchoice, (i, 0), (1, 1), LSTY, 3)
        sizer.Add(colr,     (i, 1), (1, 1), CSTY, 3)
        sizer.Add(logs,     (i, 2), (1, 1), CSTY, 3)
        sizer.Add(ymin,     (i, 3), (1, 1), CSTY, 3)
        sizer.Add(ymax,     (i, 4), (1, 1), CSTY, 3)
        sizer.Add(desc,     (i, 5), (1, 1), CSTY, 3)
        sizer.Add(side,     (i, 6), (1, 1), CSTY, 3)

        pvchoice.Bind(wx.EVT_CHOICE,     partial(self.onPVchoice, row=i))
        colr.Bind(csel.EVT_COLOURSELECT, partial(self.onPVcolor, row=i))
        logs.Bind(wx.EVT_CHOICE,         self.onPVwid)
        ymin.Bind(wx.EVT_TEXT_ENTER,     self.onPVwid)
        ymax.Bind(wx.EVT_TEXT_ENTER,     self.onPVwid)

        self.pvchoices.append(pvchoice)
        self.pvlabels.append(desc)
        self.pvwids.append((logs, colr, ymin, ymax, desc, side))

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

    def onPVname(self, event=None):
        self.addPV(self.pvname.GetValue())

    @EpicsFunction
    def addPV(self, name):
        if name is not None and name not in self.pvlist:
            basename = str(name)
            pv = get_pv(basename, callback=self.onPVChange)
            pv.get()
            self.pvs.append(pv)
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
            descname = basename + '.DESC'
            descpv = get_pv(descname)
            desc =  descpv.get(timeout=1.0)
            if desc is None or len(desc) < 1:
                desc = basename

            self.pv_desc[basename] = desc

            i_new = len(self.pvdata)
            new_shown = False
            for ix, choice in enumerate(self.pvchoices):
                if choice is None:
                    continue
                cur = choice.GetSelection()
                choice.Clear()
                choice.SetItems(self.pvlist)
                choice.SetSelection(cur)
                if cur == 0 and not new_shown:
                    choice.SetSelection(i_new)
                    self.pvlabels[ix].SetValue(desc)
                    new_shown = True
            self.needs_refresh = True
            
    @DelayedEpicsCallback
    def onPVChange(self, pvname=None, value=None, timestamp=None, **kw):
        if timestamp is None:
            timestamp = time.time()
        self.pvdata[pvname].append((timestamp, value))
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
        # if row == 1:
        #    self.plotpanel.set_y2label('')
        self.plotpanel.conf.set_viewlimits()

        
    def onPVcolor(self, event=None, row=None, **kws):

        self.plotpanel.conf.set_trace_color(hexcolor(event.GetValue()),
                                            trace=row-1)
        self.needs_refresh = True

    def onPVwid(self, event=None, row=None, **kws):
        self.needs_refresh = True

    def onDisplayTimeVal(self, event=None, value=None, **kws):
        new  = -abs(value)
        if abs(new) < 0.1:
            new = -0.1
        if abs(new - self.tmin) > 1.e-3*max(new, self.tmin):
            new = new
        self.tmin = new

        self.plotpanel.axes.set_xlim(self.tmin, 0)
        try:
            for axes in self.plotpanel.fig.get_axes():
                self.plotpanel.user_limits[axes][0] = self.tmin
                self.plotpanel.user_limits[axes][1] = 0
        except:
            pass
        self.needs_refresh = True

    def onTimeChoice(self, event=None, **kws):
        newval = event.GetString()
        denom, num = 1.0, 1.0
        if self.timelabel != newval:
            if self.timelabel == 'hours':
                denom = 3600.
            elif self.timelabel == 'minutes':
                denom = 60.0
            if newval == 'hours':
                num = 3600.
            elif newval == 'minutes':
                num = 60.0
        
            self.timelabel = newval
            timeval = self.time_ctrl.GetValue()
            self.time_ctrl.SetValue(timeval * denom/num)
            self.tmin = -timeval*denom
            self.plotpanel.set_xlabel('Elapsed Time (%s)' % self.timelabel)
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
            self.write_message('Saved data to %s' % path)
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

            fout = open(fname, 'w')
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
        for pv in self.pvs:
            pv.clear_callbacks()
            pv.disconnect()
            time.sleep(0.001)
        self.Destroy()

    def get_current_traces(self):
        "return list of current traces"
        traces = []   # to be shown
        for irow, s in enumerate(self.pvchoices):
            if s is not None:
                ix = s.GetSelection()
                if ix > 0:
                    name = self.pvlist[ix]
                    logs  = 1 == self.pvwids[irow][0].GetSelection()
                    color = self.pvwids[irow][1].GetColour()
                    ymin  = get_bound(self.pvwids[irow][2].GetValue())
                    ymax  = get_bound(self.pvwids[irow][3].GetValue())
                    desc  = self.pvwids[irow][4].GetValue()
                    side  = self.pvwids[irow][5].GetSelection()
                    traces.append((irow, name, logs, color, ymin, ymax, desc, side))
        return traces

    def onUpdatePlot(self, event=None):
        if self.paused or not self.needs_refresh:
            return
        tnow = time.time()
        for pvname, data in self.pvdata.items():
            if (tnow - data[-1][0]) > 15.0:
                print("Append Data at ", tnonw, data[-1])
                self.pvdata[pvname].append((tnow, data[-1][1]))

        # set timescale sec/min/hour
        timescale = 1.0
        if self.time_choice.GetSelection() == 1:
            timescale  = 1./60
        elif self.time_choice.GetSelection() == 2:
            timescale = 1./3600

        ylabelset, y2labelset = False, False
        xlabel = 'Elapsed Time (%s)' % self.timelabel
        itrace = -1
        update_failed = False
        hasplot = False
        span1 = (1, 0)
        did_update = False
        left_axes = self.plotpanel.axes
        # right_axes = self.plotpanel.get_right_axes()
        for tracedata in self.get_current_traces():
            irow, pname, uselog, color, ymin, ymax, desc, xside = tracedata
            if len(desc.strip() ) < 1:
                desc = pname
            if pname not in self.pvdata:
                continue
            itrace += 1
            if len(self.plots_drawn) < itrace:
                self.plots_drawn.extend([False]*3)
            side = 'left'
            axes = left_axes
            # if xside == 1:
            #     side = 'right'
            #     axes = right_axes

            data = self.pvdata[pname][:]
            if len(data)  < 2:
                update_failed = True
                continue
            tdat = timescale * (array([i[0] for i in data]) - tnow)
            mask = where(tdat > self.tmin)
            if (len(mask[0]) < 2 or
                ((abs(min(tdat)) / abs(1 -self.tmin)) > 0.1)):
                # data.append((time.time(), data[0][-1]))
                tdat = timescale*(array([i[0] for i in data]) - tnow)
                mask = where(tdat > self.tmin)
                
            i0 = mask[0][0]
            if i0 > 0:
                i0 = i0-1
            i1 = mask[0][-1] + 1
            tdat = timescale*(array([i[0] for i in data[i0:i1]]) - tnow)
            ydat = array([i[1] for i in data[i0:i1]])

            if len(ydat)  < 2:
                update_failed = True
                continue
            if ymin is None:
                ymin = min(ydat)
            if ymax is None:
                ymax = max(ydat)
            # print(pvname, ymin, ymax, i0, i1)
            # print(' -> ', ydat)
            # for more than 2 plots, scale to left hand axis
            if itrace ==  0:
                span1 = (ymax-ymin, ymin)
                if span1[0]*ymax < 1.e-6:
                    update_failed = True
                    continue
            elif itrace > 1:
                yr = abs(ymax-ymin)
                if yr > 1.e-9:
                    ydat = span1[1] + 0.99*(ydat - ymin)*span1[0]/yr
                ymin, ymax = min(ydat), max(ydat)

            if self.needs_refresh:
                ppnl = self.plotpanel
                # if side == 'left':
                #     ppnl.set_ylabel(desc)
                # elif side == 'right':
                #     ppnl.set_y2label(desc)
                if self.force_redraw or not self.plots_drawn[itrace]:
                    self.force_redraw = False
                    plot = ppnl.oplot
                    if itrace == 0:
                        plot = ppnl.plot
                    try:
                        plot(tdat, ydat, drawstyle='steps-post', side=side,
                             ylog_scale=uselog, color=color,
                             xmin=self.tmin, xmax=0,
                             show_legend=True,
                             xlabel=xlabel, label=desc)
                        self.plots_drawn[itrace] = True
                    except:
                        update_failed = True
                else:
                    try:
                        ppnl.update_line(itrace, tdat, ydat, draw=False,
                                         update_limits=False)
                        axes.set_ylim((ymin, ymax), emit=False)
                        did_update = True
                    except:
                        update_failed = True
                if uselog and min(ydat) > 0:
                    axes.set_yscale('log', basey=10)
                else:
                    axes.set_yscale('linear')

        snow = time.strftime("%Y-%b-%d %H:%M:%S", time.localtime())
        self.plotpanel.set_title(snow, delay_draw=True)

        if did_update:
            self.plotpanel.canvas.draw()

        self.needs_refresh = update_failed
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
