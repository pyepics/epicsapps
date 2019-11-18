#!/usr/bin/python
"""
Epics MCA Display application
"""
import os
import time
import numpy as np

import wx
import wx.lib.colourselect  as csel

from epics import PV
from epics.wx import EpicsFunction, DelayedEpicsCallback
from epics.wx.utils import  SimpleText, Closure, FloatCtrl

from wxmplot.plotpanel import PlotPanel
from wxmplot.colors import hexcolor
from wxmplot.utils import LabelEntry

ICON_FILE = 'stripchart.ico'
FILECHARS = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_'

BGCOL  = (250, 250, 240)

POLLTIME = 25

STY  = wx.GROW|wx.ALL|wx.ALIGN_CENTER_VERTICAL
LSTY = wx.ALIGN_LEFT|wx.EXPAND|wx.ALL|wx.ALIGN_CENTER_VERTICAL
CSTY = wx.ALIGN_CENTER|wx.ALIGN_CENTER_VERTICAL


MENU_EXIT   = wx.NewId()
MENU_SAVE_IMG = wx.NewId()
MENU_SAVE_DAT = wx.NewId()
MENU_CONFIG = wx.NewId()
MENU_UNZOOM = wx.NewId()
MENU_HELP   = wx.NewId()
MENU_ABOUT  = wx.NewId()
MENU_PRINT  = wx.NewId()
MENU_PSETUP = wx.NewId()
MENU_PREVIEW = wx.NewId()
MENU_CLIPB  = wx.NewId()
MENU_SELECT_COLOR = wx.NewId()
MENU_SELECT_SMOOTH = wx.NewId()


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

class MyChoice(wx.Choice):
    """Simplified wx Choice"""
    def __init__(self, parent, choices=('No', 'Yes'),
                 defaultyes=True, size=(75, -1)):
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

class MCADisplay(wx.Frame):
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

    about_msg =  """Epics MCA Display  version 0.1
Matt Newville <newville@cars.uchicago.edu>
"""

    def __init__(self, mca_pv=None, parent=None):

        self.mca_pv = '13SDD1:mca1'

        self.mca_pv = 'Py:long2k'
        self.needs_refresh = False
        self.paused = False
        self.mca_data = np.ones(2048)
        self.mca_en = None
        self.mca_data_sum = 0
        self.create_frame(parent)

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.onUpdatePlot, self.timer)
        self.timer.Start(POLLTIME)
        self.init_epics()

    @EpicsFunction
    def init_epics(self):
        self.pv = PV(self.mca_pv, callback=self.onMCAData)
        self.pv.connect()

    def create_frame(self, parent, size=(750, 450), **kwds):
        self.parent = parent

        kwds['style'] = wx.DEFAULT_FRAME_STYLE|wx.TAB_TRAVERSAL
        kwds['size']  = size
        wx.Frame.__init__(self, parent, -1, 'Epics MCA Display', **kwds)

        self.build_statusbar()

        self.plotpanel = PlotPanel(self, trace_color_callback=self.onTraceColor)
        self.plotpanel.messenger = self.write_message
        self.build_menus()
        self.SetBackgroundColour(wx.Colour(*BGCOL))

        mainsizer = wx.BoxSizer(wx.VERTICAL)

        mainsizer.Add(self.plotpanel, 1, wx.EXPAND, 5)
        self.SetAutoLayout(True)
        self.SetSizer(mainsizer)
        self.Fit()

        try:
            self.SetIcon(wx.Icon(ICON_FILE, wx.BITMAP_TYPE_ICO))
        except:
            pass

        self.Refresh()


    def build_statusbar(self):
        sbar = self.CreateStatusBar(2, wx.CAPTION|wx.THICK_FRAME)
        sfont = sbar.GetFont()
        sfont.SetWeight(wx.BOLD)
        sfont.SetPointSize(10)
        sbar.SetFont(sfont)
        self.SetStatusWidths([-5, -2])
        self.SetStatusText('', 0)

    def write_message(self, s, panel=0):
        """write a message to the Status Bar"""
        self.SetStatusText(s, panel)

    def build_menus(self):
        mbar = wx.MenuBar()

        mfile = wx.Menu()
        mfile.Append(MENU_SAVE_DAT, "&Save Data\tCtrl+S",
                     "Save PNG Image of Plot")
        mfile.Append(MENU_SAVE_IMG, "Save Plot Image\t",
                     "Save PNG Image of Plot")
        mfile.Append(MENU_CLIPB, "&Copy Image to Clipboard\tCtrl+C",
                     "Copy Plot Image to Clipboard")
        mfile.AppendSeparator()
        mfile.Append(MENU_PSETUP, 'Page Setup...', 'Printer Setup')
        mfile.Append(MENU_PREVIEW, 'Print Preview...', 'Print Preview')
        mfile.Append(MENU_PRINT, "&Print\tCtrl+P", "Print Plot")
        mfile.AppendSeparator()
        mfile.Append(MENU_EXIT, "E&xit\tCtrl+Q", "Exit the 2D Plot Window")

        mopt = wx.Menu()
        mopt.Append(MENU_CONFIG, "Configure Plot\tCtrl+K",
                 "Configure Plot styles, colors, labels, etc")
        mopt.AppendSeparator()
        mopt.Append(MENU_UNZOOM, "Zoom Out\tCtrl+Z",
                 "Zoom out to full data range")

        mhelp = wx.Menu()
        mhelp.Append(MENU_HELP, "Quick Reference",  "Quick Reference for MPlot")
        mhelp.Append(MENU_ABOUT, "About", "About MPlot")

        mbar.Append(mfile, "File")
        mbar.Append(mopt, "Options")
        mbar.Append(mhelp, "&Help")

        self.SetMenuBar(mbar)
        self.Bind(wx.EVT_MENU, self.onHelp,     id=MENU_HELP)
        self.Bind(wx.EVT_MENU, self.onAbout,    id=MENU_ABOUT)
        self.Bind(wx.EVT_MENU, self.onExit,     id=MENU_EXIT)
        self.Bind(wx.EVT_CLOSE, self.onExit)

        pp = self.plotpanel
        self.Bind(wx.EVT_MENU, pp.configure,    id=MENU_CONFIG)
        self.Bind(wx.EVT_MENU, pp.unzoom_all,   id=MENU_UNZOOM)
        self.Bind(wx.EVT_MENU, pp.save_figure,  id=MENU_SAVE_IMG)
        self.Bind(wx.EVT_MENU, pp.Print,        id=MENU_PRINT)
        self.Bind(wx.EVT_MENU, pp.PrintSetup,   id=MENU_PSETUP)
        self.Bind(wx.EVT_MENU, pp.PrintPreview, id=MENU_PREVIEW)
        self.Bind(wx.EVT_MENU, pp.canvas.Copy_to_Clipboard, id=MENU_CLIPB)


    def onTraceColor(self, trace, color, **kws):
        irow = self.get_current_traces()[trace][0] - 1
        self.colorsels[irow].SetColour(color)



    @DelayedEpicsCallback
    def onMCAData(self, pvname=None, value=None, timestamp=None, **kw):
        if timestamp is None:
            timestamp = time.time()
        print 'onMCA DATA!! ', len(value), value.sum(), timestamp
        self.mca_data = value[:]
        self.needs_refresh = True


    def onAbout(self, event=None):
        dlg = wx.MessageDialog(self, self.about_msg,
                               "About Epics MCA Display",
                               wx.OK | wx.ICON_INFORMATION)
        dlg.ShowModal()
        dlg.Destroy()

    def onHelp(self, event=None):
        dlg = wx.MessageDialog(self, self.help_msg, "Epics MCA Display Help",
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
                    traces.append((irow, name, logs, color, ymin, ymax))
        return traces

    def onUpdatePlot(self, event=None):
        if self.paused or not self.needs_refresh:
            return

        if (len(self.mca_data) < 1 or 
            self.mca_data.sum() ==  self.mca_data_sum):
            return
        self.mca_data_sum = self.mca_data.sum()
        ppanel = self.plotpanel
        did_update = False

        if self.mca_en is None: # first plot!
            self.mca_en = np.arange(len(self.mca_data))
            ppanel.plot(self.mca_en*1.0, 1.0*self.mca_data, 
                        xmax=self.mca_en.max(),
                        ylog_scale=True, autoscale=True)
            did_update = True
        else:
            try:
                ppanel.update_line(0, self.mca_en, self.mca_data, 
                                   draw=False, update_limits=False)
                # self.plotpanel.plot(tdat, ydat, draw=False, update_limits=True)    
                # self.plotpanel.set_xylims((self.tmin, 0, ymin, ymax),
                #                          side=side, autoscale=False)
                did_update = True
            except:
                pass

        if did_update:
            self.plotpanel.canvas.draw()
        self.needs_refresh = not did_update
        return

if __name__ == '__main__':
    app = wx.PySimpleApp()
    f = StripChart()
    f.Show(True)
    app.MainLoop()
