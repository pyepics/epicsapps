#!/usr/bin/python
import sys
import time
import numpy
import wx

import epics
import epics.wx
from  mplot.plotpanel import PlotPanel

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

class EpicsStripChart(wx.Frame):
    def __init__(self, parent=None, pvname=None):
        self.pvs = []
        self.pvdata = {}
        if pvname is not None:
            self.pv = epics.PV(pvname)
            self.pv.add_callback(self.onPVChange)
            self.pvdata[pvname] = []
        self.time0 = time.time()
        self.nplot = 0
        self.create_frame(parent)

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
        
        self.plotpanel = PlotPanel(self)
        self.plotpanel.BuildPanel()
        self.plotpanel.messenger = self.write_message
        mainsizer.Add(self.plotpanel, 1, wx.EXPAND)
        self.BindMenuToPanel()
            
        self.SetAutoLayout(True)
        self.SetSizer(mainsizer)
        self.Fit()

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
        wx.CallAfter(self.UpdatePlot)

    def UpdatePlot(self):
        tnow = time.time()

        self.tmin = -120
        for pvname, data in self.pvdata.items():
            if  self.nplot == len(data):
                return
            if self.nplot % 100 == 0:
                print self.nplot, time.time()-self.time0
            self.nplot = len(data)
            tdat = numpy.array([i[0] for i in data]) - tnow

            mask = numpy.where(tdat>self.tmin)
            tdat = tdat[mask]
            ydat = numpy.array([i[1] for i in data])[mask]

            tmin = self.tmin
            if mask[0][0] == 0 and (min(tdat) > self.tmin/2.0):
                tmin = self.tmin/2.0
                    
            try:
                self.plotpanel.set_xylims([tmin, 0, min(ydat),max(ydat)],
                                      autoscale=False)
            except:
                pass

            try:
                self.plotpanel.update_line(0, tdat, ydat)
                self.plotpanel.canvas.draw()
            except:
                self.plotpanel.plot(tdat, ydat, 
                                    drawstyle='steps-post',
                                    xlabel='Elapsed Time (s)',
                                    ylabel=pvname)
                
            
        self.plotpanel.canvas.draw_idle()

#                       ydat[mask].max())
#             print len(tdat), xylims ,  min(tdat), max(tdat)
#             n = len(ydat)

            #elif n > 3:
            #    self.plotframe.update_line(tdat, ydat)
            #s = " %i points in %8.4f s" % (n,etime)
            #self.plotframe.write_message(s)
            # self.plotframe.panel.set_xylims(xylims)


if __name__ == '__main__':
    app = wx.PySimpleApp()
    #f = EpicsStripChart(pvname='13IDA:DMM1Ch2_calc.VAL')
    f = EpicsStripChart(pvname='Py:ao3')
    f.Show(True)
    app.MainLoop()

