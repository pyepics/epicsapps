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

from debugtime import debugtime

os.environ['EPICS_CA_MAX_ARRAY_BYTES'] = '16777216'

import epics
from epics.wx import DelayedEpicsCallback, EpicsFunction, Closure

class ImageView(wx.Window):
    def __init__(self, parent, id=-1, pos=wx.DefaultPosition,
                 size=wx.DefaultSize, **kw):
        wx.Window.__init__(self, parent, id, pos, size, **kw)
        
        self.image = None
        self.SetBackgroundColour('WHITE')

        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_SIZE, self.OnSize)

    def SetValue(self, image):
        self.image = image
        self.Refresh()
    
    def OnSize(self, event):
        self.DrawImage(size=event.GetSize())
        event.Skip()
        self.Refresh()

    def OnPaint(self, event):
        self.DrawImage()

    def DrawImage(self, dc=None, size=None):
        if not hasattr(self,'image') or self.image is None:
            return
        if size is None:
            size = self.GetSize()
        wwidth,wheight = size
        image = self.image
        bmp = None
        if image.IsOk():
            iwidth = image.GetWidth()   
            iheight = image.GetHeight()
        else:
            bmp = wx.ArtProvider.GetBitmap(wx.ART_MISSING_IMAGE,
                                           wx.ART_MESSAGE_BOX, (64,64))
            iwidth  = bmp.GetWidth()
            iheight = bmp.GetHeight()

        xfactor = float(wwidth) / iwidth
        yfactor = float(wheight) / iheight

        scale = 1.0
        if xfactor < 1.0 and xfactor < yfactor:
            scale = xfactor
        elif yfactor < 1.0 and yfactor < xfactor:
            scale = yfactor

        owidth = int(scale*iwidth)
        oheight = int(scale*iheight)
        diffx = (wwidth - owidth)/2   # center calc
        diffy = (wheight - oheight)/2   # center calc

        if bmp is None:
            if owidth!=iwidth or oheight!=iheight:
                image = image.Scale(owidth,oheight)
            bmp = image.ConvertToBitmap()

        if dc is None:
            try:
                dc = wx.PaintDC(self)
            except:
                pass
        if dc is not None:
            dc.DrawBitmap(bmp, diffx, diffy, useMask=True)


class AD_Display(wx.Frame):
    """AreaDetector Display """
    img_attrs = ('ArrayData', 'UniqueId_RBV', 'NDimensions_RBV',
                 'ArraySize0_RBV', 'ArraySize1_RBV', 'ArraySize2_RBV',
                 'ColorMode_RBV')

    cam_attrs = ('Acquire', 'ArrayCounter', 'ArrayCounter_RBV',
                 'DetectorState_RBV',
                 'NumImages')
    
    def __init__(self, prefix=None, scale=1.0, approx_height=600):



        self.ad_img = None
        self.ad_cam = None
        self.prefix = prefix
        self.scale  = scale
        self.arrsize  = [0,0,0]
        self.imbuff = None
        self.colormode = 0

        wx.Frame.__init__(self, None, -1,
                          "Epics Area Detector Display",
                          style=wx.DEFAULT_FRAME_STYLE)
        
        self.img_w = 0
        self.img_h = 0
        self.wximage = wx.EmptyImage(approx_height, approx_height)
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
        labstyle = wx.ALIGN_LEFT|wx.LEFT|wx.TOP|wx.EXPAND        

        sizer.Add(wx.StaticText(panel, label='Base PV:', size=(120, -1)),
                  (0, 0), (1, 1), labstyle)
                               
        sizer.Add(wx.StaticText(panel, label='NX ', size=(60, -1)),
                  (0, 1), (1, 1), labstyle)
                               
        sizer.Add(wx.StaticText(panel, label='NY ', size=(60, -1)),
                  (0, 2), (1, 1), labstyle)
                               
        sizer.Add(wx.StaticText(panel, label='NZ ', size=(60, -1)),
                  (0, 3), (1, 1), labstyle)

#         sizer.Add(wx.StaticText(panel, label='Color', size=(60, -1)),
#                   (0, 4), (1, 1), labstyle)
# 
        txtstyle=wx.ALIGN_LEFT|wx.ST_NO_AUTORESIZE|wx.TE_PROCESS_ENTER
        self.wids = {}
        self.wids['name']= wx.TextCtrl(panel, -1,  size=(120,-1),
                                       style=txtstyle)
        self.wids['nx'] = wx.StaticText(panel, -1, size=(60,-1),
                                     style=txtstyle)
        self.wids['ny'] = wx.StaticText(panel, -1, size=(60,-1),
                                       style=txtstyle)
        self.wids['nz'] = wx.StaticText(panel, -1, size=(60,-1),
                                       style=txtstyle)        

        self.wids['name'].SetValue(self.prefix)
        
        for key, val in self.wids.items():
            val.Bind(wx.EVT_TEXT_ENTER, Closure(self.onEntry, key=key))
        
        sizer.Add(self.wids['name'], (1, 0), (1, 1), labstyle)
        sizer.Add(self.wids['nx'],  (1, 1), (1, 1), labstyle)
        sizer.Add(self.wids['ny'],  (1, 2), (1, 1), labstyle)
        sizer.Add(self.wids['nz'],  (1, 3), (1, 1), labstyle)

        self.image = ImageView(self, size=(600,500))
        
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

    def onEntry(self, evt=None, key='name', **kw):
        if evt is None:
            return
        s = evt.GetString()
        s = str(s).strip()
        if key == 'name':
            if s.endswith(':image1:'): s = s[:-8]
            if s.endswith(':cam1:'):   s = s[:-6]            
            self.prefix = s
            self.connect_pvs()
        else:
            print 'onEntry ? ', key

    @EpicsFunction
    def connect_pvs(self):
        self.messag('Connecting to AD %s' % self.prefix)
        self.ad_img = epics.Device(self.prefix + ':image1:', delim='',
                                   attrs=self.img_attrs)
        self.ad_cam = epics.Device(self.prefix + ':cam1:', delim='',
                                   attrs=self.cam_attrs)
        
        time.sleep(0.01)
        if not self.ad_img.PV('UniqueId_RBV').connected:
            epics.ca.poll()
            if not self.ad_img.PV('UniqueId_RBV').connected:
                self.messag('Warning:  Camera seems to not be connected!')
                return

        self.messag('Connected to AD %s' % self.prefix)

        self.SetTitle("Epics Image Display: %s" % self.prefix)
        self.ad_img.add_callback('UniqueId_RBV',   self.onNewImage)
        self.ad_img.add_callback('ArraySize0_RBV', self.onProperty, dim=0)
        self.ad_img.add_callback('ArraySize1_RBV', self.onProperty, dim=1)
        self.ad_img.add_callback('ArraySize2_RBV', self.onProperty, dim=2)
        self.ad_img.add_callback('ColorMode_RBV',  self.onProperty, dim='color')
        self.ad_cam.add_callback('DetectorState_RBV',  self.onDetState)

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

        self.wids['nx'].SetLabel('%i' % self.arrsize[0])
        self.wids['ny'].SetLabel('%i' % self.arrsize[1])
        self.wids['nz'].SetLabel('%i' % self.arrsize[2])

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
        self.RefreshImage()
        
    @EpicsFunction
    def RefreshImage(self):
        d = debugtime()
        imgdim = self.ad_img.NDimensions_RBV
        arraysize = self.arrsize[0] * self.arrsize[1]
        if imgdim == 3:
            arraysize = arraysize * self.arrsize[2] 
        if not self.ad_img.PV('ArrayData').connected:
            return

        im_mode = 'L'
        im_size = (self.arrsize[0], self.arrsize[1])
        
        if self.colormode == 2:
            im_mode = 'RGB'
            im_size = [self.arrsize[1], self.arrsize[2]]
        d.add('know image size/type')
        rawdata = self.ad_img.PV('ArrayData').get(count=arraysize)
        d.add('have rawdata')
        self.messag(' Image # %i ' % self.ad_cam.ArrayCounter_RBV, panel=2)

        imbuff =  Image.frombuffer(im_mode, im_size, rawdata,
                                   'raw', im_mode, 0, 1)
        d.add('data to imbuff')
        self.GetImageSize()
        if self.img_h < 1 or self.img_w < 1:
            return
        display_size = (int(self.img_h*self.scale), int(self.img_w*self.scale))

        imbuff = imbuff.resize(display_size)
        d.add('imbuff resized')
        if self.wximage.GetSize() != imbuff.size:
             self.wximage = wx.EmptyImage(display_size[0], display_size[1])

        self.wximage.SetData(imbuff.convert('RGB').tostring())
        self.image.SetValue(self.wximage)

        d.add('wx bitmap set')
        #if self.ad_cam.ArrayCounter_RBV % 5 == 0: d.show()
        
if __name__ == '__main__':
    import sys
    prefix = '13IDCPS1'
    if len(sys.argv) > 1:
        prefix = sys.argv[1]

    app = wx.PySimpleApp()
    frame = AD_Display(prefix=prefix)
    frame.Show()
    app.MainLoop()

