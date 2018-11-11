#!/usr/bin/env python
"""
   Display Application for Epics AreaDetector
(in /lib)
"""
import os
import sys
import time
import json
from functools import partial

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

from epics import caget, caput
from epics.wx.utils import add_menu

HAS_SIMPLON = False
try:
    from epicsscan.detectors.ad_eiger import EigerSimplon
    HAS_SIMPLON = True
except ImportError:
    HAS_SIMPLON = False

HAS_ESCAN = False
try:
    from epicsscan import ScanDB
    HAS_ESCAN = True
except ImportError:
    HAS_ESCAN = False

from pyFAI.azimuthalIntegrator import AzimuthalIntegrator

from .autocontrast_panel import ContrastChoice
from .calibration_panel import CalibrationDialog, read_poni
from .imagepanel import ADMonoImagePanel
from .pvconfig import PVConfigPanel

os.environ['EPICS_CA_MAX_ARRAY_BYTES'] = '4800000'
ICON_FILE = 'camera.ico'

IMG_SIZE = (1024, 512)

labstyle = wx.ALIGN_LEFT|wx.ALIGN_BOTTOM|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL
rlabstyle = wx.ALIGN_RIGHT|wx.RIGHT|wx.TOP|wx.EXPAND
txtstyle=wx.ALIGN_LEFT|wx.ST_NO_AUTORESIZE|wx.TE_PROCESS_ENTER


##     Label,            PV Name,         Type,   RBV suffix,  Widget Size
display_pvs = [
    ('Trigger Mode',     'cam1:TriggerMode',     'pvenum',  '_RBV', 125),
    ('# Images',         'cam1:NumImages',       'pvfloat', '_RBV', 100),
    ('Acqure Period',    'cam1:AcquirePeriod',   'pvfloat', '_RBV', 100),
    ('Acquire Time',     'cam1:AcquireTime',     'pvfloat', '_RBV', 100),
    ('X-ray Energy',     'cam1:PhotonEnergy',    'pvfloat', '_RBV', 100),
    ('Energy Threshold', 'cam1:ThresholdEnergy', 'pvfloat', '_RBV', 100),
    ('File Pattern',     'cam1:FWNamePattern',   'pvtctrl', False,  225),
    ('File Path',        'cam1:FilePath',        'pvtctrl', False,  225),
    ]

colormaps = ['gray', 'viridis', 'coolwarm', 'inferno', 'plasma', 'magma',
             'hot', 'jet']


################
class EigerFrame(wx.Frame):
    """AreaDetector Display """

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

    def __init__(self, prefix=None, url=None, scale=1.0):
        self.ad_img = None
        self.ad_cam = None

        self.prefix = prefix
        self.fname = 'Eiger.tif'
        self.esimplon = None
        if url is not None and HAS_SIMPLON:
            self.esimplon = EigerSimplon(url, prefix=prefix+'cam1:')

        self.lineplotter = None
        self.calib = {}
        self.integrator = None
        self.int_panel = None
        self.int_lastid = None
        self.contrast_levels = None
        self.scandb = None
        wx.Frame.__init__(self, None, -1, "Eiger500K Area Detector Display",
                          style=wx.DEFAULT_FRAME_STYLE)

        self.buildMenus()
        self.buildFrame()

        wx.CallAfter(self.connect_escandb)

    def connect_escandb(self):
        if HAS_ESCAN and os.environ.get('ESCAN_CREDENTIALS', None) is not None:
            self.scandb = ScanDB()
            calib_loc = self.scandb.get_info('eiger_calibration')
            cal = self.scandb.get_detectorconfig(calib_loc)
            self.setup_calibration(json.loads(cal.text))

    def buildFrame(self):
        sbar = self.CreateStatusBar(3, wx.CAPTION) # |wx.THICK_FRAME)
        self.SetStatusWidths([-1, -1, -1])
        sfont = sbar.GetFont()
        sfont.SetWeight(wx.BOLD)
        sfont.SetPointSize(10)
        sbar.SetFont(sfont)

        self.SetStatusText('',0)

        sizer = wx.GridBagSizer(3, 3)
        panel = self.panel = wx.Panel(self)

        pvpanel = PVConfigPanel(self, self.prefix, display_pvs)

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
        self.cmap_choice.Bind(wx.EVT_CHOICE,  self.onColorMap)

        self.cmap_reverse = wx.CheckBox(panel, label='Reverse', size=(60, -1))
        self.cmap_reverse.Bind(wx.EVT_CHECKBOX,  self.onColorMap)

        self.show1d_btn =  wx.Button(panel, label='Show 1D Integration', size=(200, -1))
        self.show1d_btn.Bind(wx.EVT_BUTTON, self.onShowIntegration)

        self.imagesize = wx.StaticText(panel, label='? x ?',
                                       size=(250, 30), style=txtstyle)

        self.contrast = ContrastChoice(panel, callback=self.set_contrast_level)

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
        self.image = ADMonoImagePanel(self, prefix=self.prefix, rot90=3,
                                      size=(400, 750),
                                      writer=partial(self.write, panel=2))

        mainsizer = wx.BoxSizer(wx.HORIZONTAL)
        mainsizer.Add(panel, 0, wx.LEFT|wx.GROW|wx.ALL)
        mainsizer.Add(self.image, 1, wx.CENTER|wx.GROW|wx.ALL)
        self.SetSizer(mainsizer)
        mainsizer.Fit(self)

        self.SetAutoLayout(True)

        try:
            self.SetIcon(wx.Icon(ICON_FILE, wx.BITMAP_TYPE_ICO))
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
            self.int_panel.Raise()
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
            self.int_panel.Raise()
            self.show_1dpattern(init=True)
        else:
            self.show_1dpattern()
        self.int_timer.Start(500)

    def show_1dpattern(self, init=False):
        if self.calib is None:
            return

        img = self.ad_img.PV('ArrayData').get()
        img.shape = self.image.arrsize[1], self.image.arrsize[0]
        img = img[3:-3, 1:-1][::-1, :]

        img_id = self.ad_cam.ArrayCounter_RBV

        # print(img.shape)
        q, xi = self.integrator.integrate1d(img, 2048, unit='q_A^-1',
                                            correctSolidAngle=True,
                                            polarization_factor=0.999)
        if init:
            self.int_panel.plot(q, xi, xlabel=r'$Q (\rm\AA^{-1})$', marker='+',
                                title='Image %d' % img_id)

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
                            style=wx.SAVE)
        path = None
        if dlg.ShowModal() == wx.ID_OK:
            path = os.path.abspath(dlg.GetPath())


        root, fname = os.path.split(path)
        caput("%sTIFF1:FileName" % self.prefix, fname)
        caput("%sTIFF1:FileWriteMode" % self.prefix, 0)
        time.sleep(0.05)
        caput("%sTIFF1:WriteFile" % self.prefix, 1)
        time.sleep(0.05)

        print("Saved TIFF File ",
              caget("%sTIFF1:FullFileName_RBV" % self.prefix, as_string=True))


    def onExit(self, event=None):
        try:
            wx.Yield()
        except:
            pass
        self.Destroy()

    def onAbout(self, event=None):
        msg =  """Eiger Image Display version 0.1
Matt Newville <newville@cars.uchicago.edu>"""

        dlg = wx.MessageDialog(self, msg, "About Epics Image Display",
                               wx.OK | wx.ICON_INFORMATION)
        dlg.ShowModal()
        dlg.Destroy()

    def buildMenus(self):
        fmenu = wx.Menu()
        add_menu(self, fmenu, "&Save\tCtrl+S", "Save Image", self.onSaveImage)
        add_menu(self, fmenu, "&Copy\tCtrl+C", "Copy Image to Clipboard",
                 self.onCopyImage)
        add_menu(self, fmenu, "Read Calibration File", "Read PONI Calibration",
                 self.onReadCalibFile)
        add_menu(self, fmenu, "Show 1D integration", "Show 1D integration",
                 self.onShowIntegration)

        fmenu.AppendSeparator()
        add_menu(self, fmenu, "E&xit\tCtrl+Q",  "Exit Program", self.onExit)

        omenu = wx.Menu()
        add_menu(self, omenu,  "&Rotate CCW\tCtrl+R", "Rotate Counter Clockwise", self.onRot90)
        add_menu(self, omenu,  "Flip Up/Down\tCtrl+T", "Flip Up/Down", self.onFlipV)
        add_menu(self, omenu,  "Flip Left/Right\tCtrl+F", "Flip Left/Right", self.onFlipH)
        add_menu(self, omenu,  "Reset Rotations and Flips", "Reset", self.onResetRotFlips)
        omenu.AppendSeparator()

        hmenu = wx.Menu()
        add_menu(self, hmenu, "About", "About Epics AreadDetector Display", self.onAbout)

        mbar = wx.MenuBar()
        mbar.Append(fmenu, "File")
        mbar.Append(omenu, "Options")

        mbar.Append(hmenu, "&Help")
        self.SetMenuBar(mbar)

    def onResetRotFlips(self, event):
        self.image.rot90 = 0
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
            self.ad_cam.AcquireTime = 0.25
            self.ad_cam.AcquirePeriod = 0.25
            self.ad_cam.NumImages = 345600
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

        self.write('Connecting to AD %s' % self.prefix)
        self.ad_img = epics.Device(self.prefix + ':image1:', delim='',
                                   attrs=self.img_attrs)
        self.ad_cam = epics.Device(self.prefix + ':cam1:', delim='',
                                   attrs=self.cam_attrs)

        caput("%s:TIFF1:EnableCallbacks" % self.prefix, 1)
        caput("%s:TIFF1:AutoSave" % self.prefix, 0)
        caput("%s:TIFF1:AutoIncrement" % self.prefix, 0)
        caput("%s:TIFF1:FileWriteMode" % self.prefix, 0)

        time.sleep(0.002)
        if not self.ad_img.PV('UniqueId_RBV').connected:
            epics.poll()
            if not self.ad_img.PV('UniqueId_RBV').connected:
                self.write('Warning:  Camera seems to not be connected!')
                return
        if verbose:
            self.write('Connected to AD %s' % self.prefix)

        self.SetTitle("Epics Image Display: %s" % self.prefix)

        sizex = self.ad_cam.MaxSizeX_RBV
        sizey = self.ad_cam.MaxSizeY_RBV

        sizelabel = 'Image Size: %i x %i pixels'
        try:
            sizelabel = sizelabel  % (sizex, sizey)
        except:
            sizelabel = sizelabel  % (0, 0)

        self.imagesize.SetLabel(sizelabel)

        self.ad_cam.add_callback('DetectorState_RBV',  self.onDetState)
        self.contrast.set_level_str('0.05')

    @DelayedEpicsCallback
    def onDetState(self, pvname=None, value=None, char_value=None, **kw):
        self.write(char_value, panel=1)

class EigerApp(wx.App, wx.lib.mixins.inspection.InspectionMixin):
    def __init__(self, prefix=None, url=None, **kws):
        self.prefix = prefix
        self.url = url
        wx.App.__init__(self, **kws)

    def createApp(self):
        frame = EigerFrame(prefix=self.prefix, url=self.url)
        frame.Show()
        self.SetTopWindow(frame)

    def OnInit(self):
        self.createApp()
        return True

if __name__ == '__main__':
    EigerApp(prefix=sys.argv[1]).MainLoop()