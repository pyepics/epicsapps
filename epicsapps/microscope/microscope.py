import wx
import wx.lib.mixins.inspection
import numpy as np
import sys
import time
import os
import shutil

from threading import Thread
from collections import namedtuple, OrderedDict
from functools import partial

import base64
import json

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

import matplotlib
matplotlib.use('WXAgg')
from wxmplot import PlotFrame

from epics import caput, Motor
from epics.wx import EpicsFunction

from epics.wx.utils import (add_menu, LTEXT, CEN, LCEN, RCEN, RIGHT)

from wxutils import (GridPanel, OkCancel, FloatSpin, NumericCombo,
                     SimpleText, FileSave, FileOpen, pack, Popup, fix_filename)

from .configfile import MicroscopeConfig, CONFFILE, get_default_configfile
from .icons import icons
from .controlpanel import ControlPanel
from .positionpanel import PositionPanel
from .overlayframe import OverlayFrame
from .calibrationframe import CalibrationFrame

from .imagepanel_base import ZoomPanel
from .imagepanel_pyspin import ImagePanel_PySpin, ConfPanel_PySpin
from .imagepanel_fly2 import ImagePanel_Fly2AD, ConfPanel_Fly2AD
from .imagepanel_epicsAD import ImagePanel_EpicsAD, ConfPanel_EpicsAD
from .imagepanel_epicsarray import ImagePanel_EpicsArray, ConfPanel_EpicsArray
from .imagepanel_weburl import ImagePanel_URL, ConfPanel_URL

from ..utils import SelectWorkdir, get_icon

try:
    from .imagepanel_zmqjpeg import ImagePanel_ZMQ, ConfPanel_ZMQ
except ImportError:
    ImagePanel_ZMQ = ImagePanel_URL
    ConfPanel_ZMQ = ConfPanel_URL


ALL_EXP  = wx.ALL|wx.GROW
CEN_ALL  = wx.ALIGN_CENTER_VERTICAL
LEFT_CEN = wx.ALIGN_LEFT
LEFT_TOP = wx.ALIGN_LEFT|wx.ALIGN_TOP
LEFT_BOT = wx.ALIGN_LEFT|wx.ALIGN_BOTTOM
CEN_TOP  = wx.ALIGN_TOP
CEN_BOT  = wx.ALIGN_BOTTOM

txtstyle = wx.ALIGN_LEFT|wx.ST_NO_AUTORESIZE|wx.TE_PROCESS_ENTER

def image_blurriness(imgpanel, full=False):
    """ get image blurriness of central half of intensity

    want to maximize sharpness = sum([image - <image>]**2)

    """
    img = imgpanel.GrabNumpyImage().astype(np.float32)
    if len(img.shape) == 3:
        img = img.sum(axis=2)
    w, h = img.shape
    w1, w2, h1, h2 = int(0.15*w), int(0.85*w), int(0.15*h), int(0.85*h)
    img = img[w1:w2, h1:h2]
    sharpness = ((img - img.mean())**2).sum()/(w*h)
    return -sharpness


class VideoDialog(wx.Dialog):
    """dialog for video options"""
    def __init__(self, parent, name,  **kws):
        title = "Video Capture"
        wx.Dialog.__init__(self, parent, wx.ID_ANY, title=title)

        panel = GridPanel(self, ncols=3, nrows=2, pad=2, itemstyle=LCEN)

        self.filename = wx.TextCtrl(panel, -1, 'Capture.avi',  size=(150, -1))
        self.runtime  = wx.TextCtrl(panel, -1, '15.0',   size=(150, -1))

        panel.Add(SimpleText(panel, 'File Name : '), newrow=True)
        panel.Add(self.filename)
        panel.Add(SimpleText(panel, 'Run Time: '), newrow=True)
        panel.Add(self.runtime)
        panel.Add(OkCancel(panel), dcol=2, newrow=True)
        panel.pack()

    def GetResponse(self, newname=None):
        self.Raise()
        response = namedtuple('RenameResponse', ('ok', 'runtime', 'filename'))
        runtime, filename, ok = 0, '', False
        if self.ShowModal() == wx.ID_OK:
            filename = self.filename.GetValue()
            runtime  = float(self.runtime.GetValue())
            ok = True
        return response(ok, runtime, filename)

class CompositeDialog(wx.Dialog):
    """dialog for composite options"""
    def __init__(self, parent, **kws):
        title = "Capture Composite Image"
        wx.Dialog.__init__(self, parent, wx.ID_ANY, title=title)

        panel = GridPanel(self, ncols=3, nrows=2, pad=2, itemstyle=LCEN)

        self.cal = cal = [x for x in parent.calibrations[parent.calib_current]]
        self.filename = wx.TextCtrl(panel, -1, 'Composite01',  size=(250, -1))
        self.size     = FloatSpin(panel, value=10.0, min_val=0, increment=1)

        panel.Add(SimpleText(panel, 'File Name : '), newrow=True)
        panel.Add(self.filename)
        panel.Add(SimpleText(panel, 'Image Size (mm): '), newrow=True)
        panel.Add(self.size)
        panel.Add(SimpleText(panel, 'Pixel Size = %.3f x %.3f um' % (cal[0], cal[1])),
                  dcol=2, newrow=True)
        panel.Add(OkCancel(panel), dcol=2, newrow=True)
        panel.pack()

    def GetResponse(self, newname=None):
        self.Raise()
        response = namedtuple('CompositeResponse', ('ok', 'size', 'cal', 'filename'))
        size, filename, ok = 1, '', False
        if self.ShowModal() == wx.ID_OK:
            filename = self.filename.GetValue()
            size = self.size.GetValue()
            ok = True
        return response(ok, size, self.cal, filename)

class MicroscopeFrame(wx.Frame):
    htmllog  = 'SampleStage.html'
    html_header = """<html><head><title>Sample Microscope Log</title></head>
<meta http-equiv='Pragma'  content='no-cache'>
<meta http-equiv='Refresh' content='300'>
<body>
    """
    def __init__(self, configfile=None, prompt=True, **kws):
        wx.Frame.__init__(self, parent=None, size=(1500, 750), **kws)
        self.SetFont(wx.Font(10, wx.SWISS, wx.NORMAL, wx.BOLD, False))
        self.SetTitle('Sample Microscope')
        if configfile is None:
            configfile = get_default_configfile(CONFFILE)
        if configfile is None:
            default_file = configfile or CONFFILE
            fpath, fname = os.path.split(default_file)
            wcard = 'Detector Config Files (*.yaml)|*.yaml|All files (*.*)|*.*'
            configfile = FileOpen(self, "Read Microscope Configuration File",
                                  default_file=fname,
                                  default_dir=fpath,
                                  wildcard=wcard)
        if configfile is None:
            sys.exit()
        self.read_config(configfile)
        try:
            os.chdir(self.config.get('workdir', os.getcwd()))
        except:
            pass
        self.videocam = self.config.get('videocam', None)
        ret = SelectWorkdir(self)
        if ret is None:
            self.Destroy()
        if ret is not None:
            os.chdir(ret)

        self.overlayframe = None
        self.calibframe = None
        self.last_pixel = None
        self.xhair_pixel = None
        self.create_frame(orientation=self.orientation)
        self.xplot = None
        self.yplot = None
        self.imgpanel.Start()

    def create_frame(self, size=(1500, 750), orientation='landscape'):
        "build main frame"
        self.statusbar = self.CreateStatusBar(2, wx.CAPTION)
        self.statusbar.SetStatusWidths([-4, -1])
        for index in range(2):
            self.statusbar.SetStatusText('', index)
        config = self.config

        opts = dict(writer=self.write_framerate,
                    publish_type=self.cam_pubtype,
                    publish_delay=self.cam_pubdelay,
                    publish_addr=self.cam_pubaddr,
                    publish_port=self.cam_pubport,
                    leftdown_cb=self.onSelectPixel,
                    motion_cb=self.onPixelMotion,
                    xhair_cb=self.onShowCrosshair,
                    lamp=self.lamp)

        autofocus_cb = self.onAutoFocus

        if self.cam_type.startswith('fly2'):
            opts['camera_id'] = int(self.cam_fly2id)
            ImagePanel, ConfPanel = ImagePanel_Fly2, ConfPanel_Fly2
        elif self.cam_type.startswith('pyspin'):
            opts['camera_id'] = int(self.cam_id)
            ImagePanel, ConfPanel = ImagePanel_PySpin, ConfPanel_PySpin
        elif self.cam_type.startswith('adfly'):
            opts['prefix'] = self.cam_adpref
            ImagePanel, ConfPanel = ImagePanel_Fly2AD, ConfPanel_Fly2AD
            autofocus_cb = None
        elif self.cam_type.startswith('area'):
            opts['prefix'] = self.cam_adpref
            ImagePanel, ConfPanel = ImagePanel_EpicsAD, ConfPanel_EpicsAD
        elif self.cam_type.startswith('webcam'):
            opts['url'] = self.cam_weburl
            ImagePanel, ConfPanel = ImagePanel_URL, ConfPanel_URL
        elif self.cam_type.startswith('zmq'):
            ImagePanel, ConfPanel = ImagePanel_ZMQ, ConfPanel_ZMQ
            opts['host'] = self.cam_pubaddr
            opts['port'] = self.cam_pubport
            autofocus_cb = None
        elif self.cam_type.startswith('epicsarray'):
            ImagePanel, ConfPanel = ImagePanel_EpicsArray, ConfPanel_EpicsArray
            opts['prefix'] = self.cam_pubaddr
            autofocus_cb = None

        self.imgpanel  = ImagePanel(self, **opts)
        self.imgpanel.SetMinSize((285, 250))

        offline_inst = config.get('offline_instrument', None)
        offline_xyz = config.get('offline_xyzmotors', None)
        safe_move   = config.get('safe_move', None)

        ppanel = wx.Panel(self)
        self.pospanel = PositionPanel(ppanel, self,
                                      instrument=config['instrument'],
                                      xyzmotors=config.get('xyzmotors', ()),
                                      offline_instrument=offline_inst,
                                      offline_xyzmotors=offline_xyz,
                                      safe_move=safe_move)

        self.ctrlpanel = ControlPanel(ppanel,
                                      groups=self.stage_groups,
                                      config=self.stages,
                                      center_cb=self.onMoveToCenter,
                                      autofocus=autofocus_cb)

        self.confpanel = ConfPanel(ppanel, image_panel=self.imgpanel,
                                   calibrations=self.calibrations,
                                   calib_cb=self.onSetCalibration, **opts)


        zpanel = wx.Panel(ppanel)
        zlab1 = wx.StaticText(zpanel, label='ZoomBox size (\u03bCm):',
                              size=(150, -1), style=txtstyle)
        # zlab2 = wx.StaticText(zpanel, label='ZoomBox Sharpness:',
        #                       size=(150, -1), style=txtstyle)
        # zsharp = wx.StaticText(zpanel, label='=',
        #                        size=(100, -1), style=txtstyle)
        self.zoomsize = FloatSpin(zpanel, value=150, min_val=5, increment=5,
                                  action=self.onZoomSize,
                                size=(80, -1), style=txtstyle)
        self.imgpanel.zoompanel = ZoomPanel(zpanel, imgsize=150,
                                            size=(275, 275),
                                            # sharpness_label=zsharp,
                                            **opts)
        zsizer = wx.GridBagSizer(2, 2)
        zsizer.Add(zlab1,         (0, 0), (1, 1), ALL_EXP|LEFT_TOP, 1)
        zsizer.Add(self.zoomsize, (0, 1), (1, 1), ALL_EXP|LEFT_TOP, 1)
        # zsizer.Add(zlab2,         (1, 0), (1, 1), ALL_EXP|LEFT_TOP, 1)
        # zsizer.Add(zsharp,        (2, 1), (1, 1), ALL_EXP|LEFT_TOP, 1)
        zsizer.Add(self.imgpanel.zoompanel, (1, 0), (1, 2), ALL_EXP|LEFT_TOP, 1)
        zpanel.SetSizer(zsizer)
        zsizer.Fit(zpanel)

        if orientation.lower().startswith('land'):
            size = (1500, 750)
            msizer = wx.GridBagSizer(2, 2)
            msizer.Add(self.ctrlpanel, (0, 0), (1, 1), LEFT_TOP, 1)
            msizer.Add(self.confpanel, (1, 0), (1, 1), LEFT_TOP, 1)
            # msizer.Add((1, 1),         (2, 0), (1, 1), ALL_EXP, 1)
            msizer.Add(zpanel,         (2, 0), (1, 1), LEFT_TOP, 1)
            msizer.Add(self.pospanel,  (0, 1), (5, 1), ALL_EXP, 1)
            self.pospanel.SetMinSize((275, 1000))

            pack(ppanel, msizer)

            sizer = wx.BoxSizer(wx.HORIZONTAL)
            sizer.AddMany([(self.imgpanel,  5, ALL_EXP|LEFT_CEN, 0),
                           (ppanel,     1, ALL_EXP|LEFT_CEN|wx.GROW, 1)])
            pack(self, sizer)

        else: # portrait mode
            size = (900, 1500)
            self.pospanel.SetMinSize((250, 450))
            msizer = wx.GridBagSizer(3, 3)
            msizer.Add(self.ctrlpanel, (0, 0), (1, 1), ALL_EXP|LEFT_TOP, 1)
            msizer.Add(self.pospanel,  (0, 1), (3, 1), ALL_EXP|LEFT_TOP, 2)
            msizer.Add(self.confpanel, (0, 2), (1, 1), ALL_EXP|LEFT_TOP, 1)
            msizer.Add((10, 10),       (1, 2), (1, 1), ALL_EXP, 1)
            msizer.Add(zpanel,         (2, 2), (1, 1), ALL_EXP, 1)
            pack(ppanel, msizer)
            sizer = wx.BoxSizer(wx.VERTICAL)
            sizer.AddMany([(self.imgpanel,  5, ALL_EXP|LEFT_CEN, 0),
                          (ppanel,    1, ALL_EXP|LEFT_CEN|wx.GROW, 1)])
            pack(self, sizer)

        self.imgpanel.confpanel = self.confpanel
        self.SetSize(size)
        self.SetIcon(wx.Icon(get_icon('microscope'), wx.BITMAP_TYPE_ICO))

        ex  = [{'shape':'circle', 'color': (255, 0, 0),
                'width': 1.5, 'args': (0.5, 0.5, 0.007)},
               {'shape':'line', 'color': (200, 100, 0),
                'width': 2.0, 'args': (0.7, 0.97, 0.97, 0.97)}]

        self.create_menus()
        self.Bind(wx.EVT_CLOSE, self.onClose)
        self.init_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.onInitTimer, self.init_timer)
        self.init_timer.Start(1000)

    def onZoomSize(self, event=None):
        cal = min(10, abs(self.cam_calibx))
        self.imgpanel.zoompanel.imgsize = int(self.zoomsize.GetValue()/cal)

    def OnPaneChanged(self, evt=None):
        self.Layout()
        if self.cpanel.IsExpanded():
            self.cpanel.SetLabel('Hide Controls')
        else:
            self.cpanel.SetLabel('Show Controls')
        self.imgpanel.Refresh()


    def onInitTimer(self, event=None, **kws):
        if self.imgpanel.full_size is not None:
            if 'overlays' in self.config:
                img_x, img_y = self.imgpanel.full_size
                pix_x = abs(self.get_calibration()[0])
                try:
                    iscale = 0.5/abs(pix_x * img_x)
                except ZeroDivisionError:
                    iscale = 1.0

                scalebar = circle = None
                for overlay in self.config.get('overlays', []):
                    name  = overlay[0].lower()
                    if name == 'scalebar':
                        scalebar = [float(x) for x in overlay[1:]]
                    elif name == 'circle':
                        circle = [float(x) for x in overlay[1:]]

                dobjs = []
                if scalebar is not None:
                    ssiz, sx, sy, swid, scolr, scolg, scolb = scalebar
                    sargs = [sx - ssiz*iscale, sy, sx + ssiz*iscale, sy]
                    scol = wx.Colour(int(scolr), int(scolg), int(scolb))
                    dobjs.append(dict(shape='Line', width=swid,
                                      style=wx.SOLID, color=scol, args=sargs))

                if circle is not None:
                    csiz, cx, cy, cwid, ccolr, ccolg, ccolb = circle
                    cargs = [cx, cy, csiz*iscale]
                    ccol = wx.Colour(int(ccolr), int(ccolg), int(ccolb))
                    dobjs.append(dict(shape='Circle', width=cwid,
                                      style=wx.SOLID, color=ccol, args=cargs))


                if self.xhair_pixel is not None:
                    xwid, xcolr, xcolg, xcolb = swid, scolr, scolg, scolb
                    xcol = wx.Colour(int(xcolr), int(xcolg), int(xcolb))
                    xcol = wx.Colour(int(20), int(300), int(250))
                    hx = self.xhair_pixel['x']
                    hy = self.xhair_pixel['y']
                    xargs = [hx - ssiz*iscale, hy - ssiz*iscale, hx + ssiz*iscale, hy + ssiz*iscale]

                    dobjs.append(dict(shape='Line', width=2,
                                      style=wx.SOLID, color=xcol, args=xargs))

                self.imgpanel.draw_objects = dobjs
                self.onZoomSize()
            self.init_timer.Stop()

    def onChangeCamera(self, evt=None):
        if not self.cam_type.startswith('area'):
            print('How did that happen?')
            return

        name = self.cam_adpref
        prefix = None
        dlg = wx.TextEntryDialog(self, 'Enter PV for Area Detector',
                                 caption='Enter PV for Area Detector',
                                 defaultValue=name)
        dlg.Raise()
        if dlg.ShowModal() == wx.ID_OK:
            prefix = dlg.GetValue()
        dlg.Destroy()
        if prefix is not None:
            self.imgpanel.set_prefix(prefix)
            self.confpanel.set_prefix(prefix)
            self.cam_adpref = prefix


    def create_menus(self):
        "Create the menubar"
        mbar  = wx.MenuBar()
        fmenu = wx.Menu()
        pmenu = wx.Menu()
        omenu = wx.Menu()
        add_menu(self, fmenu, label="&Read Config", text="Read Configuration",
                 action = self.onReadConfig)

        add_menu(self, fmenu, label="&Save Config", text="Save Configuration",
                 action = self.onSaveConfig)

        # add_menu(self, fmenu, label="Capture Video",
        #         text="Capture Video",
        #         action = self.onCaptureVideo)

        add_menu(self, fmenu, label="Build Composite",
                 text="Build Composite",
                 action = self.onBuildCompositeEvent)

        add_menu(self, fmenu, label="Select &Working Directory\tCtrl+W",
                 text="change Working Folder",
                 action = self.onChangeWorkdir)

        if self.cam_type.startswith('area'):
            add_menu(self, fmenu, label="Change AreaDetector",
                     text="Change Camera to different AreaDetector",
                     action = self.onChangeCamera)

        fmenu.AppendSeparator()
        add_menu(self, fmenu, label="E&xit\tCtrl+x",  text="Quit Program",
                 action = self.onClose)

        add_menu(self, pmenu, label="Export Positions", text="Export Positions",
                 action = self.onExportPositions)
        add_menu(self, pmenu, label="Import Positions", text="Import Positions",
                 action = self.onImportPositions)
        add_menu(self, pmenu, label="Erase Many Positions\tCtrl+E",
                 text="Select Multiple Positions to Erase",
                 action = self.onEraseMany)
        add_menu(self, omenu, label="Image Overlays",
                 text="Setup Image Overlays",
                 action = self.onConfigOverlays)
        add_menu(self, omenu, label="Calibration",
                 text="Setup Image Calibration",
                 action = self.onConfigCalibration)
        vmove  = wx.NewId()
        verase = wx.NewId()
        vreplace = wx.NewId()
        cenfine = wx.NewId()
        self.menu_opts = {vmove: 'v_move', verase: 'v_erase',
                          vreplace: 'v_replace',
                          cenfine: 'centerfine'}

        mitem = omenu.Append(vmove, "Verify Go To ",
                             "Prompt to Verify Moving with 'Go To'",
                             wx.ITEM_CHECK)
        mitem.Check()
        self.Bind(wx.EVT_MENU, self.onMenuOption, mitem)

        mitem = omenu.Append(verase, "Verify Erase",
                     "Prompt to Verify Erasing Positions", wx.ITEM_CHECK)
        mitem.Check()
        self.Bind(wx.EVT_MENU, self.onMenuOption, mitem)

        mitem = omenu.Append(vreplace, "Verify Overwrite",
                     "Prompt to Verify Overwriting Positions",  wx.ITEM_CHECK)
        mitem.Check()
        self.Bind(wx.EVT_MENU, self.onMenuOption, mitem)

        mitem = omenu.Append(cenfine, "Center With Fine Stages",
                     "Bring to Center will move the Fine Stages", wx.ITEM_CHECK)
        mitem.Check(0)
        self.Bind(wx.EVT_MENU, self.onMenuOption, mitem)

        omenu.AppendSeparator()

        for name, panel in self.ctrlpanel.subpanels.items():
            show = 0
            label = 'Enable %s' % name
            mid = wx.NewId()
            self.menu_opts[mid] = label
            for mname, data in self.stages.items():
                if data['group'] == name:
                    show = show + data['show']
            mitem = omenu.Append(mid, label, label, wx.ITEM_CHECK)
            if show > 0 :
                mitem.Check()
            self.Bind(wx.EVT_MENU, partial(self.onShowHide, name=name, panel=panel), mitem)

        mbar.Append(fmenu, '&File')
        mbar.Append(omenu, '&Options')
        mbar.Append(pmenu, 'Positions')
        if 'offline_instrument' in self.config:
            cmenu = wx.Menu()
            add_menu(self, cmenu, label="Copy Positions from Offline Microscope",
                     text="Copy Positions from Offline Microscope",
                     action = self.pospanel.onMicroscopeTransfer)
            cmenu.AppendSeparator()
            add_menu(self, cmenu, label="Calibrate to Offline Microscope",
                     text="Calibrate to Offline Microscope",
                     action = self.pospanel.onMicroscopeCalibrate)
            mbar.Append(cmenu, 'Offline Microscope')

        self.SetMenuBar(mbar)

    def onShowHide(self, event=None, panel=None, name='---'):
        showval = {True:1, False:0}[event.IsChecked()]
        if showval:
            panel.Enable()
        else:
            panel.Disable()

        for mname, data in self.config['stages'].items():
            if data['group'] == name:
                data['show'] = showval

    def onEraseMany(self, evt=None, **kws):
        self.pospanel.onEraseMany(event=evt)
        evt.Skip()

    def onConfigOverlays(self, evt=None, **kws):
        shown = False
        if self.overlayframe is not None:
            try:
                self.overlayframe.Raise()
                shown = True
            except:
                del self.overlayframe
        if not shown:
            self.overlayframe = OverlayFrame(calib=self.get_calibration(),
                                             config=self.config,
                                             callback=self.onSetOverlays)


    def onSetOverlays(self, overlays=None):
        if overlays is not None:
            self.config['overlays'] = overlays
        overlays = self.config['overlays']
        imgx, imgy = self.imgpanel.full_size
        calib = self.get_calibration()
        iscale = 0.5/abs(calib[0] * imgx)

        if overlays[0][0].startswith('circ'):
            circ, sbar = overlays[0], overlays[1]
        else:
            circ, sbar = overlays[1], overlays[0]

        cname, csiz, cx, cy, cwid, ccolr, ccolg, ccolb = circ
        ccol = [ccolr, ccolg, ccolb]
        cargs = [cx, cy, csiz*iscale]

        sname, ssiz, sx, sy, swid, scolr, scolg, scolb = sbar
        scol = [scolr, scolg, scolb]
        sargs = [sx - ssiz*iscale, sy, sx + ssiz*iscale, sy]
        dobjs = [dict(shape='Line', width=swid,
                      style=wx.SOLID, color=scol, args=sargs),
                 dict(shape='Circle', width=cwid,
                      style=wx.SOLID, color=ccol, args=cargs)]
        self.imgpanel.draw_objects = dobjs

    def onConfigCalibration(self, evt=None, **kws):
        shown = False
        if self.calibframe is not None:
            try:
                self.calibframe.Raise()
                shown = True
            except:
                del self.calibframe
        if not shown:
            self.calibframe = CalibrationFrame(self.calibrations,
                                               self.calib_current,
                                               callback=self.onSetCalibration)

    def onSetCalibration(self, calibrations, current):

        self.calibrations = calibrations
        self.calib_current = current

        self.config['calibration'] = []
        for cname, cval in calibrations.items():
            self.config['calibration'].append([cname, "%.4f" % cval[0], "%.4f" % cval[1]])
        self.confpanel.calib.Clear()
        for cname in calibrations:
            self.confpanel.calib.Append(cname)
        self.confpanel.calibrations = calibrations
        self.confpanel.calib.SetStringSelection(current)
        self.get_calibration()
        self.onSetOverlays()

    def onMenuOption(self, evt=None):
        """events for options menu: move, erase, overwrite """
        setattr(self, self.menu_opts[evt.GetId()], evt.IsChecked())

    def read_config(self, fname=None):
        "read config file"
        self.configfile = MicroscopeConfig(fname=fname)
        cnf = self.config = self.configfile.config

        self.orientation = cnf.get('orientation', 'landscape')
        self.title       = cnf.get('title', 'Microscope')

        self.v_move      = cnf.get('verify_move', True)
        self.v_erase     = cnf.get('verify_erase', True)
        self.v_replace   = cnf.get('verify_overwrite', True)
        self.centerfine  = cnf.get('center_with_fine_stages', False)
        self.imgdir      = cnf.get('image_folder', 'Sample_Images')
        self.cam_type    = cnf.get('camera_type', 'areadetector').lower()
        self.cam_id      = cnf.get('camera_id', 0)
        self.cam_adpref  = cnf.get('ad_prefix', '')
        self.cam_adform  = cnf.get('ad_format', 'JPEG')
        self.cam_weburl  = cnf.get('web_url', 'http://xxx/image.jpg')
        self.cam_pubtype = cnf.get('publish_type', 'None')
        self.cam_pubaddr = cnf.get('publish_addr', '164.54.160.93')
        self.cam_pubport = cnf.get('publish_port', '17166')
        self.cam_pubdelay = float(cnf.get('publish_delay', '0.25'))
        self.calibrations = {}
        self.calib_current = None
        calibs = cnf.get('calibration', [])
        if len(calibs) == 0:
            calibs.append(['10 um pixels', 0.01, 0.01])
        for cname, calx, caly in calibs:
            self.calibrations[cname] = (float(calx), float(caly))
            if self.calib_current is None:
                self.calib_current = cname

        self.get_calibration()
        self.lamp = None
        lamp = cnf.get('lamp', None)
        if lamp is not None:
            ctrlpv = lamp.get('ctrlpv', None)
            minval = lamp.get('minval', 0.0)
            maxval = lamp.get('maxval', 5.0)
            step   = lamp.get('step', 0.25)
            self.lamp = dict(ctrlpv=ctrlpv, minval=minval, maxval=maxval, step=step)
        try:
            pref = self.imgdir.split('_')[0]
        except:
            pref = 'Sample'
        self.htmllog = '%sStage.html' % pref
        if not os.path.exists(self.imgdir):
            os.makedirs(self.imgdir)
        if not os.path.exists(self.htmllog):
            self.begin_htmllog()

        self.stages = {}
        self.stage_groups = []
        for _dat in cnf.get('stages', []):
            name, group, desc, scale, prec, maxstep, show = _dat
            self.stages[name] = dict(label=name, group=group, desc=desc,
                                    scale=scale, prec=prec, maxstep=maxstep,
                                    show=show)
            if group not in self.stage_groups:
                self.stage_groups.append(group)
                
    def get_calibration(self, name=None):
        if name is None:
            name = self.calib_current
        if name in self.calibrations:
            self.current_calib = name

        cal = self.calibrations[name]
        self.cam_calibx = abs(float(cal[0]))
        self.cam_caliby = abs(float(cal[0]))
        return cal

    def begin_htmllog(self):
        "initialize log file"
        fout = open(self.htmllog, 'w')
        fout.write(self.html_header)
        fout.close()

    def save_image(self, fname):
        "save image to file"
        imgdata = self.imgpanel.SaveImage(fname)
        if imgdata is None:
            self.write_message('could not save image to %s' % fname)
        else:
            self.write_message('saved image to %s' % fname)
        return imgdata

    def write_htmllog(self, name=None, thispos=None):
        img_folder = self.imgdir
        junk, img_file = os.path.split(thispos['image'])
        imgfile = os.path.join(img_folder, img_file)

        txt = ["<hr>", "<table><tr><td><a href='{imgfile:s}'> <img src='{imgfile:s}' width=350></a></td>"]

        if len(thispos.get('image2', '')) > 0:
            junk, img2file = os.path.split(thispos['image2'])
            img2file = os.path.join(img_folder, img2file)

            txt.append("<td><a href='{img2file:s}'> <img src='{img2file:s}' width=350></a></td>")
        txt.append("<td><table><tr><td>Position:</td><td>{position:s}</td><td>{tstamp:s}</td></tr>")
        txt.append("<tr><td>Motor Name</td><td>PV Name</td><td>Value</td></tr>")


        pos_fmt ="    <tr><td> %s </td><td> %s </td><td>   %f</td></tr>"
        for pvname, value in thispos['position'].items():
            desc = self.stages.get(pvname).get('desc', pvname)
            txt.append(pos_fmt % (desc, pvname, value))

        txt.append("</table></td></tr></table>")
        txt.append("")
        txt = '\n'.join(txt)
        fout = open(self.htmllog, 'a')

        fout.write(txt.format(imgfile=imgfile, img2file=img2file, position=name,
                              tstamp=thispos['timestamp']))
        fout.close()


    def save_videocam(self):
        out = ''
        if HAS_CV2 and self.videocam is not None:
            cam = cv2.VideoCapture(self.videocam.strip())

            imgfile = '%s_hutch.jpg' % time.strftime('%b%d_%H%M%S')
            fullpath = os.path.join(os.getcwd(), self.imgdir, imgfile)
            status, image = cam.read()
            if status:
                cv2.imwrite(fullpath, image)
                out = fullpath
            cam.release()
        return out

    def write_message(self, msg='', index=0):
        "write to status bar"
        self.statusbar.SetStatusText(msg, index)

    def write_framerate(self, msg):
        "write to status bar"
        self.statusbar.SetStatusText(msg, 1)

    def onShowCrosshair(self, event=None, show=True, **kws):
        self.xhair_pixel = None
        if show:
            self.xhair_pixel = self.last_pixel

    def onAFTimer(self, event=None, **kws):
        if self.af_done:
            self.af_thread.join()
            self.af_timer.Stop()
            if self.ctrlpanel.af_message is not None:
                self.ctrlpanel.af_message.SetLabel('')
            self.ctrlpanel.af_button.Enable()

    def onAutoFocus(self, event=None, **kws):
        self.af_done = False
        self.ctrlpanel.af_button.Disable()
        self.af_thread = Thread(target=self.do_autofocus)
        self.af_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.onAFTimer, self.af_timer)
        self.af_timer.Start(2000)
        self.af_thread.start()

    def do_autofocus(self):
        report = None
        if self.ctrlpanel.af_message is not None:
            report = self.ctrlpanel.af_message.SetLabel
        if report is not None:
            report('Auto-setting exposure')
        expdat = self.imgpanel.GetExposureGain()
        self.imgpanel.AutoSetExposureTime()
        report('Auto-focussing start')

        def make_fibs(max=3000):
            f = [1., 1.]
            i = 0
            while True:
                val = f[i] + f[i+1]
                if val > max:
                    break
                f.append(val)
                i += 1
            return f

        zstage = self.ctrlpanel.motors['z']._pvs['VAL']

        start_pos = zstage.get()
        focus_data = []

        def get_score(pos):
            zpos = start_pos + pos * 0.001
            zstage.put(zpos, wait=True)
            time.sleep(0.05)
            score = image_blurriness(self.imgpanel)
            dat = (pos, zstage.get(), score)
            focus_data.append(dat)
            return score

        # step 1: take up to 15 steps of 250 microns
        # while score is still improving
        report('Auto-focussing finding rough focus')
        scores = []
        NMAX = 15
        step = 250.0
        score0 = get_score(0)
        scorep = get_score(step)
        scorem = get_score(-step)
        sign = None
        best = 0.0
        if scorem < score0:
            score0 = scorem
            sign = -1.0
        elif scorep < score0:
            score0 = scorep
            sign = 1.0

        if sign is not None:
            i = 1
            while i < NMAX:
                i=i+1
                tmp = sign*step*(i+1)
                score = get_score(tmp)
                if score > score0:
                    break
                score0, best = score, tmp
        zstage.put(start_pos + best * 0.001, wait=True)

        # now refine
        start_pos = zstage.get()
        report('Auto-focussing refining focus')
        start, stop = -300, 300
        fibs = make_fibs(max=abs(stop-start))
        nfibs = len(fibs)
        step = fibs[nfibs-3] / fibs[nfibs-1]
        best = (start+stop)/2
        z1, z2 = int(start + step*(stop-start)), int(stop - step*(stop-start))
        score1, score2 = get_score(z1), get_score(z2)
        for i in range(nfibs-2):
            step = fibs[nfibs-i-3] / fibs[nfibs-i-1]
            report("Auto-focussing refining focus %i " %(i+1))
            if score1 > score2:
                start = z1
                best = int(stop - step*(stop-start))
                z1, z2 = z2, best
                score1, score2 = score2, get_score(best)
            else:
                stop = z2
                best = int(start + step*(stop-start))
                z1, z2 = best, z1
                score1, score2 = get_score(best), score1
            if abs(z1-z2) < 2:
                break

        get_score(best)
        report('Auto-focussing done. ')
        self.imgpanel.SetExposureGain(expdat)
        self.ctrlpanel.af_button.Enable()

    def onMoveToCenter(self, event=None, **kws):
        "bring last pixel to image center"
        p = self.last_pixel
        if p is None:
            return

        cal_x, cal_y = self.get_calibration()
        dx = 0.001*cal_x*(p['x']-p['xmax']/2.0)
        dy = 0.001*cal_y*(p['y']-p['ymax']/2.0)

        mots = self.ctrlpanel.motors

        xmotor, ymotor = 'x', 'y'
        if self.centerfine and 'finex' in mots:
            xmotor, ymotor = 'finex', 'finey'

        xscale, yscale = 1.0, 1.0
        for stage_info in self.stages.values():
            if stage_info['desc'].lower() == xmotor:
                xscale = stage_info['scale']
            if stage_info['desc'].lower() == ymotor:
                yscale = stage_info['scale']
        mots[xmotor].VAL += dx*xscale
        mots[ymotor].VAL += dy*yscale
        self.onSelectPixel(p['xmax']/2.0, p['ymax']/2.0,
                           xmax=p['xmax'], ymax=p['ymax'])

        zoompanel = getattr(self.imgpanel, 'zoompanel', None)
        if zoompanel is not None:
            mx, my = self.imgpanel.full_size
            zoompanel.xcen = int(mx/2.0)
            zoompanel.ycen = int(my/2.0)
            zoompanel.Refresh()

    def onSelectPixel(self, x, y, xmax=100, ymax=100):
        " select a pixel from image "
        self.last_pixel = dict(x=x, y=y, xmax=xmax, ymax=ymax)
        cal_x, cal_y = self.get_calibration()
        self.confpanel.on_selected_pixel(x, y, xmax, ymax,
                                         cam_calibx=cal_x,
                                         cam_caliby=cal_y)

    def onPixelMotion(self, x, y, xmax=100, ymax=100):
        " select a pixel from image "
        fmt  = """Pixel=(%i, %i) (%.1f, %.1f)um from center, (%.1f, %.1f)um from selected"""
        if x > 0 and x < xmax and y > 0 and y < ymax:
            dx = abs(self.cam_calibx*(x-xmax/2.0))
            dy = abs(self.cam_caliby*(y-ymax/2.0))
            ux, uy = 0, 0
            if self.last_pixel is not None:
                lastx = self.last_pixel['x']
                lasty = self.last_pixel['y']
                ux = abs(self.cam_calibx*(x-lastx))
                uy = abs(self.cam_caliby*(y-lasty))

            pix_msg = fmt % (x, y, dx, dy, ux, uy)
            self.write_message(pix_msg)

            if not self.confpanel.img_size_shown:
                self.confpanel.img_size.SetLabel("(%i, %i)" % (xmax, ymax))
                self.confpanel.img_size_shown = True

    def onClose(self, event=None):
        if wx.ID_YES == Popup(self, "Really Quit?", "Exit Sample Stage?",
                              style=wx.YES_NO|wx.NO_DEFAULT|wx.ICON_QUESTION):

            self.config['workdir'] = os.path.abspath(os.getcwd())
            self.configfile.write(config=self.config)
            self.imgpanel.Stop()
            publisher = getattr(self.imgpanel, 'publisher', None)
            if publisher is not None:
                publisher.stop()
            time.sleep(1)
            pub_thread = getattr(self.imgpanel, 'pub_thread', None)
            if pub_thread is not None:
                del pub_thread

            try:
                self.overlayframe.Destroy()
            except:
                pass




            self.Destroy()

    def onExportPositions(self, event=None):
        curpath = os.getcwd()
        fname = FileSave(self, 'Export Positions File',
                         wildcard='Position Files (*.pos)|*.pos|All files (*.*)|*.*',
                         default_file='Save.pos')
        if fname is not None:
            self.pospanel.SavePositions(fname)

        self.write_message('Saved Positions File %s' % fname)
        os.chdir(curpath)

    def onImportPositions(self, event=None):
        curpath = os.getcwd()
        fname = FileOpen(self, 'Import Positions File',
                         wildcard='Position Files (*.pos)|*.pos|All files (*.*)|*.*',
                         default_file='Save.pos')
        if fname is not None:
            self.pospanel.LoadPositions(fname)

        self.write_message('Loaded Positions from File %s' % fname)
        os.chdir(curpath)

    def onChangeWorkdir(self, event=None):
        ret = SelectWorkdir(self)
        if ret is None:
            return
        os.chdir(ret)
        self.imgdir = self.config.get('image_folder', 'Sample_Images')
        if not os.path.exists(self.imgdir):
            os.makedirs(self.imgdir)
        if not os.path.exists(self.htmllog):
            self.begin_htmllog()

    def onCaptureVideo(self, event=None):
        self.imgpanel.camera.StopCapture()
        t0 = time.time()
        dlg = VideoDialog(self, 'Capture.mjpg')
        res = dlg.GetResponse()
        dlg.Destroy()
        if res.ok:
            self.imgpanel.CaptureVideo(filename=res.filename, runtime=res.runtime)

    def onBuildCompositeEvent(self, event=None):
        t0 = time.time()
        dlg = CompositeDialog(self)
        cur_pos_name = self.pospanel.pos_name.GetValue()
        comp_name = fix_filename("%s_Composite" % (cur_pos_name))
        dlg.filename.SetValue(comp_name)
        res = dlg.GetResponse()
        dlg.Destroy()
        if res.ok:
            wx.CallAfter(self.onBuildComposite, res)

    def onCompositeTimer(self, event=None, **kws):
        if self.composite_done:
            self.composite_thread.join()
            self.composite_timer.Stop()
            print("composite done!")

    def onBuildComposite(self, res):
        self.composite_done = False
        self.composite_fname = res.filename
        self.composite_size = res.size
        self.composite_cal = res.cal
        self.composite_thread = Thread(target=self.build_composite)
        self.composite_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.onCompositeTimer, self.composite_timer)
        self.composite_timer.Start(1000)
        self.composite_thread.start()

    def build_composite(self, **kws):
        cal = self.composite_cal
        size = self.composite_size
        fname = self.composite_fname.strip()
        if cal is None:
            cal = [x for x in self.calibrations[self.calib_current]]

        compdir = os.path.abspath(os.path.join(self.imgdir, fname))
        if not os.path.exists(compdir):
            os.makedirs(compdir)

        print("==Build Composite ", size, cal, fname)
        t0 = time.monotonic()
        image = self.imgpanel.GrabNumpyImage()
        nx, ny = image.shape[0], image.shape[1]
        xstep = 1.250*cal[0]
        ystep = 1.250*cal[1]

        nrows = int(1+size/abs(xstep))
        xstage = self.ctrlpanel.motors['x']._pvs['VAL']
        ystage = self.ctrlpanel.motors['y']._pvs['VAL']
        xcen = xstage.get()
        ycen = ystage.get()

        xvals = np.linspace(xcen-nrows*xstep/2, xcen+nrows*xstep/2, nrows)
        yvals = np.linspace(ycen-nrows*ystep/2, ycen+nrows*ystep/2, nrows)

        print("==Composite ", nx, ny, nrows,  xstep, nrows*xstep)
        print("==Composite X ", xvals[:3])
        print("==Composity Y ", yvals[:3])

        xstage.put(xvals[0])
        ystage.put(yvals[0])

        n = 0
        tsave = 0.
        outbuff = ['# using calibration: %.5f, %.5f' % (cal[0], cal[1]),
                   '# Files are named imgIY_IX.jpg',
                   '# IY   IX     Y      X']

        for iy in range(nrows):
            print(iy)
            xstage.put(xvals[0])
            ystage.put(yvals[iy], wait=True)
            for ix in range(nrows):
                xstage.put(xvals[ix], wait=True)
                time.sleep(0.25)
                n += 1
                fname = os.path.join(compdir, 'img%d_%d_dat.npy' % (iy, ix))
                tx = time.monotonic()
                # self.imgpanel.SaveImage(fname)
                img = None
                for _x in range(10):
                    try:
                        img = self.imgpanel.GrabNumpyImage()
                    except:
                        time.sleep(0.1)
                    if img is not None:
                        break
                if img is None:
                    print("grabbing image failed... aborting!")
                    break

                np.save(fname, img)
                tsave += (time.monotonic() -tx)
                outbuff.append('%d %d %15.4f  %15.4f' % (iy, ix, yvals[iy], xvals[ix]))
                # images.append(thisim)
        outbuff.append('')
        fout = os.path.join(compdir, 'composite.txt')
        with open(fout, 'w') as fh:
            fh.write('\n'.join(outbuff))

        print("Grabbed %d images in %.1f seconds, %.1f saving"  % (n, time.monotonic()-t0, tsave))
        xstage.put(xcen)
        ystage.put(ycen)
        self.composite_done = True

    def onSaveConfig(self, event=None):
        fname = FileSave(self, 'Save Configuration File',
                         wildcard='Config files (*.yaml)|*.yaml|All files (*.*)|*.*',
                         default_file='microscope.yaml')
        if fname is not None:
            self.configfile.save(fname=fname)
        self.write_message('Saved Configuration File %s' % fname)

    def onReadConfig(self, event=None):
        curpath = os.getcwd()
        fname = FileOpen(self, 'Read Configuration File',
                         wildcard='yaml (*.yaml)|*.yaml|All files (*.*)|*.*',
                         default_file='microscope.yaml')
        if fname is not None:
            self.read_config(fname)
            self.connect_motors()
        self.write_message('Read Configuration File %s' % fname)
        os.chdir(curpath)

class MicroscopeApp(wx.App, wx.lib.mixins.inspection.InspectionMixin):
    def __init__(self, configfile=None, prompt=True, debug=False, **kws):
        self.configfile = configfile
        self.prompt = prompt
        self.debug = debug
        wx.App.__init__(self, **kws)

    def createApp(self):
        self.frame = MicroscopeFrame(configfile=self.configfile,
                                     prompt=self.prompt)
        self.frame.Show()
        self.SetTopWindow(self.frame)

    def OnInit(self):
        self.createApp()
        if self.debug:
            self.ShowInspectionTool()
        return True
