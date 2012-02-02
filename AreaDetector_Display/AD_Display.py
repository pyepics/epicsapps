#!/usr/bin/env python
"""
Simple Display for Epics AreaDetector
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
                      PVEnumChoice, PVFloatCtrl)

class ImageView(wx.Window):
    def __init__(self, parent, id=-1, pos=wx.DefaultPosition,
                 size=wx.DefaultSize, onzoom=None, **kw):
        wx.Window.__init__(self, parent, id, pos, size, **kw)
        
        self.image = None
        self.SetBackgroundColour('#EEEEEE')
        self.can_resize = True
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)
        self.Bind(wx.EVT_LEFT_UP, self.OnLeftUp)
        self.Bind(wx.EVT_MOTION, self.OnMotion)

        self.onzoom = onzoom

        self.zoom_box = None
        self.zoom_coords = None

    def OnLeftDown(self, event=None):
        self.zoom_box = None
        self.zoom_coords = [event.x, event.y]

    def OnLeftUp(self, event=None):
        self.zoom_coords = None
        if hasattr(self.onzoom, '__call__') and self.zoom_box is not None:

            xoff = (self.win_size[0] - self.img_size[0])/2.0
            yoff = (self.win_size[1] - self.img_size[1])/2.0
            x0  = (self.zoom_box[0] - xoff)/ (1.0*self.img_size[0])
            y0  = (self.zoom_box[1] - yoff)/ (1.0*self.img_size[1])
            x1  =  self.zoom_box[2] / (1.0*self.img_size[0])
            y1  =  self.zoom_box[3] / (1.0*self.img_size[1])
            self.onzoom(x0, y0, x1, y1)
        self.zoom_box = None

    def OnMotion(self, event=None):
        if self.zoom_coords is None: 
            return
        x0 = min(event.x, self.zoom_coords[0])
        y0 = min(event.y, self.zoom_coords[1])
        w  = abs(event.x - self.zoom_coords[0])
        h  = abs(event.y - self.zoom_coords[1])

        zdc = wx.ClientDC(self)
        zdc.SetLogicalFunction(wx.XOR)
        zdc.SetBrush(wx.TRANSPARENT_BRUSH)
        zdc.SetPen(wx.Pen('White', 2, wx.SOLID))
        pen = zdc.GetPen()

        zdc.ResetBoundingBox()
        zdc.BeginDrawing()

        if self.zoom_box is not None:
            zdc.DrawRectangle(*self.zoom_box)
        self.zoom_box = (x0, y0, w, h)
        zdc.DrawRectangle(*self.zoom_box)
        zdc.EndDrawing()
        
    def SetValue(self, image):
        self.image = image
        self.Refresh()
    
    def OnSize(self, event):
        if self.can_resize:
            self.DrawImage(size=event.GetSize())
            self.Refresh()
        event.Skip()

    def OnPaint(self, event):
        self.DrawImage()

    def DrawImage(self, dc=None, isize=None, size=None):
        if not hasattr(self, 'image') or self.image is None:
            return

        if size is None:
            size = self.GetSize()
        try:
            wwidth, wheight = size
        except:
            return

        image = self.image
        bmp = None
        if isize is not None:
            iwidth, iheight = isize
        elif image.IsOk():
            iwidth = image.GetWidth()   
            iheight = image.GetHeight()
        else:
            bmp = wx.ArtProvider.GetBitmap(wx.ART_MISSING_IMAGE,
                                           wx.ART_MESSAGE_BOX, (64,64))
            iwidth  = bmp.GetWidth()
            iheight = bmp.GetHeight()
  

        xfactor = float(wwidth) / iwidth
        yfactor = float(wheight) / iheight

        scale = yfactor
        if xfactor < yfactor:
            scale = xfactor

        # print 'Draw Image ', isize is None, image.IsOk(), iwidth, iheight, wwidth, wheight, scale

        owidth = int(scale*iwidth)
        oheight = int(scale*iheight)
        diffx = (wwidth - owidth)/2   # center calc
        diffy = (wheight - oheight)/2   # center calc
        self.img_size = owidth, oheight
        self.win_size = wwidth, wheight

        if bmp is None:
            if owidth!=iwidth or oheight!=iheight:
                image = image.Scale(owidth, oheight)
            bmp = image.ConvertToBitmap()
        if dc is None:
            try:
                dc = wx.PaintDC(self)
            except:
                pass
        if dc is not None:
            dc.DrawBitmap(bmp, diffx, diffy, useMask=True)


        if self.zoom_box is not None:
            zdc = wx.ClientDC(self)
            zdc.SetLogicalFunction(wx.XOR)
            zdc.SetBrush(wx.TRANSPARENT_BRUSH)
            zdc.SetPen(wx.Pen('White', 2, wx.SOLID))
            pen = zdc.GetPen()

            zdc.ResetBoundingBox()
            zdc.BeginDrawing()
            zdc.DrawRectangle(*self.zoom_box)
            zdc.EndDrawing()


        
class AD_Display(wx.Frame):
    """AreaDetector Display """
    img_attrs = ('ArrayData', 'UniqueId_RBV', 'NDimensions_RBV',
                 'ArraySize0_RBV', 'ArraySize1_RBV', 'ArraySize2_RBV',
                 'ColorMode_RBV')

    cam_attrs = ('Acquire', 'ArrayCounter', 'ArrayCounter_RBV',
                 'DetectorState_RBV',  'NumImages', 'ColorMode',
                 'DataType_RBV', 
                 'AcquireTime', 'AcquirePeriod', 'ImageMode',
                 'MaxSizeX_RBV', 'MaxSizeY_RBV', 'TriggerMode',
                 'SizeX', 'SizeY', 'MinX', 'MinY')
                 
    def __init__(self, prefix=None, app=None, scale=1.0, approx_height=800):

        self.app = app
        self.ad_img = None
        self.ad_cam = None
        self.imgcount = 0
        self.prefix = prefix
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
        wx.CallAfter(self.connect_pvs )
        wx.Frame.__init__(self, None, -1,
                          "Epics Area Detector Display",
                          style=wx.DEFAULT_FRAME_STYLE)

        self.img_w = 0
        self.img_h = 0
        self.wximage = wx.EmptyImage(approx_height, 1.5*approx_height)
        self.buildFrame()

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
        labstyle = wx.ALIGN_LEFT|wx.LEFT|wx.TOP|wx.EXPAND        
        rlabstyle = wx.ALIGN_RIGHT|wx.RIGHT|wx.TOP|wx.EXPAND      

        txtstyle=wx.ALIGN_LEFT|wx.ST_NO_AUTORESIZE|wx.TE_PROCESS_ENTER
        self.wids = {}
        self.wids['name']= wx.TextCtrl(panel, -1,  size=(100,-1),
                                       style=txtstyle)
        self.wids['expt']   = PVFloatCtrl(panel, pv=None, size=(60,-1))
        self.wids['period'] = PVFloatCtrl(panel, pv=None, size=(60,-1))
        self.wids['numimages'] = PVFloatCtrl(panel, pv=None, size=(60,-1))

        self.wids['imagemode'] = PVEnumChoice(panel, pv=None)
        self.wids['triggermode'] = PVEnumChoice(panel, pv=None)
        self.wids['color'] = PVEnumChoice(panel, pv=None)
        self.wids['start'] = wx.Button(panel, -1, label='Start', size=(50,-1))
        self.wids['stop']  = wx.Button(panel, -1, label='Stop', size=(50,-1))
        self.wids['unzoom']  = wx.Button(panel, -1, label='Zoom Out', size=(75,-1))

        self.wids['name'].SetValue(self.prefix)
        self.wids['name'].Bind(wx.EVT_TEXT_ENTER, self.onName)

        for key in ('start', 'stop', 'unzoom'):
            self.wids[key].Bind(wx.EVT_BUTTON, Closure(self.onEntry, key=key))
            
        self.wids['xmin'] = PVFloatCtrl(panel, pv=None, size=(60,-1))
        self.wids['ymin'] = PVFloatCtrl(panel, pv=None, size=(60,-1))
        self.wids['xsize'] = PVFloatCtrl(panel, pv=None, size=(60,-1))
        self.wids['ysize'] = PVFloatCtrl(panel, pv=None, size=(60,-1))
        self.wids['fullsize']= wx.StaticText(panel, -1,  size=(120,-1), style=txtstyle)
        sizer.Add(wx.StaticText(panel, label='PV Name:', size=(100, -1)),
                  (0, 0), (1, 1), labstyle)
                               
        sizer.Add(wx.StaticText(panel, label='Exposure Time ', size=(60, -1)),
                  (0, 1), (1, 1), labstyle)
                               
        sizer.Add(wx.StaticText(panel, label='Period ', size=(60, -1)),
                  (0, 2), (1, 1), labstyle)
        sizer.Add(wx.StaticText(panel, label='# Images', size=(60, -1)),
                  (0, 3), (1, 1), labstyle)
                                                     
        sizer.Add(wx.StaticText(panel, label='Image Mode ', size=(60, -1)),
                  (0, 4), (1, 1), labstyle)

        sizer.Add(wx.StaticText(panel, label='Trigger Mode ', size=(60, -1)),
                  (0, 5), (1, 1), labstyle)

        sizer.Add(wx.StaticText(panel, label='Color', size=(60, -1)),
                  (0, 6), (1, 1), labstyle)

        sizer.Add(wx.StaticText(panel, label=' Acquire ', size=(120, -1)),
                  (0, 7), (1, 2), labstyle)

        sizer.Add(self.wids['name'], (1, 0), (1, 1), labstyle)
        sizer.Add(self.wids['expt'],  (1, 1), (1, 1), labstyle)
        sizer.Add(self.wids['period'],  (1, 2), (1, 1), labstyle)
        sizer.Add(self.wids['numimages'],  (1, 3), (1, 1), labstyle)
        sizer.Add(self.wids['imagemode'],  (1, 4), (1, 1), labstyle)
        sizer.Add(self.wids['triggermode'], (1, 5), (1, 1), labstyle)
        sizer.Add(self.wids['color'], (1, 6), (1, 1), labstyle)
        sizer.Add(self.wids['start'], (1, 7), (1, 1), labstyle)
        sizer.Add(self.wids['stop'],  (1, 8), (1, 1), labstyle)

        sizer.Add(wx.StaticText(panel, label='Region: Start= ', size=(60, -1), style=rlabstyle),
                  (2, 0), (1, 1), rlabstyle)
        sizer.Add(self.wids['xmin'],  (2, 1), (1, 1), labstyle)
        sizer.Add(self.wids['ymin'],  (2, 2), (1, 1), labstyle)
        sizer.Add(wx.StaticText(panel, label=' Size= ', size=(60, -1), style=rlabstyle),
                  (2, 3), (1, 1), rlabstyle)
        sizer.Add(self.wids['xsize'],  (2, 4), (1, 1), labstyle)
        sizer.Add(self.wids['ysize'],  (2, 5), (1, 1), labstyle)
        
        sizer.Add(self.wids['fullsize'],  (2, 6), (1, 2), labstyle)
        sizer.Add(self.wids['unzoom'],  (2, 8), (1, 1), labstyle)
    
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
    def unZoom(self):
        self.ad_cam.MinX = 0
        self.ad_cam.MinY = 0
        self.ad_cam.SizeX = self.ad_cam.MaxSizeX_RBV
        self.ad_cam.SizeY = self.ad_cam.MaxSizeY_RBV
        self.onZoom(0, 0, 1, 1)

    @EpicsFunction
    def onZoom(self, x0, y0, x1, y1):
        # print '=== ZOOM ',x0, y0, x1, y1
        width  = self.ad_cam.SizeX 
        height = self.ad_cam.SizeY
        xmin   = max(0, int(self.ad_cam.MinX  + x0 * width))
        ymin   = max(0, int(self.ad_cam.MinY  + y0 * height))
        width  = int(x1 * width)
        height = int(y1 * height)
        self.ad_cam.MinX = xmin
        self.ad_cam.MinY = ymin
        self.ad_cam.SizeX = width
        self.ad_cam.SizeY = height
        self.img_w = height
        self.img_h = width
        self.image.DrawImage(isize=(width, height))
        self.image.Refresh()

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
        if self.prefix is None or len(self.prefix) < 4:
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
        self.wids['expt'].SetPV(self.ad_cam.PV('AcquireTime'))
        self.wids['period'].SetPV(self.ad_cam.PV('AcquirePeriod'))        
        self.wids['numimages'].SetPV(self.ad_cam.PV('NumImages'))
        self.wids['imagemode'].SetPV(self.ad_cam.PV('ImageMode'))
        self.wids['triggermode'].SetPV(self.ad_cam.PV('TriggerMode'))     
        self.wids['xmin'].SetPV(self.ad_cam.PV('MinX'))        
        self.wids['ymin'].SetPV(self.ad_cam.PV('MinY'))   
        self.wids['xsize'].SetPV(self.ad_cam.PV('SizeX'))   
        self.wids['ysize'].SetPV(self.ad_cam.PV('SizeY'))    
        sizelabel = 'Image Size: %i x %i' % (self.ad_cam.MaxSizeX_RBV, self.ad_cam.MaxSizeY_RBV)
        self.wids['fullsize'].SetLabel(sizelabel) 
              
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

        #self.wids['nx'].SetLabel('%i' % self.arrsize[0])
        #self.wids['ny'].SetLabel('%i' % self.arrsize[1])
        #self.wids['nz'].SetLabel('%i' % self.arrsize[2])

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
        # print 'on New Image ', value, self.img_id, self.n_img, self.drawing
        if value != self.img_id:
            self.img_id = value
            self.n_img += 1
            if not self.drawing:
                self.drawing = True
                self.RefreshImage()


    @EpicsFunction
    def RefreshImage(self, pvname=None, **kws):
        try:
            #time.sleep(0.005)
            #app = wx.GetApp()
            #app.ProcessIdle()
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
        # print 'Image Mode ', im_mode, self.colormode, ' datatype = ', self.ad_cam.get('DataType_RBV', as_string=True)
        #print type(rawdata), rawdata[:10], rawdata.dtype
        #rawdata = rawdata.astype(np.uint32)
        # print type(rawdata), rawdata[:10], rawdata.dtype
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
    prefix = ''
    if len(sys.argv) > 1:
        prefix = sys.argv[1]

    #app = wx.PySimpleApp()
    app = wx.App()
    frame = AD_Display(prefix=prefix, app=app)
    frame.Show()
    app.MainLoop()

