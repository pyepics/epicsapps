#!/usr/bin/python
import sys
import time
import numpy
import wx

import epics
import epics.wx
from  mplot.plotpanel import PlotPanel

def source1(t):
    t = t % 100
    return 2.0*numpy.sin(3.0*t) + numpy.random.normal(scale=0.14) + (t+15.0)/63.0

def source2(t):
    t = t % 200
    return t/25. + numpy.random.normal(scale=0.4)

def source3(t):
    t = t % 50
    return t + numpy.random.normal(scale=10.0)

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
    def __init__(self, parent=None):

        self.pvdata = {'source1':[], 'source2':[], 'source3':[]}
        self.time0 = time.time()
        self.nplot = -1
        self.paused = False

        self.create_frame(parent)
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.OnUpdatePlot, self.timer)
        self.timer.Start(50)

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
        self.BuildTopPanel()

        self.plotpanel = PlotPanel(self)
        self.plotpanel.BuildPanel()
        self.plotpanel.messenger = self.write_message
        mainsizer.Add(self.toppanel,  0)
        mainsizer.Add(self.plotpanel, 1, wx.EXPAND)

        self.BindMenuToPanel()
        self.SetAutoLayout(True)
        self.SetSizer(mainsizer)
        self.Fit()

    def BuildTopPanel(self):
        panel = self.toppanel = wx.Panel(self)


        sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.pause_btn = wx.Button(panel, label='Pause', size=(105, 30))
        self.resume_btn = wx.Button(panel, label='Resume', size=(105, 30))
        self.resume_btn.Disable()

        self.pause_btn.Bind(wx.EVT_BUTTON, self.onPause)
        self.resume_btn.Bind(wx.EVT_BUTTON, self.onPause)

        sizer.Add(self.pause_btn, 1, wx.ALIGN_LEFT, wx.ALIGN_CENTER, 2)
        sizer.Add(self.resume_btn, 1, wx.ALIGN_LEFT, wx.ALIGN_CENTER, 2)

        panel.SetAutoLayout(True)
        panel.SetSizer(sizer)
        sizer.Fit(panel)

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

        try:
            self.plotpanel.set_xylims([tmin, 0, min(y1dat), max(y1dat)],
                                      autoscale=False)
            self.plotpanel.set_xylims([tmin, 0, min(y2dat), max(y2dat)],
                                      side='right', autoscale=False)
        except:
            pass

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

