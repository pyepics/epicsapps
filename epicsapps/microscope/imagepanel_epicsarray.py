"""Image Panel for Epics AreaDetector
"""

import wx
import time
import os
import numpy as np
from functools import partial
from epics import PV, Device, caput, poll

from epics.wx import DelayedEpicsCallback, EpicsFunction
from epics.wx import PVEnumChoice, PVFloatCtrl, PVTextCtrl

from PIL import Image

from .imagepanel_base import ImagePanel_Base, ConfPanel_Base

from wxutils import pack, Button

class ImagePanel_EpicsArray(ImagePanel_Base):
    img_attrs = ('ArrayData', 'UniqueId_RBV', 'NDimensions_RBV',
                 'ArraySize0_RBV', 'ArraySize1_RBV', 'ArraySize2_RBV',
                 'ColorMode_RBV', 'RequestTStamp', 'PublishTStamp')

    """Image Panel for Simple Array pushed by PushEpics"""
    def __init__(self, parent, prefix=None, format='JPEG',
                 writer=None, autosave_file=None, **kws):
        ImagePanel_Base.__init__(self, parent, -1,
                                 size=(800, 600),
                                 writer=writer,
                                 autosave_file=autosave_file, **kws)

        self.format = format
        self.set_prefix(prefix)
        self.imgcount = 0
        self.imgcount_start = 0
        self.last_update = 0.0

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.onTimer, self.timer)

    def set_prefix(self, prefix):
        if prefix.endswith(':'):         prefix = prefix[:-1]
        if prefix.endswith(':image1'):   prefix = prefix[:-7]
        self.prefix = prefix

        self.ad_img = Device(prefix + ':image1:', delim='',
                                   attrs=self.img_attrs)
        w, h = self.GetImageSize()
        self.cam_name = prefix

    def config_filesaver(self, prefix, format):
        if not prefix.endswith(':'):  prefix = "%s:" % prefix
        if not format.endswith('1'):  format = "%s1" % format
        if not format.endswith('1:'): format = "%s:" % format
        pass

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
        arrsize0 = self.ad_img.ArraySize0_RBV
        arrsize1 = self.ad_img.ArraySize1_RBV
        arrsize2 = self.ad_img.ArraySize2_RBV
        self.arrsize   = (arrsize0, arrsize1, arrsize2)
        self.colormode = self.ad_img.ColorMode_RBV

        w, h = arrsize0, arrsize1
        if self.ad_img.NDimensions_RBV == 3:
            w, h  = arrsize1, arrsize2
        self.img_w = float(w+0.5)
        self.img_h = float(h+0.5)
        return w, h

    def GrabNumpyImage(self):
        width, height = self.GetImageSize()

        im_mode = 'L'
        self.im_size = (self.arrsize[0], self.arrsize[1])
        if self.ad_img.ColorMode_RBV == 2:
            im_mode = 'RGB'
            self.im_size = (self.arrsize[1], self.arrsize[2])

        dcount = self.arrsize[0] * self.arrsize[1]
        if self.ad_img.NDimensions_RBV == 3:
            dcount *= self.arrsize[2]

        img = self.ad_img.PV('ArrayData').get(count=dcount)
        if img is None:
            time.sleep(0.025)
            img = self.ad_img.PV('ArrayData').get(count=dcount)

        if self.ad_img.ColorMode_RBV == 2:
            img = img.reshape((width, height, 3)).sum(axis=2)
        else:
            img = img.reshape((width, height))
        return img

    def GrabWxImage(self, scale=1, rgb=True, can_skip=True):
        if self.ad_img is None:
            print('GrabWxImage .. no ad_img ', self.ad_img)
            return

        # imgcount = self.ad_cam.ArrayCounter_RBV
        now = time.time()
        if (can_skip and (imgcount == self.imgcount or
                          abs(now - self.last_update) < 0.025)):
            return None
        rawdata = self.GetNumpyImage()
        if rawdata is None:
            return

        self.imgcount = imgcount
        self.last_update = time.time()

        if (self.ad_img.ColorMode_RBV == 0 and
            isinstance(rawdata, np.ndarray) and
            rawdata.dtype != np.uint8):
            im_mode = 'I'
            rawdata = rawdata.astype(np.uint32)
        if im_mode in ('L', 'I'):
            image = wx.EmptyImage(width, height)
            imbuff = Image.frombuffer(im_mode, self.im_size, rawdata,
                                      'raw',  im_mode, 0, 1)
            image.SetData(imbuff.convert('RGB').tobytes())
        elif im_mode == 'RGB':
            rawdata.shape = (3, width, height)
            rawdata = rawdata.astype(np.uint8)
            image = wx.Image(width, height, rawdata)
        return image.Scale(int(scale*width), int(scale*height))

class ConfPanel_EpicsArray(ConfPanel_Base):
    def __init__(self, parent, url=None, center_cb=None, xhair_cb=None, **kws):
        super(ConfPanel_ZMQ, self).__init__(parent, center_cb=center_cb,
                                            xhair_cb=xhair_cb,
                                            size=(280, 300))

        title =  wx.StaticText(self, label="Epics Array", size=(285, 25))

        sizer = self.sizer
        sizer.Add(title,       (0, 0), (1, 3),  wx.ALIGN_LEFT|wx.ALL)
        next_row = self.show_position_info(row=2)
        pack(self, sizer)
