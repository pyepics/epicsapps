#!/usr/bin/python
import sys
import time
import numpy
import wx
import wx.lib.colourselect  as csel

import epics
import epics.wx
from epics.wx.utils import  SimpleText, Closure, FloatCtrl

from  mplot.plotpanel import PlotPanel

def source1(t):
    t = t % 100
    return 0.4*numpy.sin(.6*t) + numpy.random.normal(scale=0.27) + (t)/23.0

def source2(t):
    t = t % 30
    return ((t/4.) + numpy.random.normal(scale=0.5))/ 10.0

def source3(t):
    t = t % 50
    return t + numpy.random.normal(scale=10.0)

STY  = wx.GROW|wx.ALL|wx.ALIGN_CENTER_VERTICAL
LSTY = wx.ALIGN_LEFT|wx.EXPAND|wx.ALL|wx.ALIGN_CENTER_VERTICAL
CSTY = wx.ALIGN_CENTER|wx.ALIGN_CENTER_VERTICAL

class Choice2(wx.Choice):
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
            self.SetSelection(0)
        elif choice in self.choices:
            self.SetSelection(self.choices.index(choice))

class Menu_IDs:
    def __init__(self):
        self.EXIT   = wx.NewId()
        self.SAVE   = wx.NewId()
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

    def __init__(self, parent=None):

        self.pvdata = {'source1':[], 'source2':[], 'source3':[]}
        self.time0 = time.time()
        self.nplot = -1
        self.paused = False

        self.create_frame(parent)
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnUpdatePlot, self.timer)
        self.timer.Start(150)

    def create_frame(self, parent, size=(700, 450), **kwds):
        self.parent = parent

        kwds['style'] = wx.DEFAULT_FRAME_STYLE
        kwds['size']  = size
        wx.Frame.__init__(self, self.parent, -1, 'Epics PV Strip Chart', **kwds)

        self.menuIDs = Menu_IDs()
        self.top_menus = {'File':None,'Help':None}

        sbar = self.CreateStatusBar(2,wx.CAPTION|wx.THICK_FRAME)
        sfont = sbar.GetFont()
        sfont.SetWeight(wx.BOLD)
        sfont.SetPointSize(10)
        sbar.SetFont(sfont)

        self.SetStatusWidths([-3,-1])
        self.SetStatusText('',0)

        mainsizer = wx.BoxSizer(wx.VERTICAL)
        self.BuildMenu()
        self.BuildTopPanels()

        self.plotpanel = PlotPanel(self)
        self.plotpanel.BuildPanel()
        self.plotpanel.messenger = self.write_message
        mainsizer.Add(self.pvpanel,   0, wx.EXPAND)
        mainsizer.Add(wx.StaticLine(self, size=(250, -1),
                                    style=wx.LI_HORIZONTAL),
                                      0, wx.EXPAND)
        mainsizer.Add(self.btnpanel,  0, wx.EXPAND)
        mainsizer.Add(self.plotpanel, 1, wx.EXPAND)

        self.BindMenuToPanel()
        self.SetAutoLayout(True)
        self.SetSizer(mainsizer)
        self.Fit()

    def AddPV_row(self, i=None):
        if i is None:
            i = self.npv_rows = self.npv_rows + 1
        panel = self.pvpanel
        sizer = self.pvsizer
        name = wx.TextCtrl(panel, value='', size=(230, -1))
        show = wx.CheckBox(panel)
        logs = Choice2(panel)
        axes = Choice2(panel, choices=('Left', 'Right'))
        show.SetValue(False)
        logs.SetSelection(0)
        axes.SetSelection(0)
        if i == 2:
            axes.SetSelection(1)
        colval = (0, 0, 0)
        if i < len(self.default_colors):
            colval = self.default_colors[i]
        colr = csel.ColourSelect(panel, -1, '', colval)

        sizer.Add(name,  (i, 0), (1, 1), LSTY, 3)
        sizer.Add(show,  (i, 1), (1, 1), CSTY, 3)
        sizer.Add(colr,  (i, 2), (1, 1), CSTY, 3)
        sizer.Add(logs,  (i, 3), (1, 1), CSTY, 3)
        sizer.Add(axes,  (i, 4), (1, 1), LSTY, 3)
        name.Bind(wx.EVT_TEXT_ENTER, Closure(self.onPVname, row=i))
        show.Bind(wx.EVT_CHECKBOX,   Closure(self.onPVshow, row=i))
        logs.Bind(wx.EVT_CHOICE,     Closure(self.onPVlogs, row=i))
        axes.Bind(wx.EVT_CHOICE,     Closure(self.onPVaxes, row=i))
        colr.Bind(csel.EVT_COLOURSELECT,  Closure(self.onPVcolor, row=i))

    def onPVname(self, event=None, row=None, **kws):
        print 'onPVname ', row, event

    def onPVcolor(self, event=None, row=None, **kws):
        print 'onPVcolor ', row, event

    def onPVshow(self, event=None, row=None, **kws):
        print 'onPVshow ', row, event
    def onPVlogs(self, event=None, row=None, **kws):
        print 'onPVlogs ', row, event

    def onPVaxes(self, event=None, row=None, **kws):
        print 'onPVaxes ', row, event

    def onTimeVal(self, event=None, value=None, **kws):
        print 'onTimeVal ', kws

    def onTimeChoice(self, event=None, **kws):
        print 'onTimeChoice ', event

    def BuildTopPanels(self):
        panel = self.pvpanel = wx.Panel(self, )
        sizer = self.pvsizer = wx.GridBagSizer(5, 5)
        panel.SetBackgroundColour(wx.Colour(240,240,230))

        self.wid_pvnames = []

        name = SimpleText(panel, ' PV Name   ',  minsize=(85, -1), style=LSTY)
        show = SimpleText(panel, ' Show? ',      minsize=(50, -1), style=LSTY)
        colr = SimpleText(panel, ' Color ',      minsize=(50, -1), style=LSTY)
        logs = SimpleText(panel, ' Log Scale?',  minsize=(85, -1), style=LSTY)
        axes = SimpleText(panel, ' Axes      ',  minsize=(85, -1), style=LSTY)

        sizer.Add(name, (0, 0), (1, 1), LSTY, 2)
        sizer.Add(show, (0, 1), (1, 1), LSTY, 2)
        sizer.Add(colr, (0, 2), (1, 1), LSTY, 2)
        sizer.Add(logs, (0, 3), (1, 1), LSTY, 2)
        sizer.Add(axes, (0, 4), (1, 1), LSTY, 2)

        self.npv_rows = 0
        for i in range(3):
            self.AddPV_row()

        panel.SetAutoLayout(True)
        panel.SetSizer(sizer)
        sizer.Fit(panel)
        #------
        panel = self.btnpanel = wx.Panel(self, )
        panel.SetBackgroundColour(wx.Colour(240,240,230))

        btnsizer = wx.BoxSizer(wx.HORIZONTAL)
        self.pause_btn  = wx.Button(panel, label='Pause', size=(90, 30))
        self.resume_btn = wx.Button(panel, label='Resume', size=(90, 30))
        self.resume_btn.Disable()

        self.pause_btn.Bind(wx.EVT_BUTTON, self.onPause)
        self.resume_btn.Bind(wx.EVT_BUTTON, self.onPause)

        time_label = SimpleText(panel, '    Time Range: ',  minsize=(85, -1), style=LSTY)
        self.time_ctrl  = FloatCtrl(panel, value=20, precision=1, size=(90, -1),
                                    action=self.onTimeVal)
        self.time_choice = Choice2(panel, choices=('seconds', 'minutes', 'hours'))
        self.time_choice.SetSelection(0)
        self.time_choice.Bind(wx.EVT_CHOICE,   self.onTimeChoice)

        btnsizer.Add(self.pause_btn,   1, wx.ALIGN_LEFT|wx.ALIGN_CENTER, 2)
        btnsizer.Add(self.resume_btn,  1, wx.ALIGN_LEFT|wx.ALIGN_CENTER, 2)
        btnsizer.Add(time_label,       1, wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_CENTER, 2)
        btnsizer.Add(self.time_ctrl,   1, wx.ALIGN_LEFT|wx.ALIGN_CENTER, 2)
        btnsizer.Add(self.time_choice, 1, wx.ALIGN_LEFT|wx.ALIGN_CENTER, 2)

        panel.SetAutoLayout(True)
        panel.SetSizer(btnsizer)
        btnsizer.Fit(panel)

    def onPause(self, event=None):
        if self.paused:
            self.pause_btn.Enable()
            self.resume_btn.Disable()
        else:
            self.pause_btn.Disable()
            self.resume_btn.Enable()
        self.paused = not self.paused

    def BuildMenu(self):
        mids = self.menuIDs
        m0 = wx.Menu()

        m0.Append(mids.SAVE, "&Save\tCtrl+S",   "Save PNG Image of Plot")
        m0.Append(mids.CLIPB, "&Copy\tCtrl+C",  "Copy Plot Image to Clipboard")
        m0.AppendSeparator()
        m0.Append(mids.PSETUP, 'Page Setup...', 'Printer Setup')
        m0.Append(mids.PREVIEW, 'Print Preview...', 'Print Preview')
        m0.Append(mids.PRINT, "&Print\tCtrl+P", "Print Plot")
        m0.AppendSeparator()
        m0.Append(mids.EXIT, "E&xit\tCtrl+Q", "Exit the 2D Plot Window")

        self.top_menus['File'] = m0

        mhelp = wx.Menu()
        mhelp.Append(mids.HELP, "Quick Reference",  "Quick Reference for MPlot")
        mhelp.Append(mids.ABOUT, "About", "About MPlot")
        self.top_menus['Help'] = mhelp

        mbar = wx.MenuBar()
        m = wx.Menu()
        m.Append(mids.CONFIG, "Configure Plot\tCtrl+K",
                 "Configure Plot styles, colors, labels, etc")
        m.AppendSeparator()
        m.Append(mids.UNZOOM, "Zoom Out\tCtrl+Z",
                 "Zoom out to full data range")
        self.user_menus  = [('&Options',m)]


        mbar.Append(self.top_menus['File'], "File")
        for m in self.user_menus:
            title,menu = m
            mbar.Append(menu, title)
        mbar.Append(self.top_menus['Help'], "&Help")


        self.SetMenuBar(mbar)
        self.Bind(wx.EVT_MENU, self.onHelp,            id=mids.HELP)
        self.Bind(wx.EVT_MENU, self.onAbout,           id=mids.ABOUT)
        self.Bind(wx.EVT_MENU, self.onExit ,           id=mids.EXIT)
        self.Bind(wx.EVT_CLOSE,self.onExit)

    def BindMenuToPanel(self, panel=None):
        if panel is None: panel = self.plotpanel
        if panel is not None:
            p = panel
            mids = self.menuIDs
            self.Bind(wx.EVT_MENU, panel.configure,    id=mids.CONFIG)
            self.Bind(wx.EVT_MENU, panel.unzoom_all,   id=mids.UNZOOM)

            self.Bind(wx.EVT_MENU, panel.save_figure,  id=mids.SAVE)
            self.Bind(wx.EVT_MENU, panel.Print,        id=mids.PRINT)
            self.Bind(wx.EVT_MENU, panel.PrintSetup,   id=mids.PSETUP)
            self.Bind(wx.EVT_MENU, panel.PrintPreview, id=mids.PREVIEW)
            self.Bind(wx.EVT_MENU, panel.canvas.Copy_to_Clipboard,
                      id=mids.CLIPB)

    def write_message(self,s,panel=0):
        """write a message to the Status Bar"""
        self.SetStatusText(s, panel)

    def onAbout(self, event=None):
        dlg = wx.MessageDialog(self, self.about_msg, "About MPlot",
                               wx.OK | wx.ICON_INFORMATION)
        dlg.ShowModal()
        dlg.Destroy()

    def onHelp(self, event=None):
        dlg = wx.MessageDialog(self, self.help_msg, "MPlot Quick Reference",
                               wx.OK | wx.ICON_INFORMATION)
        dlg.ShowModal()
        dlg.Destroy()

    def onExit(self, event=None):
        try:
            if callable(self.exit_callback):  self.exit_callback()
        except:
            pass
        try:
            if self.panel is not None: self.panel.win_config.Close(True)
            if self.panel is not None: self.panel.win_config.Destroy()
        except:
            pass

        try:
            self.Destroy()
        except:
            pass

    @epics.wx.DelayedEpicsCallback
    def onPVChange(self, pvname=None, value=None,**kw):
        self.pvdata[pvname].append((time.time(),value))

    def OnUpdatePlot(self, event=None):
        tnow = time.time()
        n = self.nplot = self.nplot + 1

        self.tmin = -20
        self.pvdata['source1'].append((tnow, source1(tnow)))
        self.pvdata['source2'].append((tnow, source2(tnow)))
        self.pvdata['source3'].append((tnow, source3(tnow)))


        data1 = self.pvdata['source1']
        data2 = self.pvdata['source2']
        if len(data1) < 2 or self.paused: return

        t1dat = numpy.array([i[0] for i in data1]) - tnow
        mask1 = numpy.where(t1dat>self.tmin)
        t1dat = t1dat[mask1]
        y1dat = numpy.array([i[1] for i in data1])[mask1]

        t2dat = numpy.array([i[0] for i in data2]) - tnow
        mask2 = numpy.where(t2dat>self.tmin)
        t2dat = t2dat[mask2]
        y2dat = numpy.array([i[1] for i in data2])[mask2]

        tmin = self.tmin
        if mask1[0][0] == 0 and (min(t1dat) > self.tmin/2.0):
            tmin = self.tmin/2.0


        self.plotpanel.set_xylims(((tmin, 0), (min(y1dat), max(y1dat))),
                                  autoscale=False)
        self.plotpanel.set_xylims(((tmin, 0), (min(y2dat), max(y2dat))),
                                  side='right', autoscale=False)

        try:
            self.plotpanel.update_line(0, t1dat, y1dat)
            self.plotpanel.update_line(1, t2dat, y2dat)
            self.plotpanel.canvas.draw()

        except:
            self.plotpanel.plot(t1dat, y1dat,
                                drawstyle='steps-post',
                                xlabel='Elapsed Time (s)',
                                ylabel='source1')
            self.plotpanel.set_y2label('source2')

            self.plotpanel.oplot(t2dat, y2dat, side='right')

        #self.plotpanel.canvas.draw_idle()
        # event.Skip()

if __name__ == '__main__':
    app = wx.PySimpleApp()
    f = StripChart()
    f.Show(True)
    app.MainLoop()

