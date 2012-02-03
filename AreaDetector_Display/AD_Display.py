#!/usr/bin/env python
"""
   Display Application for Epics AreaDetector
"""

import os
import sys
import time

import wx
import numpy as np
import Image

# from debugtime import debugtime

os.environ['EPICS_CA_MAX_ARRAY_BYTES'] = '16777216'

import epics
import epics.wx
from epics.wx import (DelayedEpicsCallback, EpicsFunction, Closure,
                      PVEnumChoice, PVFloatCtrl, PVFloatSpin)
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
                 
    def __init__(self, prefix=None, app=None, scale=1.0, approx_height=800):
        self.app = app
        self.ad_img = None
        self.ad_cam = None
        self.imgcount = 0
        self.prefix = prefix
        self.fname = 'AD_Image.tiff'
        self.scale  = scale
        self.arrsize  = [0,0,0]
        self.imbuff = None
        self.colormode = 0
        self.last_update = 0.0
        self.n_img   = 0
        self.n_drawn = 0
        self.img_id = 0
        self.starttime = time.time()
        self.drawing = False
        self.zoom_lims = []

        wx.Frame.__init__(self, None, -1,
                          "Epics Area Detector Display",
                          style=wx.DEFAULT_FRAME_STYLE)

        if self.prefix is None:
            self.GetPVName()
            
        self.img_w = 0
        self.img_h = 0
        self.wximage = wx.EmptyImage(approx_height, 1.5*approx_height)
        self.buildMenus()
        self.buildFrame()

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
        if self.imbuff is not None:
            self.imbuff.save(path)

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
        filemenu = wx.Menu()
        FOPEN = wx.NewId()
        FSAVE = wx.NewId()
        FCOPY = wx.NewId()
        FEXIT = wx.NewId()
        HABOUT = wx.NewId()

        filemenu.Append(FOPEN, "&Connect to PV\tCtrl+O",  "Connect to PV")
        filemenu.Append(FSAVE, "&Save\tCtrl+S",  "Save Image")
        filemenu.Append(FCOPY, "&Copy\tCtrl+C",  "Copy Image to Clipboard")
        filemenu.AppendSeparator()
        filemenu.Append(FEXIT, "E&xit\tCtrl+Q",  "Exit Program")

        self.Bind(wx.EVT_MENU, self.GetPVName,   id=FOPEN)
        self.Bind(wx.EVT_MENU, self.onSaveImage, id=FSAVE)
        self.Bind(wx.EVT_MENU, self.onCopyImage, id=FCOPY)
        self.Bind(wx.EVT_MENU, self.onExit,      id=FEXIT)
        self.Bind(wx.EVT_MENU, self.onAbout,     id=HABOUT)

        OROTCW  = wx.NewId()
        OROTCCW = wx.NewId()
        OFLIPH  = wx.NewId()
        OFLIPV  = wx.NewId()
        OZOOM   = wx.NewId()
        ORESET  = wx.NewId()
        OCMODE  = wx.NewId()

        optsmenu = wx.Menu()
        optsmenu.Append(OROTCW,  "&Rotate Clockwise\tCtrl+R", "Rotate Clockwise")
        optsmenu.Append(OROTCCW, "&Rotate CounterClockwise", "Rotate Counter Clockwise")
        optsmenu.Append(OFLIPV,  "&Flip Up/Down\tCtrl+F", "Flip Up/Down")
        optsmenu.Append(OFLIPH,  "&Mlip Left/Right\tCtrl+M", "Flip Left/Right")
        optsmenu.AppendSeparator()
        optsmenu.Append(ORESET,  "Reset Image Counter", "Set Image Counter to 0")
        optsmenu.Append(OZOOM,  "&Zoom out\tCtrl+Z", "Zoom Out")

        self.CM_ZOOM = wx.NewId()
        self.CM_PROF = wx.NewId()
        self.CM_SHOW = wx.NewId()
#         optsmenu.Append(self.CM_ZOOM, "Cursor Mode: Zoom",
#                         "Zoom to box by clicking and dragging", wx.ITEM_RADIO)
#         optsmenu.Append(self.CM_SHOW, "Cursor Mode: Show X,Y",
#                         "Show X,Y, Intensity Values",  wx.ITEM_RADIO)
#         optsmenu.Append(self.CM_PROF, "Cursor Mode: Line Profile",
#                         "Show Line Profile",  wx.ITEM_RADIO)
# 
        helpmenu = wx.Menu()
        helpmenu.Append(HABOUT, "About", "About Epics AreadDetector Display")

        mbar = wx.MenuBar()

        mbar.Append(filemenu, "File")
        mbar.Append(optsmenu, "Options")
        mbar.Append(helpmenu, "&Help")
        self.SetMenuBar(mbar)

        self.Bind(wx.EVT_MENU, self.onFlipV,  id=OFLIPV)
        self.Bind(wx.EVT_MENU, self.onFlipH,  id=OFLIPH)
        self.Bind(wx.EVT_MENU, self.onRotCW,  id=OROTCW)
        self.Bind(wx.EVT_MENU, self.onRotCCW,  id=OROTCCW)
        self.Bind(wx.EVT_MENU, self.unZoom,   id=OZOOM)
        self.Bind(wx.EVT_MENU, self.onResetImageCounter,  id=ORESET)

        self.Bind(wx.EVT_MENU, self.onCursorMode,  id=self.CM_ZOOM)
        self.Bind(wx.EVT_MENU, self.onCursorMode,  id=self.CM_PROF)
        self.Bind(wx.EVT_MENU, self.onCursorMode,  id=self.CM_SHOW)

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
        self.Refresh()

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
        labstyle = wx.ALIGN_CENTER|wx.ALIGN_BOTTOM|wx.EXPAND        

        rlabstyle = wx.ALIGN_RIGHT|wx.RIGHT|wx.TOP|wx.EXPAND      

        txtstyle=wx.ALIGN_LEFT|wx.ST_NO_AUTORESIZE|wx.TE_PROCESS_ENTER
        self.wids = {}
        self.wids['exptime']   = PVFloatCtrl(panel, pv=None, size=(60,-1))
        self.wids['period']    = PVFloatCtrl(panel, pv=None, size=(60,-1))
        self.wids['numimages'] = PVFloatCtrl(panel, pv=None, size=(60,-1))
        self.wids['gain']      = PVFloatSpin(panel, pv=None, size=(60,-1), 
                                             min_val=0, max_val=20, increment=1, digits=1)

        self.wids['imagemode']   = PVEnumChoice(panel, pv=None)
        self.wids['triggermode'] = PVEnumChoice(panel, pv=None)
        self.wids['color']       = PVEnumChoice(panel, pv=None)
        self.wids['start'] = wx.Button(panel, -1, label='Start', size=(50,-1))
        self.wids['stop']  = wx.Button(panel, -1, label='Stop', size=(50,-1))


        for key in ('start', 'stop'):
            self.wids[key].Bind(wx.EVT_BUTTON, Closure(self.onEntry, key=key))

        self.wids['zoomsize']= wx.StaticText(panel, -1,  size=(170,-1), style=txtstyle)
        self.wids['fullsize']= wx.StaticText(panel, -1,  size=(170,-1), style=txtstyle)

        def txt(label, size=80):
            return wx.StaticText(panel, label=label, size=(size, -1), style=labstyle)


        sizer.Add(txt('Image Mode '),       (0, 0), (1, 1), labstyle)
        sizer.Add(self.wids['imagemode'],   (1, 0), (1, 1), labstyle)

        sizer.Add(txt('# Images '),         (0, 1), (1, 1), labstyle)
        sizer.Add(self.wids['numimages'],   (1, 1), (1, 1), labstyle)

        sizer.Add(txt('Trigger Mode '),     (0, 2), (1, 1), labstyle)
        sizer.Add(self.wids['triggermode'], (1, 2), (1, 1), labstyle)

        sizer.Add(txt('Period '),           (0, 3), (1, 1), labstyle)
        sizer.Add(self.wids['period'],      (1, 3), (1, 1), labstyle)

        sizer.Add(txt('Exposure Time '),    (0, 4), (1, 1), labstyle)
        sizer.Add(self.wids['exptime'],     (1, 4), (1, 1), labstyle)


        sizer.Add(txt('Gain '),             (0, 5), (1, 1), labstyle)
        sizer.Add(self.wids['gain'],        (1, 5), (1, 1), labstyle)

        sizer.Add(txt('Color Mode'),        (0, 6), (1, 1), labstyle)
        sizer.Add(self.wids['color'],       (1, 6), (1, 1), labstyle)

        sizer.Add(txt('Acquire '),          (0, 7), (1, 2), labstyle)
        sizer.Add(self.wids['start'],       (1, 7), (1, 1), labstyle)
        sizer.Add(self.wids['stop'],        (1, 8), (1, 1), labstyle)

        sizer.Add(self.wids['fullsize'],    (0, 9), (1, 1), labstyle)
        sizer.Add(self.wids['zoomsize'],    (1, 9), (1, 1), labstyle)
    
        self.image = ImageView(self, size=(800,600), onzoom=self.onZoom)
        
        self.SetAutoLayout(True)
        panel.SetSizer(sizer)
        sizer.Fit(panel)
        
        mainsizer = wx.BoxSizer(wx.VERTICAL)

        mainsizer.Add(panel, 0, wx.CENTER|wx.GROW|wx.ALL, 1)
        mainsizer.Add(self.image, 1, wx.CENTER|wx.GROW|wx.ALL, 1)
        self.SetSizer(mainsizer)
        mainsizer.Fit(self)
        wx.CallAfter(self.connect_pvs )

    def messag(self, s, panel=0):
        """write a message to the Status Bar"""
        self.SetStatusText(s, panel)

    @EpicsFunction
    def unZoom(self, event=None, full=False):
        if self.zoom_lims is None or full:
            self.zoom_lims = []

        if len(self.zoom_lims) == 0:
            xmin, ymin = 0, 0
            width = self.ad_cam.MaxSizeX_RBV
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
        time.sleep(0.05)
        self.showZoomsize()
        self.image.DrawImage(isize=(width, height))
        self.image.Refresh()

    @EpicsFunction
    def showZoomsize(self):
        msg  = 'Displaying:  %i x %i pixels' % (self.ad_cam.SizeX, self.ad_cam.SizeY)
        self.wids['zoomsize'].SetLabel(msg) 
        
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
        
        self.img_w = height
        self.img_h = width
        self.drawing = True
        self.image.DrawImage(isize=(width, height))
        self.image.Refresh()
        self.drawing = False

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

        if verbose:
            self.messag('Connecting to AD %s' % self.prefix)

        self.ad_img = epics.Device(self.prefix + ':image1:', delim='',
                                   attrs=self.img_attrs)
        self.ad_cam = epics.Device(self.prefix + ':cam1:', delim='',
                                   attrs=self.cam_attrs)
        
        time.sleep(0.005)
        if not self.ad_img.PV('UniqueId_RBV').connected:
            epics.ca.poll()
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

        sizelabel = 'Image Size:   %i x %i pixels' % (self.ad_cam.MaxSizeX_RBV,
                                                    self.ad_cam.MaxSizeY_RBV)
        self.wids['fullsize'].SetLabel(sizelabel) 
        self.showZoomsize()

        self.ad_img.add_callback('UniqueId_RBV',   self.onNewImage)
        self.ad_img.add_callback('ArraySize0_RBV', self.onProperty, dim=0)
        self.ad_img.add_callback('ArraySize1_RBV', self.onProperty, dim=1)
        self.ad_img.add_callback('ArraySize2_RBV', self.onProperty, dim=2)
        self.ad_img.add_callback('ColorMode_RBV',  self.onProperty, dim='color')
        self.ad_cam.add_callback('DetectorState_RBV',  self.onDetState)
    
        self.ad_cam.Acquire = 0
        self.GetImageSize()
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
            self.n_img += 1
            if not self.drawing:
                self.drawing = True
                self.RefreshImage()


    @EpicsFunction
    def RefreshImage(self, pvname=None, **kws):
        try:
            wx.Yield()
        except:
            pass
        # d = debugtime()
        imgdim = self.ad_img.NDimensions_RBV
        imgcount = self.ad_cam.ArrayCounter_RBV

        now = time.time()
        if (imgcount == self.imgcount or abs(now - self.last_update) < 0.05):
            self.drawing = False
            return
        # d.add('refresh img start')
        self.imgcount = imgcount
        self.drawing = True
        self.n_drawn += 1

        self.last_update = time.time()
        self.image.can_resize = False

        arraysize = self.arrsize[0] * self.arrsize[1]
        if imgdim == 3:
            arraysize = arraysize * self.arrsize[2] 
        if not self.ad_img.PV('ArrayData').connected:
            self.drawing = False
            return

        rawdata = self.ad_img.PV('ArrayData').get(count=arraysize)
        im_mode = 'L'
        im_size = (self.arrsize[0], self.arrsize[1])

        if self.colormode == 2:
            im_mode = 'RGB'
            im_size = [self.arrsize[1], self.arrsize[2]]
        if (self.colormode == 0 and isinstance(rawdata, np.ndarray)):
            if rawdata.dtype != np.uint8:
                im_mode = 'I'
                rawdata = rawdata.astype(np.uint32)
        
        # d.add('refresh got data')

        self.messag(' Image # %i ' % self.ad_cam.ArrayCounter_RBV, panel=2)

        imbuff =  Image.frombuffer(im_mode, im_size, rawdata,
                                   'raw', im_mode, 0, 1)
        # d.add('refresh after Image.frombuffer')        
        nmissed = max(0, self.n_img-self.n_drawn)
        smsg = 'Drew %i, Missed %i images in %.2f seconds' % (self.n_drawn,
                                                              nmissed,
                                                              time.time()-self.starttime)
        self.messag(smsg, panel=0)

        self.GetImageSize()
        if self.img_h < 1 or self.img_w < 1:
            return
        display_size = (int(self.img_h*self.scale), int(self.img_w*self.scale))

        imbuff = imbuff.resize(display_size)
        if self.wximage.GetSize() != imbuff.size:
            self.wximage = wx.EmptyImage(display_size[0], display_size[1])
        # d.add('refresh after sizing')
        self.imbuff = imbuff
        self.wximage.SetData(imbuff.convert('RGB').tostring())
        # d.add('refresh set wximage.tostring')
        self.image.SetValue(self.wximage)
        self.image.DrawImage()
        # self.image.Refresh()
        self.image.can_resize = True        
        self.drawing = False
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

