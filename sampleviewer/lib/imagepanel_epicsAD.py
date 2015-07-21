"""Image Panel for Epics AreaDetector
"""

import wx
import time
import os
import numpy as np

from epics import PV, Device, caput, poll
from epics.wx import EpicsFunction

from PIL import Image
from .imagepanel_base import ImagePanel_Base

from epics.wx import (DelayedEpicsCallback, EpicsFunction, Closure,
                      PVEnumChoice, PVFloatCtrl, PVTextCtrl)
from epics.wx.utils import pack
                            
class ImagePanel_EpicsAD(ImagePanel_Base):
    img_attrs = ('ArrayData', 'UniqueId_RBV', 'NDimensions_RBV',
                 'ArraySize0_RBV', 'ArraySize1_RBV', 'ArraySize2_RBV',
                 'ColorMode_RBV')

    cam_attrs = ('Acquire', 'ArrayCounter', 'ArrayCounter_RBV',
                 'DetectorState_RBV',  'NumImages', 'ColorMode',
                 'ColorMode_RBV', 
                 'DataType_RBV',  'Gain',
                 'AcquireTime', 'AcquirePeriod', 'ImageMode',
                 'ArraySizeX_RBV', 'ArraySizeY_RBV')
    
    """Image Panel for FlyCapture2 camera"""
    def __init__(self, parent, prefix=None, format='JPEG',
                 writer=None, autosave_file=None, **kws):
        super(ImagePanel_EpicsAD, self).__init__(parent, -1,
                                                 size=(800, 600),
                                                 writer=writer,
                                                 autosave_file=autosave_file)

        if prefix.endswith(':'):
            prefix = prefix[:-1]
        if prefix.endswith(':image1'):
            prefix = prefix[:-7]
        if prefix.endswith(':cam1'):
            prefix = prefix[:-5]

        self.ad_img = Device(prefix + ':image1:', delim='',
                                   attrs=self.img_attrs)
        self.ad_cam = Device(prefix + ':cam1:', delim='',
                                   attrs=self.cam_attrs)

        self.config_filesaver(prefix, format)

        width = self.ad_cam.ArraySizeX_RBV
        height = self.ad_cam.ArraySizeY_RBV
       
        self.img_w = float(width+0.5)
        self.img_h = float(height+0.5)
        self.cam_name = prefix

        self.imgcount = 0
        self.imgcount_start = 0
        self.last_update = 0.0

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.onTimer, self.timer)


    def config_filesaver(self, prefix, format):
        if not prefix.endswith(':'):  prefix = "%s:" % prefix
        if not format.endswith('1'):  format = "%s1" % format
        if not format.endswith('1:'): format = "%s:" % format
            
        cname = "%s%s"% (prefix, format)
        caput("%sEnableCallbacks" % cname, 1)
        thisdir = os.path.abspath(os.getcwd()).replace('\\', '/')
        # caput("%sFilePath" % cname, thisdir)
        caput("%sAutoSave" % cname, 0)
        caput("%sAutoIncrement" % cname, 0)
        caput("%sFileTemplate" % cname, "%s%s")
        if format.upper() == 'JPEG1:':
            caput("%sJPEGQuality" % cname, 90)

    def Start(self):
        "turn camera on"
        self.timer.Start(50)
        if self.autosave_thread is not None:
            self.autosave_thread.start()

    def Stop(self):
        "turn camera off"
        self.timer.Stop()
        self.autosave = False
        if self.autosave_thread is not None:
            self.autosave_thread.join()

    def GetImageSize(self):
        self.arrsize = [1,1,1]
        self.arrsize[0] = self.ad_img.ArraySize0_RBV
        self.arrsize[1] = self.ad_img.ArraySize1_RBV
        self.arrsize[2] = self.ad_img.ArraySize2_RBV
        self.colormode = self.ad_img.ColorMode_RBV
        self.img_w = float(self.arrsize[0]+0.5)
        self.img_h = float(self.arrsize[1]+0.5)
        if self.colormode == 2:
            self.img_w = float(self.arrsize[1]+0.5)
            self.img_h = float(self.arrsize[2]+0.5)

    def GrabWxImage(self, scale=1, rgb=True):
        if self.ad_img is None or self.ad_cam is None:
            return

        imgdim   = self.ad_img.NDimensions_RBV
        width    = self.ad_cam.SizeX
        height   = self.ad_cam.SizeY
      
        imgcount = self.ad_cam.ArrayCounter_RBV
        now = time.time()
        if (imgcount == self.imgcount or abs(now - self.last_update) < 0.025):
            return None
        self.imgcount = imgcount
        self.last_update = time.time()

        arrsize = [1,1,1]
        arrsize[0] = self.ad_img.ArraySize0_RBV
        arrsize[1] = self.ad_img.ArraySize1_RBV
        arrsize[2] = self.ad_img.ArraySize2_RBV

        colormode = self.ad_img.ColorMode_RBV
        im_mode = 'L'
        self.im_size = (arrsize[0], arrsize[1])
        if colormode == 2:
            im_mode = 'RGB'
            self.im_size = (arrsize[1], arrsize[2])
        
        dcount = arrsize[0] * arrsize[1]
        if imgdim == 3:
            dcount *= arrsize[2]

        rawdata = self.ad_img.PV('ArrayData').get(count=dcount)
        if rawdata is None:
            return
        
        if (colormode == 0 and isinstance(rawdata, np.ndarray) and
            rawdata.dtype != np.uint8):
            im_mode = 'I'
            rawdata = rawdata.astype(np.uint32)

        if im_mode in ('L', 'I'):
            image = wx.EmptyImage(width, height)
            imbuff = Image.frombuffer(im_mode, self.im_size, rawdata,
                                      'raw',  im_mode, 0, 1)
            image.SetData(imbuff.convert('RGB').tostring())

        elif im_mode == 'RGB':
            rawdata.shape = (3, width, height)
            image = wx.ImageFromData(width, height, rawdata)

        return image.Scale(int(scale*width), int(scale*height))

class ConfPanel_EpicsAD(wx.Panel):
    img_attrs = ('ArrayData', 'UniqueId_RBV', 'NDimensions_RBV',
                 'ArraySize0_RBV', 'ArraySize1_RBV', 'ArraySize2_RBV',
                 'ColorMode_RBV')

    cam_attrs = ('Acquire', 'ArrayCounter', 'ArrayCounter_RBV',
                 'DetectorState_RBV',  'NumImages', 'ColorMode',
                 'DataType_RBV',  'Gain',
                 'AcquireTime', 'AcquirePeriod', 'ImageMode',
                 'MaxSizeX_RBV', 'MaxSizeY_RBV', 'TriggerMode',
                 'SizeX', 'SizeY', 'MinX', 'MinY')
    
    def __init__(self, parent, image_panel=None, prefix=None, **kws):
        super(ConfPanel_EpicsAD, self).__init__(parent, -1, size=(280, 300))

        self.wids = {}
        self.prefix = prefix
        if self.prefix.endswith(':'):
            self.prefix = self.prefix[:-1]
        if self.prefix.endswith(':image1'):
            self.prefix = self.prefix[:-7]
        if self.prefix.endswith(':cam1'):
            self.prefix = self.prefix[:-5]

        self.ad_img = Device(self.prefix + ':image1:',
                             delim='',  attrs=self.img_attrs)
        self.ad_cam = Device(self.prefix + ':cam1:',
                             delim='',  attrs=self.cam_attrs)


        self.SetBackgroundColour('#EEFFE')
        title =  wx.StaticText(self, size=(285, 25),
                               label="Epics AreaDetector: %s" % prefix)

        for key in ('imagemode', 'triggermode', 'color'):
            self.wids[key]   = PVEnumChoice(self, pv=None, size=(135, -1))
        for key in ('exptime', 'period', 'numimages', 'gain'):
            self.wids[key]   = PVFloatCtrl(self, pv=None, size=(135, -1), minval=0)
        self.wids['gain'].SetMax(20)

        for key in ('start', 'stop'):
            self.wids[key] = wx.Button(self, -1, label=key.title(), size=(65, -1))
            self.wids[key].Bind(wx.EVT_BUTTON, Closure(self.onButton, key=key))
        
        labstyle  = wx.ALIGN_LEFT|wx.EXPAND|wx.ALIGN_BOTTOM
        ctrlstyle = wx.ALIGN_LEFT #  |wx.ALIGN_BOTTOM
        rlabstyle = wx.ALIGN_RIGHT|wx.RIGHT|wx.TOP|wx.EXPAND
        txtstyle  = wx.ALIGN_LEFT|wx.ST_NO_AUTORESIZE|wx.TE_PROCESS_ENTER


        self.wids['fullsize']= wx.StaticText(self, -1,  size=(250,-1), style=txtstyle)

        def txt(label, size=100):
            return wx.StaticText(self, label=label, size=(size, -1), style=labstyle)

        def lin(len=30, wid=2, style=wx.LI_HORIZONTAL):
            return wx.StaticLine(self, size=(len, wid), style=style)

        sizer = wx.GridBagSizer(10, 4)
        sizer.SetVGap(5)
        sizer.SetHGap(5)
        
        sizer.Add(title,                    (0, 0), (1, 3), labstyle)
        sizer.Add(self.wids['fullsize'],    (1, 0), (1, 3), labstyle)
        sizer.Add(txt('Acquire '),          (2, 0), (1, 1), labstyle)
        sizer.Add(self.wids['start'],       (2, 1), (1, 1), ctrlstyle)
        sizer.Add(self.wids['stop'],        (2, 2), (1, 1), ctrlstyle)

        sizer.Add(txt('Image Mode '),       (3, 0), (1, 1), labstyle)
        sizer.Add(self.wids['imagemode'],   (3, 1), (1, 2), ctrlstyle)

        sizer.Add(txt('# Images '),         (4, 0), (1, 1), labstyle)
        sizer.Add(self.wids['numimages'],   (4, 1), (1, 2), ctrlstyle)

        sizer.Add(txt('Trigger Mode '),     (5, 0), (1, 1), labstyle)
        sizer.Add(self.wids['triggermode'], (5, 1), (1, 2), ctrlstyle)

        sizer.Add(txt('Period '),           (6, 0), (1, 1), labstyle)
        sizer.Add(self.wids['period'],      (6, 1), (1, 2), ctrlstyle)

        sizer.Add(txt('Exposure Time '),    (7, 0), (1, 1), labstyle)
        sizer.Add(self.wids['exptime'],     (7, 1), (1, 2), ctrlstyle)

        sizer.Add(txt('Gain '),             (8, 0), (1, 1), labstyle)
        sizer.Add(self.wids['gain'],        (8, 1), (1, 2), ctrlstyle)

        sizer.Add(txt('Color Mode'),        (9, 0), (1, 1), labstyle)
        sizer.Add(self.wids['color'],       (9, 1), (1, 2), ctrlstyle)
        
        pack(self, sizer)
        wx.CallAfter(self.connect_pvs )

    @EpicsFunction
    def connect_pvs(self, verbose=True):
        # print "Connect PVS"
        if self.prefix is None or len(self.prefix) < 2:
            return

        time.sleep(0.010)
        if not self.ad_img.PV('UniqueId_RBV').connected:
            poll()
            if not self.ad_img.PV('UniqueId_RBV').connected:
                self.messag('Warning:  Camera seems to not be connected!')
                return

        self.wids['color'].SetPV(self.ad_cam.PV('ColorMode'))
        self.wids['exptime'].SetPV(self.ad_cam.PV('AcquireTime'))
        self.wids['period'].SetPV(self.ad_cam.PV('AcquirePeriod'))
        self.wids['gain'].SetPV(self.ad_cam.PV('Gain'))
        self.wids['numimages'].SetPV(self.ad_cam.PV('NumImages'))
        self.wids['imagemode'].SetPV(self.ad_cam.PV('ImageMode'))
        self.wids['triggermode'].SetPV(self.ad_cam.PV('TriggerMode'))

        sizex = self.ad_cam.MaxSizeX_RBV
        sizey = self.ad_cam.MaxSizeY_RBV
        sizelabel = 'Image Size: %i x %i pixels'
        try:
            sizelabel = sizelabel  % (sizex, sizey)
        except:
            sizelabel = sizelabel  % (0, 0)

        self.wids['fullsize'].SetLabel(sizelabel)
        poll()

    @EpicsFunction
    def onButton(self, evt=None, key='name', **kw):
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
