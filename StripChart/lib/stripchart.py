#!/usr/bin/python
import os
import sys
import time
import numpy
import wx
import wx.lib.colourselect  as csel

import epics
import epics.wx
from epics.wx.utils import  SimpleText, Closure, FloatCtrl

from mplot.plotpanel import PlotPanel
from mplot.colors import hexcolor
from mplot.utils import LabelEntry


VALID_FILECHARS = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_'

BGCOL  = (250,250,240)

POLLTIME = 100

STY  = wx.GROW|wx.ALL|wx.ALIGN_CENTER_VERTICAL
LSTY = wx.ALIGN_LEFT|wx.EXPAND|wx.ALL|wx.ALIGN_CENTER_VERTICAL
CSTY = wx.ALIGN_CENTER|wx.ALIGN_CENTER_VERTICAL

class MyChoice(wx.Choice):
    def __init__(self, parent, choices=('No', 'Yes'), defaultyes=True, size=(75, -1)):
        wx.Choice.__init__(self, parent, -1, size=size)
        self.choices = choices
        self.Clear()
        self.SetItems(self.choices)
        self.SetSelection({False:0, True:1}[defaultyes])

    def SetChoices(self, choices):
        self.Clear()
        self.SetItems(choices)
        self.choices = choices

    def Select(self, choice):
        if isinstance(choice, int):
            self.SetSelection(choice)
        elif choice in self.choices:
            self.SetSelection(self.choices.index(choice))

class Menu_IDs:
    def __init__(self):
        self.EXIT   = wx.NewId()
        self.SAVE_IMG = wx.NewId()
        self.SAVE_DAT = wx.NewId()
        self.CONFIG = wx.NewId()
        self.UNZOOM = wx.NewId()
        self.HELP   = wx.NewId()
        self.ABOUT  = wx.NewId()
        self.PRINT  = wx.NewId()
        self.PSETUP = wx.NewId()
        self.PREVIEW= wx.NewId()
        self.CLIPB  = wx.NewId()
        self.SELECT_COLOR = wx.NewId()
        self.SELECT_SMOOTH= wx.NewId()

class StripChart(wx.Frame):
    default_colors = ((0, 0, 0), (0, 0, 255), (255, 0, 0), (0, 0, 0), (255, 0, 255), (0, 125, 0))

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
        self.pvlist = [' -- ']
        self.pvwids = [None]
        self.pvchoices = [None]
        self.colorsels = []

        self.needs_refresh = False
        self.paused = False

        self.tmin = -60.0
        self.timelabel = 'seconds'

        self.create_frame(parent)

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.onUpdatePlot, self.timer)
        self.timer.Start(POLLTIME)

    def create_frame(self, parent, size=(700, 450), **kwds):
        self.parent = parent

        kwds['style'] = wx.DEFAULT_FRAME_STYLE
        kwds['size']  = size
        wx.Frame.__init__(self, parent, -1, 'Epics PV Strip Chart', **kwds)

        self.build_statusbar()

        self.plotpanel = PlotPanel(self, trace_color_callback=self.onTraceColor)
        self.plotpanel.BuildPanel()
        self.plotpanel.messenger = self.write_message

        self.build_pvpanel()
        self.build_btnpanel()
        self.build_menus()
        self.SetBackgroundColour(wx.Colour(*BGCOL))

        mainsizer = wx.BoxSizer(wx.VERTICAL)

        p1 = wx.Panel(self)
        p1.SetBackgroundColour(wx.Colour(*BGCOL))
        s1 = wx.BoxSizer(wx.HORIZONTAL)
        n = LabelEntry(p1, '', labeltext=' Add PV: ',
                       size=300, action = self.onPVname)
        x = SimpleText(p1,'   ',  minsize=(75, -1), style=LSTY|wx.EXPAND)
        s1.Add(n.label,  0,  wx.ALIGN_LEFT|wx.ALIGN_CENTER, 10)
        s1.Add(n,        0,  wx.ALIGN_LEFT|wx.ALIGN_CENTER, 10)
        s1.Add(x,        1,  wx.ALIGN_LEFT|wx.ALIGN_CENTER, 10)
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

    def build_statusbar(self):
        sbar = self.CreateStatusBar(2,wx.CAPTION|wx.THICK_FRAME)
        sfont = sbar.GetFont()
        sfont.SetWeight(wx.BOLD)
        sfont.SetPointSize(10)
        sbar.SetFont(sfont)
        self.SetStatusWidths([-5,-2])
        self.SetStatusText('',0)

    def build_pvpanel(self):
        panel = self.pvpanel = wx.Panel(self)
        panel.SetBackgroundColour(wx.Colour(*BGCOL))
        sizer = self.pvsizer = wx.GridBagSizer(5, 5)

        name = SimpleText(panel, ' PV:  ',       minsize=(75, -1), style=LSTY|wx.EXPAND)
        colr = SimpleText(panel, ' Color ',      minsize=(50, -1), style=LSTY)
        logs = SimpleText(panel, ' Log Scale?',  minsize=(85, -1), style=LSTY)

        sizer.Add(name, (0, 0), (1, 1), LSTY|wx.EXPAND, 2)
        sizer.Add(colr, (0, 1), (1, 1), LSTY, 1)
        sizer.Add(logs, (0, 2), (1, 1), LSTY, 1)

        self.npv_rows = 0
        for i in range(3):
            self.AddPV_row(hide_log = i>1)

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

        time_label = SimpleText(panel, '    Time Range: ',  minsize=(85, -1), style=LSTY)
        self.time_choice = MyChoice(panel, choices=('seconds', 'minutes', 'hours'))
        self.time_choice.SetStringSelection(self.timelabel)
        self.time_choice.Bind(wx.EVT_CHOICE,   self.onTimeChoice)

        self.time_ctrl  = FloatCtrl(panel, value=-self.tmin, precision=2, size=(90, -1),
                                    action=self.onTimeVal)

        btnsizer.Add(self.pause_btn,   0, wx.ALIGN_LEFT|wx.ALIGN_CENTER, 2)
        btnsizer.Add(self.resume_btn,  0, wx.ALIGN_LEFT|wx.ALIGN_CENTER, 2)
        btnsizer.Add(time_label,       1, wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_CENTER, 2)
        btnsizer.Add(self.time_ctrl,   0, wx.ALIGN_LEFT|wx.ALIGN_CENTER, 2)
        btnsizer.Add(self.time_choice, 0, wx.ALIGN_LEFT|wx.ALIGN_CENTER, 2)

        panel.SetAutoLayout(True)
        panel.SetSizer(btnsizer)
        btnsizer.Fit(panel)

    def build_menus(self):
        mids = self.menuIDs = Menu_IDs()
        mbar = wx.MenuBar()

        mfile = wx.Menu()
        mfile.Append(mids.SAVE_DAT, "&Save Data\tCtrl+S",
                     "Save PNG Image of Plot")
        mfile.Append(mids.SAVE_IMG, "Save Plot Image\t",
                     "Save PNG Image of Plot")
        mfile.Append(mids.CLIPB, "&Copy Image to Clipboard\tCtrl+C",
                     "Copy Plot Image to Clipboard")
        mfile.AppendSeparator()
        mfile.Append(mids.PSETUP, 'Page Setup...', 'Printer Setup')
        mfile.Append(mids.PREVIEW, 'Print Preview...', 'Print Preview')
        mfile.Append(mids.PRINT, "&Print\tCtrl+P", "Print Plot")
        mfile.AppendSeparator()
        mfile.Append(mids.EXIT, "E&xit\tCtrl+Q", "Exit the 2D Plot Window")

        mopt = wx.Menu()
        mopt.Append(mids.CONFIG, "Configure Plot\tCtrl+K",
                 "Configure Plot styles, colors, labels, etc")
        mopt.AppendSeparator()
        mopt.Append(mids.UNZOOM, "Zoom Out\tCtrl+Z",
                 "Zoom out to full data range")

        mhelp = wx.Menu()
        mhelp.Append(mids.HELP, "Quick Reference",  "Quick Reference for MPlot")
        mhelp.Append(mids.ABOUT, "About", "About MPlot")

        mbar.Append(mfile, "File")
        mbar.Append(mopt, "Options")
        mbar.Append(mhelp, "&Help")

        self.SetMenuBar(mbar)
        self.Bind(wx.EVT_MENU, self.onSaveData, id=mids.SAVE_DAT)
        self.Bind(wx.EVT_MENU, self.onHelp,     id=mids.HELP)
        self.Bind(wx.EVT_MENU, self.onAbout,    id=mids.ABOUT)
        self.Bind(wx.EVT_MENU, self.onExit,     id=mids.EXIT)
        self.Bind(wx.EVT_CLOSE,self.onExit)

        pp = self.plotpanel
        self.Bind(wx.EVT_MENU, pp.configure,    id=mids.CONFIG)
        self.Bind(wx.EVT_MENU, pp.unzoom_all,   id=mids.UNZOOM)
        self.Bind(wx.EVT_MENU, pp.save_figure,  id=mids.SAVE_IMG)
        self.Bind(wx.EVT_MENU, pp.Print,        id=mids.PRINT)
        self.Bind(wx.EVT_MENU, pp.PrintSetup,   id=mids.PSETUP)
        self.Bind(wx.EVT_MENU, pp.PrintPreview, id=mids.PREVIEW)
        self.Bind(wx.EVT_MENU, pp.canvas.Copy_to_Clipboard,id=mids.CLIPB)

    def AddPV_row(self, i=None, hide_log=False):
        if i is None:
            i = self.npv_rows = self.npv_rows + 1
        panel = self.pvpanel
        sizer = self.pvsizer
        pvchoice = MyChoice(panel, choices=self.pvlist, size=(200, -1))
        pvchoice.SetSelection(0)
        logs = MyChoice(panel)
        logs.SetSelection(0)
        if hide_log:
            logs.Disable()
        colval = (0, 0, 0)
        if i < len(self.default_colors):
            colval = self.default_colors[i]
        colr = csel.ColourSelect(panel, -1, '', colval)
        self.colorsels.append(colr)

        sizer.Add(pvchoice, (i, 0), (1, 1), LSTY, 3)
        sizer.Add(colr,     (i, 1), (1, 1), CSTY, 3)
        sizer.Add(logs,     (i, 2), (1, 1), CSTY, 3)
        pvchoice.Bind(wx.EVT_CHOICE,     Closure(self.onPVchoice, row=i))
        colr.Bind(csel.EVT_COLOURSELECT, Closure(self.onPVcolor, row=i))
        logs.Bind(wx.EVT_CHOICE,         self.onPVwid)
        self.pvchoices.append(pvchoice)
        self.pvwids.append((logs, colr))

    def onTraceColor(self, trace, color, **kws):
        irow = self.get_current_traces()[trace][0] - 1
        self.colorsels[irow].SetColour(color)
        
    def onPVshow(self, event=None, row=0, **kws):
        if not event.IsChecked():
            trace = self.plotpanel.conf.get_mpl_line(row)
            trace.set_data([], [])
            self.plotpanel.canvas.draw()
        self.needs_refresh = True

    def onPVname(self, event=None, **kws):
        try:
            name = event.GetString()
        except AttributeError:
            return
        self.addPV(name)

    @epics.wx.EpicsFunction
    def addPV(self, name):
        if name is not None and name not in self.pvlist:
            self.pvdata[name] = []
            pv = epics.PV(str(name), callback=self.onPVChange)
            self.pvlist.append(name)
            pv.get()
            self.pvdata[name].append((time.time(), pv.get()))
            i_new = len(self.pvdata)
            new_shown = False
            for ic, choice in enumerate(self.pvchoices):
                if choice is None:
                    continue
                cur = choice.GetSelection()
                choice.Clear()
                choice.SetItems(self.pvlist)
                choice.SetSelection(cur)
                if cur == 0 and not new_shown:
                    choice.SetSelection(i_new)
                    new_shown = True
            self.needs_refresh = True

    @epics.wx.DelayedEpicsCallback
    def onPVChange(self, pvname=None, value=None, timestamp=None, **kw):
        if timestamp is None: timestamp = time.time()
        self.pvdata[pvname].append((timestamp,value))
        
    def onPVchoice(self, event=None, row=None, **kws):
        self.needs_refresh = True
        for i in range(len(self.pvlist)+1):
            try:
                trace = self.plotpanel.conf.get_mpl_line(row-1)
                trace.set_data([], [])
            except:
                pass
        self.plotpanel.canvas.draw()
                

    def onPVcolor(self, event=None, row=None, **kws):
        self.plotpanel.conf.set_trace_color(hexcolor(event.GetValue()), trace=row-1)
        self.needs_refresh = True

    def onPVwid(self, event=None, row=None, **kws):
        self.needs_refresh = True


    def onTimeVal(self, event=None, value=None, **kws):
        self.tmin = -value
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

    def write_message(self,s,panel=0):
        """write a message to the Status Bar"""
        self.SetStatusText(s, panel)

    def onSaveData(self, event=None):
        dlg = wx.FileDialog(self, message='Save Data to File...',
                            defaultDir = os.getcwd(),
                            defaultFile='PVStripChart.dat',
                            style=wx.SAVE|wx.CHANGE_DIR)
        if dlg.ShowModal() == wx.ID_OK:
            path = dlg.GetPath()
            self.SaveDataFiles(path)
            self.write_message('Saved data to %s' % path)
        dlg.Destroy()

    def SaveDataFiles(self, path):
        print 'save data to ', path
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
                if s not in VALID_FILECHARS:
                    s = '_'
                fname.append(s)
            fname = os.path.join("%s_%s.%s" % (basename, ''.join(fname), ext))
            
            buff =["# Epics PV Strip Chart Data for PV: %s " % pvname]
            buff.append("# Current Time  = %s " % time.ctime(tnow))
            buff.append("# Earliest Time = %s " % time.ctime(tmin))
            buff.append("#------------------------------")
            buff.append("#  Timestamp         Value          Time-Current_Time(s)")
            for tx, yval in data: 
                buff.append("  %.3f %16g     %.3f"  % (tx, yval, tx-tnow))

            fout = open(fname, 'w')
            fout.write("\n".join(buff))
            fout.close()
            #dat = tnow, func(tnow)
                
    def onAbout(self, event=None):
        dlg = wx.MessageDialog(self, self.about_msg, "About Epics PV Strip Chart",
                               wx.OK | wx.ICON_INFORMATION)
        dlg.ShowModal()
        dlg.Destroy()

    def onHelp(self, event=None):
        dlg = wx.MessageDialog(self, self.help_msg, "Epics PV Strip Chart Help",
                               wx.OK | wx.ICON_INFORMATION)
        dlg.ShowModal()
        dlg.Destroy()

    def onExit(self, event=None):

        try:
            self.plotpanel.win_config.Close(True)
            self.plotpanel.win_config.Destroy()
        except:
            pass

        self.Destroy()


    def Get_Data(self, tnow):
        # test only -- would replace with getting data from PVs
        for name, func in self.test_sources.items():
            if name in self.pvdata:
                self.pvdata[name].append((tnow, func(tnow)))

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
                    traces.append((irow, name, logs, color))

        return traces
        
    def onUpdatePlot(self, event=None):
        tnow = time.time()

        # self.Get_Data(tnow)
        if self.paused and not self.needs_refresh:
            return

        traces = self.get_current_traces()
        
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
        for irow, pname, uselog, color in traces:
            if pname in self.pvdata:
                itrace += 1
                side = 'left'
                if itrace==1:
                    side = 'right'
                data = self.pvdata[pname][:]
                if len(data)  < 1:
                    update_failed = True
                    continue
                tdat = timescale * (numpy.array([i[0] for i in data]) - tnow)
                mask = numpy.where(tdat > self.tmin)

                if len(mask[0]) < 2 or ( (abs(min(tdat)) / abs(1 -self.tmin)) > 0.1):
                    data.append((time.time(), data[0][-1]))
                    tdat = timescale * (numpy.array([i[0] for i in data]) - tnow)
                    mask = numpy.where(tdat > self.tmin)
                    

                i0 = mask[0][0]
                if i0 > 1: i0 = i0 -1
                i1 = mask[0][-1] + 1
                tdat = timescale * (numpy.array([i[0] for i in data[i0:i1]]) - tnow)
                ydat = numpy.array([i[1] for i in data[i0:i1]])

                if len(ydat)  < 2:
                    update_failed = True
                    continue

                if itrace ==  0:
                    span1 = (max(ydat)-min(ydat), min(ydat))
                    if span1*max(ydat) < 1.e-4:
                        span1 = (1.e-4, min(ydat))
                elif itrace > 1:
                    yr = abs(max(ydat)-min(ydat))
                    if yr > 1.e-9:
                        ydat = span1[1] + (ydat - min(ydat))*span1[0]/yr


                if not self.needs_refresh:
                    try:
                        self.plotpanel.update_line(itrace, tdat, ydat)
                    except:
                        update_failed = True
                else:
                    plot = self.plotpanel.oplot
                    if not hasplot:
                        plot = self.plotpanel.plot
                        hasplot = True
                    if itrace==1 and not y2labelset:
                        self.plotpanel.set_y2label(pname)
                        y2labelset = True
                    elif not ylabelset:
                        self.plotpanel.set_ylabel(pname)
                        ylabelset = True
                    plot(tdat, ydat, drawstyle='steps-post', side=side,
                         ylog_scale=uselog, color=color,
                         xlabel=xlabel, label=pname)
                if itrace < 2:
                    self.plotpanel.set_xylims(((self.tmin, 0), (min(ydat), max(ydat))),
                                              side=side, autoscale=False)
                self.plotpanel.set_title(time.strftime("%Y-%b-%d %H:%M:%S", time.localtime()))
        self.plotpanel.canvas.draw()
        self.needs_refresh = update_failed
        return

if __name__ == '__main__':
    app = wx.PySimpleApp()
    f = StripChart()
    f.Show(True)
    app.MainLoop()

