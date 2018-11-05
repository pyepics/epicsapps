#!/usr/bin/env python
"""
   Display Application for Epics AreaDetector
(in /lib)
"""
import os
import sys
import time
import json
import numpy as np

import wx
import wx.lib.mixins.inspection
is_wxPhoenix = 'phoenix' in wx.PlatformInfo
try:
    from wx._core import PyDeadObjectError
except:
    PyDeadObjectError = Exception

import wxmplot
from wxmplot.plotframe import PlotFrame
from wxmplot.colors import hexcolor
import epics
from epics.wx import (DelayedEpicsCallback, EpicsFunction, Closure,
                      PVEnumChoice, PVFloatCtrl, PVTextCtrl, PVStaticText)
from epics import caget, caput
from epics.wx.utils import add_menu

HAS_ESCAN = False
try:
    from epicsscan import ScanDB
    HAS_ESCAN = True
except ImportError:
    HAS_ESCAN = False

from pyFAI.azimuthalIntegrator import AzimuthalIntegrator

from .autocontrast_panel import ContrastPanel
from .imagepanel import ADImagePanel

os.environ['EPICS_CA_MAX_ARRAY_BYTES'] = '4800000'
ICON_FILE = 'camera.ico'

IMG_SIZE = (1024, 512)

labstyle = wx.ALIGN_LEFT|wx.ALIGN_BOTTOM|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL
rlabstyle = wx.ALIGN_RIGHT|wx.RIGHT|wx.TOP|wx.EXPAND
txtstyle=wx.ALIGN_LEFT|wx.ST_NO_AUTORESIZE|wx.TE_PROCESS_ENTER



def read_poni(fname):
    conf = {}
    with open(fname, 'r') as fh:
        for line in fh.readlines():
            line = line[:-1].strip()
            if line.startswith('#'):
                continue
            key, val = [a.strip() for a in line.split(':')]
            key = key.lower()
            if key == 'distance': key='dist'
            if key == 'pixelsize1': key='pixel1'
            if key == 'pixelsize2': key='pixel2'
            conf[key] = float(val)
    return conf

class EigerFrame(wx.Frame):
    """AreaDetector Display """

    img_attrs = ('ArrayData', 'UniqueId_RBV', 'ArrayCounter_RBV')
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

        self.prefix = prefix
        self.fname = 'Eiger.tif'

        self.im_size = None
        self.last_update = time.time() -1000
        self.n_img   = 0
        self.n_drawn = 0
        self.img_id = 0
        self.starttime = time.time()
        self.drawing = False
        self.lineplotter = None
        self.calib = {}
        self.integrator = None
        self.int_panel = None
        self.int_lastid = None
        self.contrast_levels = None
        self.scandb = None
        wx.Frame.__init__(self, None, -1, "Eiger500K Area Detector Display",
                          style=wx.DEFAULT_FRAME_STYLE)

        self.img_w = 0
        self.img_h = 0
        self.wximage = wx.Image(3, 3)
        self.buildMenus()
        self.buildFrame()
        self.int_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.onIntTimer, self.int_timer)

        wx.CallAfter(self.connect_escandb)

    def connect_escandb(self):
        # print("Connect ESCAN DB ",
        #       HAS_ESCAN , os.environ.get('ESCAN_CREDENTIALS', '----') )
        if HAS_ESCAN and os.environ.get('ESCAN_CREDENTIALS', None) is not None:
            self.scandb = ScanDB()
            calib_loc = self.scandb.get_info('eiger_calibration')
            cal = self.scandb.get_detectorconfig(calib_loc)
            self.setup_calibration(json.loads(cal.text))




    def buildFrame(self):
        sbar = self.CreateStatusBar(3, wx.CAPTION) # |wx.THICK_FRAME)
        sfont = sbar.GetFont()
        sfont.SetWeight(wx.BOLD)
        sfont.SetPointSize(10)
        sbar.SetFont(sfont)

        self.SetStatusWidths([-3, -1, -1])
        self.SetStatusText('',0)

        sizer = wx.GridBagSizer(3, 3)
        panel = self.panel = wx.Panel(self)

        self.wids = {}
        wsize = (100, -1)
        lsize = (250, -1)
        for attr in ('PhotonEnergy', 'ThresholdEnergy', 'AcquireTime',
                     'AcquirePeriod', 'NumImages'):
            self.wids[attr] = PVFloatCtrl(panel, pv=None, size=wsize)

        for attr in ('FWNamePattern', 'FilePath'):
            self.wids[attr] = PVTextCtrl(panel, pv=None, size=lsize)

        for attr in ('AcquireTime', 'AcquirePeriod', 'NumImages',
                     'PhotonEnergy', 'ThresholdEnergy',
                     'FilePath', 'FWNamePattern'):
            size = lsize if attr.startswith('file') else wsize
            self.wids[attr + '_RBV'] = PVStaticText(panel, pv=None, size=size)

        self.wids['TriggerMode'] = PVEnumChoice(panel, pv=None, size=lsize)
        self.wids['start']    = wx.Button(panel, -1, label='Start',    size=wsize)
        self.wids['stop']     = wx.Button(panel, -1, label='Stop',     size=wsize)
        self.wids['freerun']  = wx.Button(panel, -1, label='Free Run', size=wsize)
        for key in ('start', 'stop', 'freerun'):
            self.wids[key].Bind(wx.EVT_BUTTON, Closure(self.onButton, key=key))

        self.wids['show_1dint'] =  wx.CheckBox(panel, -1, label='Show 1D Integration',
                                               size=lsize)
        self.wids['show_1dint'].SetValue(0)
        self.wids['show_1dint'].Disable()
        self.wids['show_1dint'].Bind(wx.EVT_CHECKBOX, self.onShowIntegration)

        self.wids['imagesize']= wx.StaticText(panel, -1, label='?x?',
                                              size=(250, 30), style=txtstyle)
        self.wids['contrastpanel'] = ContrastPanel(panel, callback=self.set_contrast_level)

        def txt(label, size=(125, -1)):
            return wx.StaticText(panel, label=label, size=size, style=labstyle)

        def lin(len=200, wid=2, style=wx.LI_HORIZONTAL):
            return wx.StaticLine(panel, size=(len, wid), style=style)

        def show_with_rbv(irow, title, attr, nextrow=False):
            irow  += 1
            sizer.Add(txt(title),      (irow, 0), (1, 1), labstyle)
            if nextrow:
                sizer.Add(self.wids[attr], (irow, 1), (1, 2), labstyle)
                irow += 1
                sizer.Add(self.wids['%s_RBV' % attr],  (irow, 1), (1, 2), labstyle)
            else:
                sizer.Add(self.wids[attr], (irow, 1), (1, 1), labstyle)
                sizer.Add(self.wids['%s_RBV' % attr],  (irow, 2), (1, 1), labstyle)
            return irow

        irow = 0
        sizer.Add(txt('Trigger Mode '),        (irow, 0), (1, 1), labstyle)
        sizer.Add(self.wids['TriggerMode'],    (irow, 1), (1, 2), labstyle)

        irow = show_with_rbv(irow, '# Images', 'NumImages')
        irow = show_with_rbv(irow, 'Acquire Period', 'AcquirePeriod')
        irow = show_with_rbv(irow, 'Exposure Time', 'AcquireTime')
        irow = show_with_rbv(irow, 'X-ray Energy', 'PhotonEnergy')
        irow = show_with_rbv(irow, 'Energy Threshold', 'ThresholdEnergy')

        irow = show_with_rbv(irow, 'File Pattern', 'FWNamePattern', nextrow=True)
        irow = show_with_rbv(irow, 'File Path', 'FilePath', nextrow=True)

        irow += 1
        sizer.Add(self.wids['start'],   (irow, 0), (1, 1), labstyle)
        sizer.Add(self.wids['stop'],    (irow, 1), (1, 1), labstyle)
        sizer.Add(self.wids['freerun'], (irow, 2), (1, 1), labstyle)

        irow += 1
        sizer.Add(lin(300),  (irow, 0), (1, 3), labstyle)

        irow += 1
        sizer.Add(self.wids['imagesize'], (irow, 0), (1, 3), labstyle)

        irow += 1
        sizer.Add(self.wids['contrastpanel'], (irow, 0), (1, 3), labstyle)

        irow += 1
        sizer.Add(self.wids['show_1dint'], (irow, 0), (1, 3), labstyle)


        panel.SetSizer(sizer)
        sizer.Fit(panel)

        # image panel
        self.image = ADImagePanel(self, prefix=self.prefix, rot90=3)


        mainsizer = wx.BoxSizer(wx.HORIZONTAL)
        mainsizer.Add(panel, 0, wx.LEFT|wx.GROW|wx.ALL, 5)
        mainsizer.Add(self.image, 1, wx.CENTER|wx.GROW|wx.ALL, 5)
        self.SetSizer(mainsizer)
        mainsizer.Fit(self)

        self.SetAutoLayout(True)

        try:
            self.SetIcon(wx.Icon(ICON_FILE, wx.BITMAP_TYPE_ICO))
        except:
            pass

        # self.RefreshImage()
        wx.CallAfter(self.connect_pvs )

    def OnLeftUp(self, event):
        if self.image is not None:
            self.image.OnLeftUp(event)

    def onCopyImage(self, event=None):
        "copy bitmap of canvas to system clipboard"
        bmp = wx.BitmapDataObject()
        bmp.SetBitmap(wx.Bitmap(self.wximage))
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
        path = None
        if dlg.ShowModal() == wx.ID_OK:
            path = os.path.abspath(dlg.GetPath())

        if os.path.exists(path):
            self.setup_calibration(read_poni(path))

    def setup_calibration(self, calib):
        """set up calibration from calibration dict"""
        self.calib = calib
        print("Set calibration to ", calib)
        self.integrator = AzimuthalIntegrator(**calib)
        self.wids['show_1dint'].Enable()

    def onShowIntegration(self, event=None):
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

    def onIntTimer(self, evt=None):
        "timer for integration"
        if self.calib is not None and self.img_id != self.int_lastid:
            wx.CallAfter(self.show_1dpattern)

    def show_1dpattern(self, init=False):
        if self.calib is None:
            return

        img = self.ad_img.PV('ArrayData').get()
        img.shape = self.image.arrsize[0], self.image.arrsize[1]
        img = img[3:-3, 1:-1][:,::-1].transpose()

        # print(img.shape)
        q, xi = self.integrator.integrate1d(img, 2048, unit='q_A^-1',
                                            correctSolidAngle=True,
                                            polarization_factor=0.999)
        if init:
            self.int_panel.plot(q, xi, xlabel=r'$Q (\rm\AA^{-1})$', marker='+',
                                title='Image %d' % self.img_id)

        else:
            self.int_panel.update_line(0, q, xi, draw=True)
            self.int_panel.set_title('Image %d' % self.img_id)

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
        wx.CallAfter(Closure(self.SetStatusText, text=s, number=panel))

    def onButton(self, evt=None, key='name', **kw):
        if evt is not None:
            self.onControl(key)

    @EpicsFunction
    def onControl(self, key='freerun'):
        key = key.lower()
        if key.startswith('free'):
            self.ad_cam.AcquireTime = 0.25
            self.ad_cam.AcquirePeriod = 0.25
            self.ad_cam.NumImages = 345600
            self.ad_cam.Acquire = 1
        elif key.startswith('start'):
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

        for attr in ('AcquireTime', 'AcquirePeriod', 'NumImages',
                     'FWNamePattern', 'FilePath', 'TriggerMode',
                     'PhotonEnergy', 'ThresholdEnergy'):
            if attr in self.wids:
                self.wids[attr].SetPV(self.ad_cam.PV(attr))
            rbv = attr + '_RBV'
            if rbv in self.wids:
                self.wids[rbv].SetPV(self.ad_cam.PV(rbv))

        sizex = self.ad_cam.MaxSizeX_RBV
        sizey = self.ad_cam.MaxSizeY_RBV

        sizelabel = 'Image Size: %i x %i pixels'
        try:
            sizelabel = sizelabel  % (sizex, sizey)
        except:
            sizelabel = sizelabel  % (0, 0)

        self.wids['imagesize'].SetLabel(sizelabel)

        self.ad_cam.add_callback('DetectorState_RBV',  self.onDetState)
        self.ad_cam.add_callback('ArrayCounter_RBV',  self.onArrayCounter)

        self.image.SetSize((425, 775))
        self.wids['contrastpanel'].set_level_str('0.02')

    @DelayedEpicsCallback
    def onDetState(self, pvname=None, value=None, char_value=None, **kw):
        self.write(char_value, panel=1)

    @DelayedEpicsCallback
    def onArrayCounter(self, pvname=None, value=None, char_value=None, **kw):
        self.write("Image %d" % value, panel=2)
        self.img_id = value

class EigerApp(wx.App, wx.lib.mixins.inspection.InspectionMixin):
    def __init__(self, prefix=None, **kws):
        self.prefix = prefix
        wx.App.__init__(self, **kws)

    def createApp(self):
        frame = EigerFrame(prefix=self.prefix)
        frame.Show()
        self.SetTopWindow(frame)

    def OnInit(self):
        self.createApp()
        return True

if __name__ == '__main__':
    EigerApp(prefix=sys.argv[1]).MainLoop()
