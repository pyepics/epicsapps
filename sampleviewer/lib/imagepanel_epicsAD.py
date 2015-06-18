"""Image Panel for Epics AreaDetector
"""

import wx
import time
import os
import numpy as np

from epics import PV, Device, caput
from epics.wx import EpicsFunction

import Image
from .imagepanel_base import ImagePanel_Base
from epics.wx.utils import  pack
                            
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
    def __init__(self, parent, prefix=None, **kws):
        super(ConfPanel_EpicsAD, self).__init__(parent, -1, size=(280, 300))
        self.SetBackgroundColour('#EEDDEE')
        

        title =  wx.StaticText(self, label="Eics AD Config", size=(285, 25))

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(title,     0, wx.ALIGN_LEFT|wx.ALL)
        pack(self, sizer)
        
