#!/usr/bin/env python
"""
areaDetector Display

"""
import os
import sys
import time
import json

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
                     FileOpen, SavedParameterDialog)


try:
    from pyFAI.azimuthalIntegrator import AzimuthalIntegrator
    HAS_PYFAI = True
except ImportError:
    HAS_PYFAI = False

from .contrast_control import ContrastControl
from .calibration_dialog import CalibrationDialog, read_poni
from .imagepanel import ADMonoImagePanel
from .pvconfig import PVConfigPanel

os.environ['EPICS_CA_MAX_ARRAY_BYTES'] = '4800000'

topdir, _s = os.path.split(__file__)
ICONFILE = os.path.join(topdir, 'icons', 'camera.ico')

DEFAULT_ROTATION = 3

labstyle = wx.ALIGN_LEFT|wx.ALIGN_BOTTOM|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL
rlabstyle = wx.ALIGN_RIGHT|wx.RIGHT|wx.TOP|wx.EXPAND
txtstyle = wx.ALIGN_LEFT|wx.ST_NO_AUTORESIZE|wx.TE_PROCESS_ENTER


##     Label,            PV Name,         Type,   RBV suffix,  Widget Size
display_pvs = [
    ('Trigger Mode',      'cam1:TriggerMode',       'pvenum',  '_RBV', 125),
    ('# Images',          'cam1:NumImages',         'pvfloat', '_RBV', 100),
    ('Acqure Period',     'cam1:AcquirePeriod',     'pvfloat', '_RBV', 100),
    ('Acquire Time',      'cam1:AcquireTime',       'pvfloat', '_RBV', 100),
    ('X-ray Energy',      'cam1:PhotonEnergy',      'pvfloat', '_RBV', 100),
    ('Energy Threshold',  'cam1:ThresholdEnergy',   'pvfloat', '_RBV', 100),
    ('TIFF File Path',    'TIFF1:FilePath',         'pvtctrl', False,  225),
    ('Acquire Status',    'cam1:Acquire',           'pvtext',  False,  225),
    ('Acquire Busy',      'cam1:AcquireBusy',       'pvtext',  False,  225),
    ('Acquire Message',   'cam1:StatusMessage_RBV', 'pvtext',  False,  225),
    ('Detector Armed',    'cam1:Armed',             'pvtext',  False,  225),
    ('Free Disk Space (Gb)', 'cam1:FWFree_RBV',     'pvtext',  False,  225),
    ]

colormaps = ['gray', 'magma', 'inferno', 'plasma',
             'viridis', 'coolwarm', 'hot', 'jet']


################

class ADFrame(wx.Frame):
    """
    AreaDetector Display Frame
    """
    img_attrs = ('ArrayData', 'UniqueId_RBV')
    cam_attrs = ('Acquire', 'DetectorState_RBV',
                 'ArrayCounter', 'ArrayCounter_RBV',
                 'ThresholdEnergy', 'ThresholdEnergy_RBV',
                 'PhotonEnergy', 'PhotonEnergy_RBV',
                 'NumImages', 'NumImages_RBV',
                 'AcquireTime', 'AcquireTime_RBV',
                 'AcquirePeriod', 'AcquirePeriod_RBV',
                 'TriggerMode', 'TriggerMode_RBV')

    # plugins to enable
    enabled_plugins = ('image1', 'Over1', 'ROI1', 'JPEG1', 'TIFF1')

    def __init__(self, prefix=None, scale=1.0):
        self.ad_img = None
        self.ad_cam = None
        if prefix is None:
            dlg = SavedParameterDialog(label='Load Detector Configuration File',
                                       title='Connect to areaDetector',
                                       configfile='.ad_display.dat')
            res = dlg.GetResponse()
            dlg.Destroy()
            if res.ok:
                prefix = res.value

        self.prefix = prefix
        self.fname = 'areaDetector.tif'

        self.calib = {}
        self.lineplotter = None
        self.integrator = None
        self.int_panel = None
        self.int_lastid = None
        self.contrast_levels = None
        self.scandb = None
        wx.Frame.__init__(self, None, -1, "Epics areaDetector Display",
                          style=wx.DEFAULT_FRAME_STYLE)

        self.buildMenus()
        self.buildFrame()

    def buildFrame(self):
        sbar = self.CreateStatusBar(3, wx.CAPTION)
        self.SetStatusWidths([-1, -1, -1])
        sfont = sbar.GetFont()
        sfont.SetWeight(wx.BOLD)
        sfont.SetPointSize(10)
        sbar.SetFont(sfont)

        self.SetStatusText('',0)

        sizer = wx.GridBagSizer(3, 3)
        panel = self.panel = wx.Panel(self)

        pvpanel = PVConfigPanel(panel, self.prefix, display_pvs)

        wsize = (100, -1)
        lsize = (250, -1)

        start_btn = wx.Button(panel, label='Start',    size=wsize)
        stop_btn  = wx.Button(panel, label='Stop',     size=wsize)
        free_btn  = wx.Button(panel, label='Free Run', size=wsize)
        start_btn.Bind(wx.EVT_BUTTON, partial(self.onButton, key='start'))
        stop_btn.Bind(wx.EVT_BUTTON,  partial(self.onButton, key='stop'))
        free_btn.Bind(wx.EVT_BUTTON,  partial(self.onButton, key='free'))

        self.cmap_choice = wx.Choice(panel, size=(80, -1),
                                             choices=colormaps)
        self.cmap_choice.SetSelection(0)
        self.cmap_choice.Bind(wx.EVT_CHOICE,  self.onColorMap)

        self.cmap_reverse = wx.CheckBox(panel, label='Reverse', size=(60, -1))
        self.cmap_reverse.Bind(wx.EVT_CHECKBOX,  self.onColorMap)

        self.show1d_btn =  wx.Button(panel, label='Show 1D Integration', size=(200, -1))
        self.show1d_btn.Bind(wx.EVT_BUTTON, self.onShowIntegration)
        self.show1d_btn.Disable()

        self.imagesize = wx.StaticText(panel, label='? x ?',
                                       size=(250, 30), style=txtstyle)

        self.contrast = ContrastControl(panel, callback=self.set_contrast_level)

        def lin(len=200, wid=2, style=wx.LI_HORIZONTAL):
            return wx.StaticLine(panel, size=(len, wid), style=style)


        irow = 0
        sizer.Add(pvpanel,  (irow, 0), (1, 3), labstyle)

        irow += 1
        sizer.Add(start_btn, (irow, 0), (1, 1), labstyle)
        sizer.Add(stop_btn,  (irow, 1), (1, 1), labstyle)
        sizer.Add(free_btn,  (irow, 2), (1, 1), labstyle)

        irow += 1
        sizer.Add(lin(300),  (irow, 0), (1, 3), labstyle)

        irow += 1
        sizer.Add(self.imagesize, (irow, 0), (1, 3), labstyle)

        irow += 1
        sizer.Add(wx.StaticText(panel, label='Color Map: '),
                  (irow, 0), (1, 1), labstyle)

        sizer.Add(self.cmap_choice,  (irow, 1), (1, 1), labstyle)
        sizer.Add(self.cmap_reverse, (irow, 2), (1, 1), labstyle)

        irow += 1
        sizer.Add(self.contrast.label,  (irow, 0), (1, 1), labstyle)
        sizer.Add(self.contrast.choice, (irow, 1), (1, 1), labstyle)

        irow += 1
        sizer.Add(self.show1d_btn, (irow, 0), (1, 2), labstyle)

        panel.SetSizer(sizer)
        sizer.Fit(panel)

        # image panel
        self.image = ADMonoImagePanel(self, prefix=self.prefix,
                                      rot90=DEFAULT_ROTATION,
                                      size=(400, 750),
                                      writer=partial(self.write, panel=2))

        mainsizer = wx.BoxSizer(wx.HORIZONTAL)
        mainsizer.Add(panel, 0, wx.LEFT|wx.GROW|wx.ALL)
        mainsizer.Add(self.image, 1, wx.CENTER|wx.GROW|wx.ALL)
        self.SetSizer(mainsizer)
        mainsizer.Fit(self)

        self.SetAutoLayout(True)
        try:
            self.SetIcon(wx.Icon(ICONFILE, wx.BITMAP_TYPE_ICO))
        except:
            pass
        wx.CallAfter(self.connect_pvs )

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
            if self.scandb is not None:
                CalibrationDialog(self, ppath).Show()
            else:
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
        img = img[3:-3, 1:-1][::-1, :]

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
        epics.caput("%sTIFF1:FileName" % self.prefix, fname)
        epics.caput("%sTIFF1:FileWriteMode" % self.prefix, 0)
        time.sleep(0.05)
        epics.caput("%sTIFF1:WriteFile" % self.prefix, 1)
        time.sleep(0.05)

        print("Saved TIFF File ",
              epics.caget("%sTIFF1:FullFileName_RBV" % self.prefix, as_string=True))

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
        self.image.rot90 = DEFAULT_ROTATION
        self.image.flipv = self.fliph = False

    def onRot90(self, event):
        self.image.rot90 = (self.image.rot90 - 1) % 4

    def onFlipV(self, event):
        self.image.flipv= not self.image.flipv

    def onFlipH(self, event):
        self.image.fliph = not self.image.fliph

    def set_contrast_level(self, contrast_level=0):
        self.image.contrast_levels = [contrast_level, 100.0-contrast_level]

    def write(self, s, panel=0):
        """write a message to the Status Bar"""
        self.SetStatusText(text=s, number=panel)

    @EpicsFunction
    def onButton(self, event=None, key='free'):
        key = key.lower()
        if key.startswith('free'):
            self.image.restart_fps_counter()
            self.ad_cam.AcquireTime   = self.config.free_run_time
            self.ad_cam.AcquirePeriod = self.config.free_run_time
            self.ad_cam.NumImages = int((3*86400.)/self.config.free_run_time)
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

        if self.prefix.endswith(':'):
            self.prefix = self.prefix[:-1]
        if self.prefix.endswith(':image1'):
            self.prefix = self.prefix[:-7]
        if self.prefix.endswith(':cam1'):
            self.prefix = self.prefix[:-5]

        self.write('Connecting to areaDetector %s' % self.prefix)
        self.ad_img = epics.Device(self.prefix + ':image1:', delim='',
                                   attrs=self.img_attrs)
        self.ad_cam = epics.Device(self.prefix + ':cam1:', delim='',
                                   attrs=self.cam_attrs)

        epics.caput("%s:TIFF1:EnableCallbacks" % self.prefix, 1)
        epics.caput("%s:TIFF1:AutoSave" % self.prefix, 0)
        epics.caput("%s:TIFF1:AutoIncrement" % self.prefix, 0)
        epics.caput("%s:TIFF1:FileWriteMode" % self.prefix, 0)

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
        self.write(char_value, panel=1)

class areaDetectorApp(wx.App, wx.lib.mixins.inspection.InspectionMixin):
    def __init__(self, prefix=None,  **kws):
        self.prefix = prefix
        wx.App.__init__(self, **kws)

    def createApp(self):
        frame = ADFrame(prefix=self.prefix)
        frame.Show()
        self.SetTopWindow(frame)

    def OnInit(self):
        self.createApp()
        return True

if __name__ == '__main__':
    areaDetectorApp(prefix=sys.argv[1]).MainLoop()
