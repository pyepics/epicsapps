#!/usr/bin/env python
"""
   Display Application for Epics AreaDetector
(in /lib)
"""
import os
import sys
import time
import wx
from wx._core import PyDeadObjectError

import numpy as np
import Image

from wxmplot.plotframe import PlotFrame
ICON_FILE = 'camera.ico'

from debugtime import debugtime
os.environ['EPICS_CA_MAX_ARRAY_BYTES'] = '16777216'

class Empty:
    pass

import epics
from epics.wx import (DelayedEpicsCallback, EpicsFunction, Closure,
                      PVEnumChoice, PVFloatCtrl, PVFloatSpin)
from epics.wx.utils import add_menu

from imageview import ImageView

class AD_Display(wx.Frame):
    """AreaDetector Display """
    img_attrs = ('ArrayData', 'UniqueId_RBV', 'NDimensions_RBV',
                 'ArraySize0_RBV', 'ArraySize1_RBV', 'ArraySize2_RBV',
                 'ColorMode_RBV')

    cam_attrs = ('Acquire', 'ArrayCounter', 'ArrayCounter_RBV',
                 'DetectorState_RBV',  'NumImages', 'ColorMode',
                 'DataType_RBV',  'Gain',
                 'AcquireTime', 'AcquirePeriod', 'ImageMode',
                 'MaxSizeX_RBV', 'MaxSizeY_RBV', 'TriggerMode',
                 'SizeX', 'SizeY', 'MinX', 'MinY')
    
    # plugins to enable
    enabled_plugins = ('image1', 'Over1', 'ROI1', 'JPEG1', 'TIFF1')
    
    stat_msg = 'Read %.1f%% of images: rate=%.1f frames/sec'
    
    def __init__(self, prefix=None, app=None, scale=1.0, approx_height=1200):
        self.app = app
        self.ad_img = None
        self.ad_cam = None
        self.imgcount = 0
        self.prefix = prefix
        self.fname = 'AD_Image.tiff'
        self.scale  = scale
        self.arrsize  = [0,0,0]
        self.imbuff = None
        self.d_size = None
        self.im_size = None
        self.colormode = 0
        self.last_update = 0.0
        self.n_img   = 0
        self.imgcount_start = 0
        self.n_drawn = 0
        self.img_id = 0
        self.starttime = time.time()
        self.drawing = False
        self.lineplotter = None
        self.zoom_lims = []

        wx.Frame.__init__(self, None, -1, "Epics Area Detector Display",
                          style=wx.DEFAULT_FRAME_STYLE)

        if self.prefix is None:
            self.GetPVName()
            
        self.img_w = 0
        self.img_h = 0
        self.wximage = wx.EmptyImage(1024, 1360) # 1360, 1024) # approx_height, 1.5*approx_height)
        self.buildMenus()
        self.buildFrame()

    def OnLeftUp(self, event):
        if self.image is not None:
            self.image.OnLeftUp(event)

    def GetPVName(self, event=None):
        dlg = wx.TextEntryDialog(self, 'Enter PV for Area Detector',
                                       'Enter PV for Area Detector', '')
        dlg.Raise()
        if dlg.ShowModal() == wx.ID_OK:
            self.prefix = dlg.GetValue()
            wx.CallAfter(self.connect_pvs )
        dlg.Destroy()

    def onCopyImage(self, event=None):
        "copy bitmap of canvas to system clipboard"
        bmp = wx.BitmapDataObject()
        bmp.SetBitmap(wx.BitmapFromImage(self.wximage))
        wx.TheClipboard.Open()
        wx.TheClipboard.SetData(bmp)
        wx.TheClipboard.Close()
        wx.TheClipboard.Flush()

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

        dlg.Destroy()
        if path is not None and self.data is not None:
            Image.frombuffer(self.im_mode, self.im_size, self.data.flatten(),
                             'raw', self.im_mode, 0, 1).save(path)

    def onExit(self, event=None):
        # self.ad_cam.Acquire = 0
        try:
            wx.Yield()
        except:
            pass
        self.ad_cam.Acquire = 0
        self.Destroy()

    def onAbout(self, event=None):
        msg =  """Epics Image Display version 0.2

http://pyepics.github.com/epicsapps/

Matt Newville <newville@cars.uchicago.edu>"""

        dlg = wx.MessageDialog(self, msg, "About Epics Image Display",
                               wx.OK | wx.ICON_INFORMATION)
        dlg.ShowModal()
        dlg.Destroy()

    def buildMenus(self):
        fmenu = wx.Menu()
        add_menu(self, fmenu, "&Connect to PV\tCtrl+O", "Connect to PV", self.GetPVName)
        add_menu(self, fmenu, "&Save\tCtrl+S", "Save Image", self.onSaveImage)
        add_menu(self, fmenu, "&Copy\tCtrl+C", "Copy Image to Clipboard", self.onCopyImage)
        fmenu.AppendSeparator()
        add_menu(self, fmenu, "E&xit\tCtrl+Q",  "Exit Program", self.onExit)

        omenu = wx.Menu()
        add_menu(self, omenu, "&Zoom out\tCtrl+Z", "Zoom Out", self.unZoom)
        add_menu(self, omenu, "Reset Image Counter", "Set Image Counter to 0", self.onResetImageCounter)
        omenu.AppendSeparator()
        add_menu(self, omenu,  "&Rotate Clockwise\tCtrl+R", "Rotate Clockwise", self.onRotCW)
        add_menu(self, omenu,  "Rotate CounterClockwise", "Rotate Counter Clockwise", self.onRotCCW)
        add_menu(self, omenu,  "Flip Up/Down\tCtrl+T", "Flip Up/Down", self.onFlipV)
        add_menu(self, omenu,  "Flip Left/Right\tCtrl+F", "Flip Left/Right", self.onFlipH)
        omenu.AppendSeparator()

        self.CM_ZOOM = wx.NewId()
        self.CM_SHOW = wx.NewId()
        self.CM_PROF = wx.NewId()
        omenu.Append(self.CM_ZOOM, "Cursor Mode: Zoom to Box\tCtrl+B" ,
                     "Zoom to box by clicking and dragging", wx.ITEM_RADIO)
        omenu.Append(self.CM_SHOW, "Cursor Mode: Show X,Y\tCtrl+X",
                     "Show X,Y, Intensity Values",  wx.ITEM_RADIO)
        omenu.Append(self.CM_PROF, "Cursor Mode: Line Profile\tCtrl+L",
                     "Show Line Profile",  wx.ITEM_RADIO)
        self.Bind(wx.EVT_MENU, self.onCursorMode,  id=self.CM_ZOOM)
        self.Bind(wx.EVT_MENU, self.onCursorMode,  id=self.CM_PROF)
        self.Bind(wx.EVT_MENU, self.onCursorMode,  id=self.CM_SHOW)

        hmenu = wx.Menu()
        add_menu(self, hmenu, "About", "About Epics AreadDetector Display", self.onAbout)

        mbar = wx.MenuBar()
        mbar.Append(fmenu, "File")
        mbar.Append(omenu, "Options")
        mbar.Append(hmenu, "&Help")
        self.SetMenuBar(mbar)

    def onCursorMode(self, event=None):
        if event.Id == self.CM_ZOOM:
            self.image.cursor_mode = 'zoom'
        elif event.Id == self.CM_PROF:
            self.image.cursor_mode = 'profile'
        elif event.Id == self.CM_SHOW:
            self.image.cursor_mode = 'show'

    @DelayedEpicsCallback
    def onResetImageCounter(self, event=None):
        self.ad_cam.ArrayCounter = 0
            
    def onRotCW(self, event):
        self.image.rot90 = (self.image.rot90 + 1) % 4
        self.image.Refresh()

    def onRotCCW(self, event):
        self.image.rot90 = (self.image.rot90 - 1) % 4
        self.image.Refresh()

    def onFlipV(self, event):
        self.image.flipv= not self.image.flipv
        self.image.Refresh()

    def onFlipH(self, event):
        self.image.fliph = not self.image.fliph
        self.image.Refresh()

    def buildFrame(self):
        sbar = self.CreateStatusBar(3, wx.CAPTION|wx.THICK_FRAME)
        sfont = sbar.GetFont()
        sfont.SetWeight(wx.BOLD)
        sfont.SetPointSize(10)
        sbar.SetFont(sfont)

        self.SetStatusWidths([-3, -1, -1])
        self.SetStatusText('',0)

        sizer = wx.GridBagSizer(10, 4)
        panel = wx.Panel(self)
        self.panel = panel
        labstyle = wx.ALIGN_LEFT|wx.ALIGN_BOTTOM|wx.EXPAND
        ctrlstyle = wx.ALIGN_LEFT|wx.ALIGN_BOTTOM

        rlabstyle = wx.ALIGN_RIGHT|wx.RIGHT|wx.TOP|wx.EXPAND

        txtstyle=wx.ALIGN_LEFT|wx.ST_NO_AUTORESIZE|wx.TE_PROCESS_ENTER
        self.wids = {}
        self.wids['exptime']   = PVFloatCtrl(panel, pv=None, size=(100, -1))
        self.wids['period']    = PVFloatCtrl(panel, pv=None, size=(100, -1))
        self.wids['numimages'] = PVFloatCtrl(panel, pv=None, size=(100, -1))
        self.wids['gain']      = PVFloatCtrl(panel, pv=None, size=(100, -1),
                                             minval=0, maxval=20, precision=1)
        
        self.wids['imagemode']   = PVEnumChoice(panel, pv=None, size=(100, -1))
        self.wids['triggermode'] = PVEnumChoice(panel, pv=None, size=(100, -1))
        self.wids['color']       = PVEnumChoice(panel, pv=None, size=(100, -1))
        self.wids['start']       = wx.Button(panel, -1, label='Start', size=(50, -1))
        self.wids['stop']        = wx.Button(panel, -1, label='Stop', size=(50,  -1))


        for key in ('start', 'stop'):
            self.wids[key].Bind(wx.EVT_BUTTON, Closure(self.onEntry, key=key))

        self.wids['zoomsize']= wx.StaticText(panel, -1,  size=(250,-1), style=txtstyle)
        self.wids['fullsize']= wx.StaticText(panel, -1,  size=(250,-1), style=txtstyle)

        def txt(label, size=100):
            return wx.StaticText(panel, label=label, size=(size, -1), style=labstyle)

        sizer.Add(txt(' '),                 (0, 0), (1, 1), labstyle)
        sizer.Add(txt('Image Mode '),       (1, 0), (1, 1), labstyle)
        sizer.Add(self.wids['imagemode'],   (1, 1), (1, 2), ctrlstyle)

        sizer.Add(txt('# Images '),         (2, 0), (1, 1), labstyle)
        sizer.Add(self.wids['numimages'],   (2, 1), (1, 2), ctrlstyle)

        sizer.Add(txt('Trigger Mode '),     (3, 0), (1, 1), labstyle)
        sizer.Add(self.wids['triggermode'], (3, 1), (1, 2), ctrlstyle)

        sizer.Add(txt('Period '),           (4, 0), (1, 1), labstyle)
        sizer.Add(self.wids['period'],      (4, 1), (1, 2), ctrlstyle)

        sizer.Add(txt('Exposure Time '),    (5, 0), (1, 1), labstyle)
        sizer.Add(self.wids['exptime'],     (5, 1), (1, 2), ctrlstyle)

        sizer.Add(txt('Gain '),             (6, 0), (1, 1), labstyle)
        sizer.Add(self.wids['gain'],        (6, 1), (1, 2), ctrlstyle)

        sizer.Add(txt('Color Mode'),        (7, 0), (1, 1), labstyle)
        sizer.Add(self.wids['color'],       (7, 1), (1, 2), ctrlstyle)

        sizer.Add(txt('Acquire '),          (9, 0), (1, 1), labstyle)

        sizer.Add(self.wids['start'],       (9, 1), (1, 1), ctrlstyle)
        sizer.Add(self.wids['stop'],        (9, 2), (1, 1), ctrlstyle)

        sizer.Add(self.wids['fullsize'],    (12, 0), (1, 3), labstyle)
        sizer.Add(self.wids['zoomsize'],    (13, 0), (1, 3), labstyle)

        self.image = ImageView(self, size=(1360, 1024), onzoom=self.onZoom,
                               onprofile=self.onProfile, onshow=self.onShowXY)

        panel.SetSizer(sizer)
        sizer.Fit(panel)

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

        self.RefreshImage()
        wx.CallAfter(self.connect_pvs )

    def messag(self, s, panel=0):
        """write a message to the Status Bar"""
        wx.CallAfter(Closure(self.SetStatusText, text=s, number=panel))
        # self.SetStatusText(s, panel)

    @EpicsFunction
    def unZoom(self, event=None, full=False):
        if self.zoom_lims is None or full:
            self.zoom_lims = []

        if len(self.zoom_lims) == 0:
            xmin, ymin = 0, 0
            width  = self.ad_cam.MaxSizeX_RBV
            height = self.ad_cam.MaxSizeY_RBV
            self.zoom_lims = []
        else:
            xmin, ymin, width, height = self.zoom_lims.pop()
            if (self.ad_cam.MinX == xmin and
                self.ad_cam.MinY == ymin and
                self.ad_cam.SizeX == width and
                self.ad_cam.SizeY == height):
                try:
                    xmin, ymin, width, height = self.zoom_lims.pop()
                except:
                    xmin, ymin = 0, 0
                    width = self.ad_cam.MaxSizeX_RBV
                    height = self.ad_cam.MaxSizeY_RBV


        self.ad_cam.MinX  = xmin
        self.ad_cam.MinY  = ymin
        self.ad_cam.SizeX = width
        self.ad_cam.SizeY = height
        self.zoom_lims.append((xmin, ymin, width, height))
        time.sleep(0.05)
        self.showZoomsize()
        if self.ad_cam.Acquire == 0 and self.im_size is not None:
            self.img_w = width
            self.img_h = height
            if self.colormode == 2:
                self.data.shape = [self.im_size[1], self.im_size[0], 3]
                zdata = self.data[ymin:ymin+height, xmin:xmin+width,:]
            else:
                self.data.shape = self.im_size[1], self.im_size[0]
                zdata = self.data[ymin:ymin+height,xmin:xmin+width]
            self.data = zdata #self.data.flatten()
            self.im_size = (width, height)
            # print zdata.shape, width, height, self.im_mode
            self.DatatoImage()   # zdata, (width, height), self.im_mode)

        self.RefreshImage()
        self.image.Refresh()
        
    @EpicsFunction
    def showZoomsize(self):
        try:
            msg  = 'Showing:  %i x %i pixels' % (self.ad_cam.SizeX, self.ad_cam.SizeY)
            self.wids['zoomsize'].SetLabel(msg)
        except:
            pass

    @EpicsFunction
    def onZoom(self, x0, y0, x1, y1):
        width  = self.ad_cam.SizeX
        height = self.ad_cam.SizeY
        xmin   = max(0, int(self.ad_cam.MinX  + x0 * width))
        ymin   = max(0, int(self.ad_cam.MinY  + y0 * height))

        width  = int(x1 * width)
        height = int(y1 * height)
        if width < 2 or height < 2:
            return
        self.ad_cam.MinX = xmin
        self.ad_cam.MinY = ymin
        self.ad_cam.SizeX = width
        self.ad_cam.SizeY = height
        if self.zoom_lims is None:
            self.zoom_lims = []
        self.zoom_lims.append((xmin, ymin, width, height))

        time.sleep(0.05)
        self.showZoomsize()

        if self.ad_cam.Acquire == 0:
            self.img_w = width
            self.img_h = height
            if self.colormode == 2:
                self.data.shape = [self.im_size[1], self.im_size[0], 3]
                zdata = self.data[ymin:ymin+height, xmin:xmin+width,:]
            else:
                self.data.shape = self.im_size[1], self.im_size[0]
                zdata = self.data[ymin:ymin+height,xmin:xmin+width]
            self.data = zdata #. flatten()
            self.im_size = (width, height)
            self.DatatoImage()
        self.image.Refresh()
        
    def DatatoImage(self):  #,  data, size, mode):
        """convert raw data to image"""
        #x = debugtime()

        width, height = self.im_size
        d_size = (int(width*self.scale), int(height*self.scale))
        data = self.data.flatten()
        #x.add('flatten')
        if self.imbuff is None or d_size != self.d_size or self.im_mode == 'L':
            try:
                self.imbuff =  Image.frombuffer(self.im_mode, self.im_size, data,
                                                'raw',  self.im_mode, 0, 1)
                #x.add('made image')
            except:
                return
        self.d_size = d_size = (int(width*self.scale), int(height*self.scale))
        if self.imbuff.size != d_size:
            self.imbuff = self.imbuff.resize(d_size)
            #x.add('resized imbuff')

        if self.wximage.GetSize() != self.imbuff.size:
            self.wximage = wx.EmptyImage(d_size[0], d_size[1])
        #x.add('created wximage %s  ' % (repr(self.wximage.GetSize())))
        if self.im_mode == 'L':
            self.wximage.SetData(self.imbuff.convert('RGB').tostring())
        elif self.im_mode == 'RGB':
            data.shape = (3, width, height)
            self.wximage = wx.ImageFromData(width, height, data)
        #x.add('set wx image wximage : %i, %i ' % d_size)            
        self.image.SetValue(self.wximage)
        #x.add('set image value')
        #x.show()

        
    def onProfile(self, x0, y0, x1, y1):
        width  = self.ad_cam.SizeX
        height = self.ad_cam.SizeY

        x0, y0 = int(x0 * width), int(y0 * height)
        x1, y1 = int(x1 * width), int(y1 * height)
        dx, dy = abs(x1 - x0), abs(y1 - y0)

        if dx < 2 and dy < 2:
            return
        outdat = []
        if self.colormode == 2:
            self.data.shape = (self.im_size[1], self.im_size[0], 3)
        else:
            self.data.shape = self.im_size[1], self.im_size[0]

        if dy  > dx:
            _y0 = min(int(y0), int(y1+0.5))
            _y1 = max(int(y0), int(y1+0.5))

            for iy in range(_y0, _y1):
                ix = int(x0 + (iy-int(y0))*(x1-x0)/(y1-y0))
                outdat.append((ix, iy))
        else:
            _x0 = min(int(x0), int(x1+0.5))
            _x1 = max(int(x0), int(x1+0.5))
            for ix in range(_x0, _x1):
                iy = int(y0 + (ix-int(x0))*(y1-y0)/(x1-x0))
                outdat.append((ix, iy))

        if self.lineplotter is None:
            self.lineplotter = PlotFrame(self, title='Image Profile')
        else:
            try:
                self.lineplotter.Raise()
            except PyDeadObjectError:
                self.lineplotter = PlotFrame(self, title='Image Profile')

        if self.colormode == 2:
            x, y, r, g, b = [], [], [], [], []
            for ix, iy in outdat:
                x.append(ix)
                y.append(iy)
                r.append(self.data[iy,ix,0])
                g.append(self.data[iy,ix,1])
                b.append(self.data[iy,ix,2])
            xlabel = 'Pixel (x)'
            if dy > dx:
                x = y
                xlabel = 'Pixel (y)'
            self.lineplotter.plot(x,  r, color='red', label='red',
                                  xlabel=xlabel, ylabel='Intensity',
                                  title='Image %i' % self.ad_cam.ArrayCounter_RBV)
            self.lineplotter.oplot(x, g, color='green', label='green')
            self.lineplotter.oplot(x, b, color='blue', label='blue')

        else:
            x, y, z = [], [], []
            for ix, iy in outdat:
                x.append(ix)
                y.append(iy)
                z.append(self.data[iy,ix])
            xlabel = 'Pixel (x)'
            if dy > dx:
                x = y
            xlabel = 'Pixel (y)'
            self.lineplotter.plot(x, z, color='k',
                                  xlabel=xlabel, ylabel='Intensity',
                                  title='Image %i' % self.ad_cam.ArrayCounter_RBV)
        self.lineplotter.Show()
        self.lineplotter.Raise()

    def onShowXY(self, xval, yval):
        ix  = max(0, int( xval * self.ad_cam.SizeX))
        iy  = max(0, int( yval * self.ad_cam.SizeY))
        
        if self.colormode == 2:
            self.data.shape = (self.im_size[1], self.im_size[0], 3)
            ival = tuple(self.data[iy, ix, :])
            smsg  = 'Pixel %i, %i, (R, G, B) = %s' % (ix, iy, repr(ival))
        else:
            self.data.shape = self.im_size[1], self.im_size[0]
            ival = self.data[iy, ix]
            smsg  = 'Pixel %i, %i, Intensity = %i' % (ix, iy, ival)

        self.messag(smsg, panel=1)


    def onName(self, evt=None, **kws):
        if evt is None:
            return
        s = evt.GetString()
        s = str(s).strip()
        if s.endswith(':image1:'): s = s[:-8]
        if s.endswith(':cam1:'):   s = s[:-6]
        if s.endswith(':'):   s = s[:-1]
        self.prefix = s
        self.connect_pvs()

    @EpicsFunction
    def onEntry(self, evt=None, key='name', **kw):
        if evt is None:
            return
        if key == 'start':
            self.n_img   = 0
            self.n_drawn = 0
            self.starttime = time.time()
            self.imgcount_start = self.ad_cam.ArrayCounter_RBV            
            self.ad_cam.Acquire = 1
        elif key == 'stop':
            self.ad_cam.Acquire = 0
        elif key == 'unzoom':
            self.unZoom()
        else:
            print 'unknown Entry ? ', key

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

        if verbose:
            self.messag('Connecting to AD %s' % self.prefix)
        self.ad_img = epics.Device(self.prefix + ':image1:', delim='',
                                   attrs=self.img_attrs)
        self.ad_cam = epics.Device(self.prefix + ':cam1:', delim='',
                                   attrs=self.cam_attrs)

        time.sleep(0.010)
        if not self.ad_img.PV('UniqueId_RBV').connected:
            epics.poll()
            if not self.ad_img.PV('UniqueId_RBV').connected:
                self.messag('Warning:  Camera seems to not be connected!')
                return
        if verbose:
            self.messag('Connected to AD %s' % self.prefix)

        self.SetTitle("Epics Image Display: %s" % self.prefix)

        self.wids['color'].SetPV(self.ad_cam.PV('ColorMode'))
        self.wids['exptime'].SetPV(self.ad_cam.PV('AcquireTime'))
        self.wids['period'].SetPV(self.ad_cam.PV('AcquirePeriod'))
        self.wids['gain'].SetPV(self.ad_cam.PV('Gain'))
        self.wids['numimages'].SetPV(self.ad_cam.PV('NumImages'))
        self.wids['imagemode'].SetPV(self.ad_cam.PV('ImageMode'))
        self.wids['triggermode'].SetPV(self.ad_cam.PV('TriggerMode'))

        sizelabel = 'Image Size: %i x %i pixels'
        try:
            sizelabel = sizelabel  % (self.ad_cam.MaxSizeX_RBV,
                                      self.ad_cam.MaxSizeY_RBV)
        except:
            sizelabel = sizelabel  % (0, 0)

        self.wids['fullsize'].SetLabel(sizelabel)
        self.showZoomsize()

        self.ad_img.add_callback('ArrayCounter_RBV',   self.onNewImage)
        self.ad_img.add_callback('ArraySize0_RBV', self.onProperty, dim=0)
        self.ad_img.add_callback('ArraySize1_RBV', self.onProperty, dim=1)
        self.ad_img.add_callback('ArraySize2_RBV', self.onProperty, dim=2)
        self.ad_img.add_callback('ColorMode_RBV',  self.onProperty, dim='color')
        self.ad_cam.add_callback('DetectorState_RBV',  self.onDetState)

        epics.caput("%s:cam1:ArrayCallbacks" % self.prefix, 1)
        for p in self.enabled_plugins:
            epics.caput("%s:%s:EnableCallbacks" % (self.prefix, p), 1)
        epics.caput("%s:JPEG1:NDArrayPort" % self.prefix, "OVER1")
        epics.caput("%s:TIFF1:NDArrayPort" % self.prefix, "OVER1")
        epics.caput("%s:image1:NDArrayPort"% self.prefix, "OVER1")
        
        self.ad_cam.Acquire = 0
        self.GetImageSize()
        self.unZoom()

        epics.poll()
        self.RefreshImage()

    @EpicsFunction
    def GetImageSize(self):
        self.arrsize = [1,1,1]
        self.arrsize[0] = self.ad_img.ArraySize0_RBV
        self.arrsize[1] = self.ad_img.ArraySize1_RBV
        self.arrsize[2] = self.ad_img.ArraySize2_RBV
        self.colormode = self.ad_img.ColorMode_RBV


        self.img_w = self.arrsize[1]
        self.img_h = self.arrsize[0]
        if self.colormode == 2:
            self.img_w = self.arrsize[2]
            self.img_h = self.arrsize[1]

    @DelayedEpicsCallback
    def onDetState(self, pvname=None, value=None, char_value=None, **kw):
        self.messag(char_value, panel=1)

    @DelayedEpicsCallback
    def onProperty(self, pvname=None, value=None, dim=None, **kw):
        if dim=='color':
            self.colormode=value
        else:
            self.arrsize[dim] = value

    @DelayedEpicsCallback
    def onNewImage(self, pvname=None, value=None, **kw):
        if value != self.img_id:
            self.img_id = value
            if not self.drawing:
                self.drawing = True
                self.RefreshImage()

    @EpicsFunction
    def RefreshImage(self, pvname=None, **kws):
        try:
            wx.Yield()
        except:
            pass
        d = debugtime()

        if self.ad_img is None or self.ad_cam is None:
            return 
        imgdim = self.ad_img.NDimensions_RBV
        imgcount = self.ad_cam.ArrayCounter_RBV
        now = time.time()
        if (imgcount == self.imgcount or abs(now - self.last_update) < 0.025):
            self.drawing = False
            return
        d.add('refresh img start')
        self.imgcount = imgcount
        self.drawing = True
        self.n_drawn += 1
        self.n_img = imgcount - self.imgcount_start
        #print 'ImgCount, n_drawn: ', imgcount, self.n_img, self.n_drawn

        self.last_update = time.time()
        self.image.can_resize = False

        xmin = self.ad_cam.MinX
        ymin = self.ad_cam.MinY
        width = self.ad_cam.SizeX
        height = self.ad_cam.SizeY

        arraysize = self.arrsize[0] * self.arrsize[1]
        if imgdim == 3:
            arraysize = arraysize * self.arrsize[2] 
        if not self.ad_img.PV('ArrayData').connected:
            self.drawing = False
            return
        
        d.add('refresh img before raw get %i' % arraysize)
        rawdata = self.ad_img.PV('ArrayData').get(count=arraysize)
        d.add('refresh img after raw get')        
        im_mode = 'L'
        im_size = (self.arrsize[0], self.arrsize[1])
        
        if self.colormode == 2:
            im_mode = 'RGB'
            im_size = [self.arrsize[1], self.arrsize[2]]
        if (self.colormode == 0 and isinstance(rawdata, np.ndarray) and
            rawdata.dtype != np.uint8):
            im_mode = 'I'
            rawdata = rawdata.astype(np.uint32)

        d.add('refresh img before msg')
        self.messag(' Image # %i ' % self.ad_cam.ArrayCounter_RBV, panel=2)
        d.add('refresh img before get image size')
        self.GetImageSize()

        self.im_size = im_size
        self.im_mode = im_mode
        self.data = rawdata
        d.add('refresh img before data to image')
        self.DatatoImage()
        d.add('refresh img after data to image')        
        self.image.can_resize = True
        nmissed = max(0, self.n_img-self.n_drawn)
        
        delt = time.time()-self.starttime
        percent_drawn = self.n_drawn * 100 / (self.n_drawn+nmissed)
        smsg = self.stat_msg % (percent_drawn, self.n_drawn/delt)
        self.messag(smsg, panel=0)

        self.drawing = False
        d.add('refresh img done')
        #d.show()

#         imbuff =  Image.frombuffer(im_mode, im_size, rawdata,
#                                    'raw', im_mode, 0, 1)
#         # d.add('refresh after Image.frombuffer')        
# 
#         self.GetImageSize()
# 
#         if self.img_h < 1 or self.img_w < 1:
#             return
#         display_size = (int(self.img_h*self.scale), int(self.img_w*self.scale))
# 
#         imbuff = imbuff.resize(display_size)
#         if self.wximage.GetSize() != imbuff.size:
#             self.wximage = wx.EmptyImage(display_size[0], display_size[1])
#         # d.add('refresh after sizing')
#         self.imbuff = imbuff
#         self.wximage.SetData(imbuff.convert('RGB').tostring())
#         # d.add('refresh set wximage.tostring')
#         self.image.SetValue(self.wximage)

        # d.show()

if __name__ == '__main__':
    import sys
    prefix = None
    if len(sys.argv) > 1:
        prefix = sys.argv[1]

    #app = wx.PySimpleApp()
    app = wx.App()
    frame = AD_Display(prefix=prefix, app=app)
    frame.Show()
    app.MainLoop()
