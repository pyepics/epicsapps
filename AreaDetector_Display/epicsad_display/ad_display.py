#!/usr/bin/env python
"""
areaDetector Display

"""
import os
import sys
import time

from functools import partial
from collections import namedtuple



import numpy as np
import matplotlib.cm as colormap

import wx
import wx.lib.mixins.inspection
is_wxPhoenix = 'phoenix' in wx.PlatformInfo
try:
    from wx._core import PyDeadObjectError
except:
    PyDeadObjectError = Exception

from wxmplot.plotframe import PlotFrame

import epics
from epics.wx import (DelayedEpicsCallback, EpicsFunction)

from wxutils import (GridPanel, SimpleText, MenuItem, OkCancel,
                     FileOpen, SavedParameterDialog, Font)

try:
    from pyFAI.azimuthalIntegrator import AzimuthalIntegrator
    HAS_PYFAI = True
except ImportError:
    HAS_PYFAI = False

from .contrast_control import ContrastControl
from .calibration_dialog import CalibrationDialog, read_poni
from .imagepanel import ADMonoImagePanel
from .pvconfig import PVConfigPanel
from .ad_config import read_adconfig

topdir, _s = os.path.split(__file__)
DEFAULT_ICONFILE = os.path.join(topdir, 'icons', 'camera.ico')

labstyle = wx.ALIGN_LEFT|wx.ALIGN_BOTTOM|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL
rlabstyle = wx.ALIGN_RIGHT|wx.RIGHT|wx.TOP|wx.EXPAND
txtstyle = wx.ALIGN_LEFT|wx.ST_NO_AUTORESIZE|wx.TE_PROCESS_ENTER

class ADFrame(wx.Frame):
    """
    AreaDetector Display Frame
    """
    def __init__(self, configfile=None):
        wx.Frame.__init__(self, None, -1, 'AreaDetector Viewer',
                          style=wx.DEFAULT_FRAME_STYLE)

        if configfile is None:
            wcard = 'Detector Config Files (*.yaml)|*.yaml|All files (*.*)|*.*'
            configfile = FileOpen(self, "Read Detector Configuration File",
                                  default_file='det.yaml',
                                  wildcard=wcard)
        if configfile is None:
            sys.exit()

        self.config = read_adconfig(configfile)
        self.prefix = self.config['general']['prefix']
        self.fname = self.config['general']['name']
        self.colormode = self.config['general']['colormode'].lower()
        self.cam_attrs = self.config['cam_attributes']
        self.img_attrs = self.config['img_attributes']
        self.fsaver = self.config['general']['filesaver']

        self.SetTitle(self.config['general']['title'])

        self.calib = {}
        self.ad_img = None
        self.ad_cam = None
        self.lineplotter = None
        self.integrator = None
        self.int_panel = None
        self.int_lastid = None
        self.contrast_levels = None

        self.buildMenus()
        self.buildFrame()

    def buildFrame(self):
        self.SetFont(Font(11))

        sbar = self.CreateStatusBar(3, wx.CAPTION)
        self.SetStatusWidths([-1, -1, -1])
        self.SetStatusText('',0)

        sizer = wx.GridBagSizer(3, 3)
        panel = self.panel = wx.Panel(self)
        pvpanel = PVConfigPanel(panel, self.prefix, self.config['controls'])

        wsize = (100, -1)
        lsize = (250, -1)

        start_btn = wx.Button(panel, label='Start',    size=wsize)
        stop_btn  = wx.Button(panel, label='Stop',     size=wsize)
        start_btn.Bind(wx.EVT_BUTTON, partial(self.onButton, key='start'))
        stop_btn.Bind(wx.EVT_BUTTON,  partial(self.onButton, key='stop'))

        self.contrast = ContrastControl(panel, callback=self.set_contrast_level)
        self.imagesize = wx.StaticText(panel, label='? x ?',
                                       size=(150, 30), style=txtstyle)


        def lin(len=200, wid=2, style=wx.LI_HORIZONTAL):
            return wx.StaticLine(panel, size=(len, wid), style=style)

        irow = 0
        sizer.Add(pvpanel,  (irow, 0), (1, 3), labstyle)

        irow += 1
        sizer.Add(start_btn, (irow, 0), (1, 1), labstyle)
        sizer.Add(stop_btn,  (irow, 1), (1, 1), labstyle)

        if self.config['general'].get('show_free_run', False):
            free_btn  = wx.Button(panel, label='Free Run', size=wsize)
            free_btn.Bind(wx.EVT_BUTTON,  partial(self.onButton, key='free'))
            irow += 1
            sizer.Add(free_btn,  (irow, 0), (1, 2), labstyle)

        irow += 1
        sizer.Add(lin(200, wid=4),  (irow, 0), (1, 3), labstyle)

        irow += 1
        sizer.Add(self.imagesize, (irow, 0), (1, 3), labstyle)

        if self.colormode.startswith('mono'):
            self.cmap_choice = wx.Choice(panel, size=(80, -1),
                                         choices=self.config['colormaps'])
            self.cmap_choice.SetSelection(0)
            self.cmap_choice.Bind(wx.EVT_CHOICE,  self.onColorMap)
            self.cmap_reverse = wx.CheckBox(panel, label='Reverse', size=(60, -1))
            self.cmap_reverse.Bind(wx.EVT_CHECKBOX,  self.onColorMap)

            irow += 1
            sizer.Add(wx.StaticText(panel, label='Color Map: '),
                      (irow, 0), (1, 1), labstyle)

            sizer.Add(self.cmap_choice,  (irow, 1), (1, 1), labstyle)
            sizer.Add(self.cmap_reverse, (irow, 2), (1, 1), labstyle)

        irow += 1
        sizer.Add(self.contrast.label,  (irow, 0), (1, 1), labstyle)
        sizer.Add(self.contrast.choice, (irow, 1), (1, 1), labstyle)

        if self.config['general']['show_1dintegration']:
            self.show1d_btn = wx.Button(panel, label='Show 1D Integration',
                                         size=(200, -1))
            self.show1d_btn.Bind(wx.EVT_BUTTON, self.onShowIntegration)
            self.show1d_btn.Disable()

            irow += 1
            sizer.Add(self.show1d_btn, (irow, 0), (1, 2), labstyle)

        panel.SetSizer(sizer)
        sizer.Fit(panel)

        # image panel
        self.image = ADMonoImagePanel(self, prefix=self.prefix,
                                      rot90=self.config['general']['default_rotation'],
                                      size=(750, 750),
                                      writer=partial(self.write, panel=1),
                                      motion_writer=partial(self.write, panel=2))

        mainsizer = wx.BoxSizer(wx.HORIZONTAL)
        mainsizer.Add(panel, 0, wx.LEFT|wx.GROW|wx.ALL)
        mainsizer.Add(self.image, 1, wx.CENTER|wx.GROW|wx.ALL)
        self.SetSizer(mainsizer)
        mainsizer.Fit(self)

        self.SetAutoLayout(True)
        iconfile = self.config['general'].get('iconfile', None)
        if iconfile is None or not os.path.exists(iconfile):
            iconfile = DEFAULT_ICONFILE
        print("IconFile ", iconfile)
        try:
            self.SetIcon(wx.Icon(iconfile, wx.BITMAP_TYPE_ICO))
        except:
            pass
        self.connect_pvs()

    def onColorMap(self, event=None):
        cmap_name = self.cmap_choice.GetStringSelection()
        if self.cmap_reverse.IsChecked():
            cmap_name = cmap_name + '_r'
        self.image.colormap = getattr(colormap, cmap_name)
        self.image.Refresh()

    def onCopyImage(self, event=None):
        "copy bitmap of canvas to system clipboard"
        bmp = wx.BitmapDataObject()
        bmp.SetBitmap(wx.Bitmap(self.image.GrabWxImage()))
        wx.TheClipboard.Open()
        wx.TheClipboard.SetData(bmp)
        wx.TheClipboard.Close()
        wx.TheClipboard.Flush()

    def onReadCalibFile(self, event=None):
        "read calibration file"
        wcards = "Poni Files(*.poni)|*.poni|All files (*.*)|*.*"
        dlg = wx.FileDialog(None, message='Read Calibration File',
                            defaultDir=os.getcwd(),
                            wildcard=wcards,
                            style=wx.FD_OPEN)
        ppath = None
        if dlg.ShowModal() == wx.ID_OK:
            ppath = os.path.abspath(dlg.GetPath())

        if os.path.exists(ppath):
            self.setup_calibration(read_poni(ppath))

    def setup_calibration(self, calib):
        """set up calibration from calibration dict"""
        if self.image.rot90 in (1, 3):
            calib['rot3'] = np.pi/2.0
        self.calib = calib
        if HAS_PYFAI:
            self.integrator = AzimuthalIntegrator(**calib)
            self.show1d_btn.Enable()

    def onShowIntegration(self, event=None):

        if self.calib is None or 'poni1' not in self.calib:
            return
        shown = False
        try:
            self.int_panel.Raise()
            shown = True
        except:
            self.int_panel = None
        if not shown:
            self.int_panel = PlotFrame(self)
            self.show_1dpattern(init=True)
        else:
            self.show_1dpattern()

    def onAutoIntegration(self, event=None):
        if not event.IsChecked():
            self.int_timer.Stop()
            return

        if self.calib is None or 'poni1' not in self.calib:
            return
        shown = False
        try:
            self.int_panel.Raise()
            shown = True
        except:
            self.int_panel = None
        if not shown:
            self.int_panel = PlotFrame(self)
            self.show_1dpattern(init=True)
        else:
            self.show_1dpattern()
        self.int_timer.Start(500)

    def show_1dpattern(self, init=False):
        if self.calib is None or not HAS_PYFAI:
            return

        img = self.ad_img.PV('ArrayData').get()

        h, w = self.image.GetImageSize()
        img.shape = (w, h)
        # img = img[3:-3, 1:-1][::-1, :]

        img_id = self.ad_cam.ArrayCounter_RBV
        q, xi = self.integrator.integrate1d(img, 2048, unit='q_A^-1',
                                            correctSolidAngle=True,
                                            polarization_factor=0.999)
        if init:
            self.int_panel.plot(q, xi, xlabel=r'$Q (\rm\AA^{-1})$', marker='+',
                                title='Image %d' % img_id)
            self.int_panel.Raise()
            self.int_panel.Show()
        else:
            self.int_panel.update_line(0, q, xi, draw=True)
            self.int_panel.set_title('Image %d' % img_id)

    @EpicsFunction
    def onSaveImage(self, event=None):
        "prompts for and save image to file"
        defdir = os.getcwd()
        self.fname = "Image_%i.tiff"  % self.ad_cam.ArrayCounter_RBV
        dlg = wx.FileDialog(None, message='Save Image as',
                            defaultDir=os.getcwd(),
                            defaultFile=self.fname,
                            style=wx.FD_SAVE)
        path = None
        if dlg.ShowModal() == wx.ID_OK:
            path = os.path.abspath(dlg.GetPath())


        root, fname = os.path.split(path)
        epics.caput("%s%sFileName" % self.prefix, self.fsaver, fname)
        epics.caput("%s%sFileWriteMode" % self.prefix, self.fsaver, 0)
        time.sleep(0.05)
        epics.caput("%s%sWriteFile" % self.prefix, self.fsaver, 1)
        time.sleep(0.05)

        file_pv = "%s%sFullFileName_RBV" % (self.prefix, self.prefix)
        print("Saved image File ", epics.caget(file_pv,  as_string=True))

    def onExit(self, event=None):
        try:
            wx.Yield()
        except:
            pass
        self.Destroy()

    def onAbout(self, event=None):
        msg =  """areaDetector Display version 0.2
Matt Newville <newville@cars.uchicago.edu>"""

        dlg = wx.MessageDialog(self, msg, "About areaDetector Display",
                               wx.OK | wx.ICON_INFORMATION)
        dlg.ShowModal()
        dlg.Destroy()

    def buildMenus(self):
        fmenu = wx.Menu()
        MenuItem(self, fmenu, "&Save\tCtrl+S", "Save Image", self.onSaveImage)
        MenuItem(self, fmenu, "&Copy\tCtrl+C", "Copy Image to Clipboard",
                 self.onCopyImage)
        MenuItem(self, fmenu, "Read Calibration File", "Read PONI Calibration",
                 self.onReadCalibFile)
        fmenu.AppendSeparator()
        MenuItem(self, fmenu, "E&xit\tCtrl+Q",  "Exit Program", self.onExit)

        omenu = wx.Menu()
        MenuItem(self, omenu,  "&Rotate CCW\tCtrl+R", "Rotate Counter Clockwise", self.onRot90)
        MenuItem(self, omenu,  "Flip Up/Down\tCtrl+T", "Flip Up/Down", self.onFlipV)
        MenuItem(self, omenu,  "Flip Left/Right\tCtrl+F", "Flip Left/Right", self.onFlipH)
        MenuItem(self, omenu,  "Reset Rotations and Flips", "Reset", self.onResetRotFlips)
        omenu.AppendSeparator()

        hmenu = wx.Menu()
        MenuItem(self, hmenu, "About", "About areaDetector Display", self.onAbout)

        mbar = wx.MenuBar()
        mbar.Append(fmenu, "File")
        mbar.Append(omenu, "Options")

        mbar.Append(hmenu, "&Help")
        self.SetMenuBar(mbar)

    def onResetRotFlips(self, event):
        self.image.rot90 = 0
        self.image.flipv = self.image.fliph = False

    def onRot90(self, event):
        self.image.rot90 = (self.image.rot90 - 1) % 4

    def onFlipV(self, event):
        self.image.flipv= not self.image.flipv

    def onFlipH(self, event):
        self.image.fliph = not self.image.fliph

    def set_contrast_level(self, contrast_level=0):
        self.image.contrast_levels = [contrast_level, 100.0-contrast_level]
        self.image.Refresh()

    def write(self, s, panel=0):
        """write a message to the Status Bar"""
        self.SetStatusText(text=s, number=panel)

    @EpicsFunction
    def onButton(self, event=None, key='free'):
        key = key.lower()
        if key.startswith('free'):
            ftime = self.config['general']['free_run_time']
            self.image.restart_fps_counter()
            self.ad_cam.AcquireTime   = ftime
            self.ad_cam.AcquirePeriod = ftime
            self.ad_cam.NumImages = int((3*86400.)/ftime)
            self.ad_cam.Acquire = 1
        elif key.startswith('start'):
            self.image.restart_fps_counter()
            self.ad_cam.Acquire = 1
        elif key.startswith('stop'):
            self.ad_cam.Acquire = 0

    @EpicsFunction
    def connect_pvs(self, verbose=True):
        if self.prefix is None or len(self.prefix) < 2:
            return
        self.write('Connecting to areaDetector %s' % self.prefix)

        self.ad_img = epics.Device(self.prefix + 'image1:', delim='',
                                   attrs=self.img_attrs)
        self.ad_cam = epics.Device(self.prefix + 'cam1:', delim='',
                                   attrs=self.cam_attrs)


        if self.config['general']['use_filesaver']:
            epics.caput("%s%sEnableCallbacks" % (self.prefix, self.fsaver), 1)
            epics.caput("%s%sAutoSave" % (self.prefix, self.fsaver), 0)
            epics.caput("%s%sAutoIncrement" % (self.prefix, self.fsaver), 0)
            epics.caput("%s%sFileWriteMode" % (self.prefix, self.fsaver), 0)

        time.sleep(0.002)
        if not self.ad_img.PV('UniqueId_RBV').connected:
            epics.poll()
            if not self.ad_img.PV('UniqueId_RBV').connected:
                self.write('Warning: detector seems to not be connected!')
                return
        if verbose:
            self.write('Connected to detector %s' % self.prefix)

        self.SetTitle("Epics areaDetector Display: %s" % self.prefix)

        sizex = self.ad_cam.MaxSizeX_RBV
        sizey = self.ad_cam.MaxSizeY_RBV

        sizelabel = 'Image Size: %i x %i pixels'
        try:
            sizelabel = sizelabel  % (sizex, sizey)
        except:
            sizelabel = sizelabel  % (0, 0)

        self.imagesize.SetLabel(sizelabel)

        self.ad_cam.add_callback('DetectorState_RBV',  self.onDetState)
        self.contrast.set_level_str('0.01')

    @DelayedEpicsCallback
    def onDetState(self, pvname=None, value=None, char_value=None, **kw):
        self.write(char_value, panel=0)

class areaDetectorApp(wx.App, wx.lib.mixins.inspection.InspectionMixin):
    def __init__(self, configfile=None,  **kws):
        self.configfile = configfile
        wx.App.__init__(self, **kws)

    def createApp(self):
        frame = ADFrame(configfile=self.configfile)
        frame.Show()
        self.SetTopWindow(frame)

    def OnInit(self):
        self.createApp()
        return True

if __name__ == '__main__':
    configfile = None
    if len(sys.argv) > 1:
        configfile = sys.argv[1]
    areaDetectorApp(configfile=configfile).MainLoop()
