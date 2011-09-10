#!/usr/bin/python
##
## MPlot PlotFrame: a wx.Frame for 2D line plotting, using matplotlib
##

import os
import time
import wx
import matplotlib

from plotpanel import PlotPanel

class PlotFrame(wx.Frame):
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
    about_msg =  """MPlot  version 0.9
Matt Newville <newville@cars.uchicago.edu>"""

    menulist = ('EXIT', 'SAVE', 'CONFIG', 'UNZOOM', 'HELP',
                'ABOUT', 'PRINT', 'PSETUP', 'PREVIEW', 'CLIPB',
                'SELECT_COLOR', 'SELECT_SMOOTH')

    def __init__(self, parent=None, size=(700,450), exit_callback=None, **kwds):
        self.exit_callback = exit_callback
        self.title  = '2D Plot Frame'
        self.parent = parent
        class Menu_IDs:
            pass
        self.menuIDs = Menu_IDs()
        for a in self.menulist:
            setattr(self.menuIDs, a, wx.NewId())

        self.top_menus = {'File':None,'Help':None}

        self.plotpanel = PlotPanel(self, parent)
        self.Build_DefaultUserMenus()
        self.BuildFrame(size=size, **kwds)

        for attr in ('plot', 'oplot', 'update_line',
                     'set_xylims', 'get_xylims', 'clear', 'unzoom',
                     'unzoom_all', 'set_title', 'set_xlabel', 'set_ylabel',
                     'save_figure', 'configure'):
            setattr(self, attr, getattr(self.plotpanel, attr))

    def write_message(self, s, panel=0):
        """write a message to the Status Bar"""
        self.SetStatusText(s, panel)

    def get_cursor(self):
        """ return cursor position"""
        return self.panel.cursor_xy

    ####
    ## create GUI
    ####
    def BuildFrame(self, size=(700,450), **kwds):
        kwds['style'] = wx.DEFAULT_FRAME_STYLE
        kwds['size']  = size
        wx.Frame.__init__(self, self.parent, -1, self.title, **kwds)

        sbar = self.CreateStatusBar(2,wx.CAPTION|wx.THICK_FRAME)
        sfont = sbar.GetFont()
        sfont.SetWeight(wx.BOLD)
        sfont.SetPointSize(10)
        sbar.SetFont(sfont)

        self.SetStatusWidths([-3,-1])
        self.SetStatusText('',0)

        sizer = wx.BoxSizer(wx.VERTICAL)
        self.BuildMenu()

        ppanel = self.plotpanel
        ppanel.BuildPanel()
        ppanel.messenger = self.write_message
        sizer.Add(ppanel, 1, wx.EXPAND)
        mids = self.menuIDs
        self.Bind(wx.EVT_MENU, ppanel.configure,    id=mids.CONFIG)
        self.Bind(wx.EVT_MENU, ppanel.unzoom_all,   id=mids.UNZOOM)

        self.Bind(wx.EVT_MENU, ppanel.save_figure,  id=mids.SAVE)
        self.Bind(wx.EVT_MENU, ppanel.Print,        id=mids.PRINT)
        self.Bind(wx.EVT_MENU, ppanel.PrintSetup,   id=mids.PSETUP)
        self.Bind(wx.EVT_MENU, ppanel.PrintPreview, id=mids.PREVIEW)
        self.Bind(wx.EVT_MENU, ppanel.canvas.Copy_to_Clipboard, id=mids.CLIPB)

        self.SetAutoLayout(True)
        self.SetSizer(sizer)
        self.Fit()

    def Build_DefaultUserMenus(self):
        mids = self.menuIDs
        m = wx.Menu()
        m.Append(mids.CONFIG, "Configure Plot\tCtrl+K",
                 "Configure Plot styles, colors, labels, etc")
        m.AppendSeparator()
        m.Append(mids.UNZOOM, "Zoom Out\tCtrl+Z",
                 "Zoom out to full data range")
        self.user_menus  = [('&Options',m)]

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

        mbar.Append(self.top_menus['File'], "File")
        for m in self.user_menus:
            title,menu = m
            mbar.Append(menu, title)
        mbar.Append(self.top_menus['Help'], "&Help")

        self.SetMenuBar(mbar)
        self.Bind(wx.EVT_MENU, self.onHelp,    id=mids.HELP)
        self.Bind(wx.EVT_MENU, self.onAbout,   id=mids.ABOUT)
        self.Bind(wx.EVT_MENU, self.onExit ,   id=mids.EXIT)
        self.Bind(wx.EVT_CLOSE,self.onExit)

    def onAbout(self, event=None):
        dlg = wx.MessageDialog(self, self.about_msg, "About Plot Window",
                               wx.OK | wx.ICON_INFORMATION)
        dlg.ShowModal()
        dlg.Destroy()

    def onHelp(self, event=None):
        dlg = wx.MessageDialog(self, self.help_msg, "Plot Quick Reference",
                               wx.OK | wx.ICON_INFORMATION)
        dlg.ShowModal()
        dlg.Destroy()

    def onExit(self, event=None):
        try:
            if hasattr(self.exit_callback, '__call__'):
                self.exit_callback()
        except:
            pass
        try:
            self.plotpanel.win_config.Close(True)
            self.plotpanel.win_config.Destroy()
        except:
            pass

        try:
            self.Destroy()
        except:
            pass

