"""Image Panel for Web cameras
"""

import wx
import time
import os
import io
import urllib
import requests

import numpy as np

from PIL import Image

from wxutils import  pack

from .imagepanel_base import ImagePanel_Base, ConfPanel_Base

class ImagePanel_URL(ImagePanel_Base):
    """Image Panel for webcam"""
    def __init__(self, parent, url=None, writer=None, autosave_file=None, **kws):
        super(ImagePanel_URL, self).__init__(parent, -1,
                                             size=(800, 600),
                                             writer=writer,
                                             autosave_file=autosave_file, **kws)

        self.url = url
        pil_image = Image.open(self.read_url())
        width, height = pil_image.size

        self.img_w = float(width+0.5)
        self.img_h = float(height+0.5)
        self.img_size = (width, height)
        self.cam_name = url
        self.imgcount = 0
        self.imgcount_start = 0
        self.last_update = 0.0
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.onTimer, self.timer)

    def read_url(self):
        return io.BytesIO(requests.get(self.url).content)

    def Start(self):
        "turn camera on"
        self.timer.Start(65)
        #if self.autosave_thread is not None:
        #    self.autosave_thread.start()

    def Stop(self):
        "turn camera off"
        self.timer.Stop()
        self.autosave = False

    def GrabNumpyImage(self):
        pimg = Image.open(self.read_url())
        self.data = np.array(pimg.getdata()).reshape(pimg.size[0], pimg.size[1], 3)
        return self.data

    def GrabWxImage(self, scale=1, rgb=True, can_skip=True):
        try:
            wximage = wx.Image(self.read_url())
            time.sleep(0.025)
            return wximage.Scale(int(scale*self.img_w), int(scale*self.img_h))
        except:
            pass

class ConfPanel_URL(ConfPanel_Base):
    def __init__(self, parent, url=None, center_cb=None, xhair_cb=None, **kws):
        super(ConfPanel_URL, self).__init__(parent, center_cb=center_cb,
                                            xhair_cb=xhair_cb,
                                            size=(280, 300))

        super(ConfPanel_URL, self).__init__(parent, center_cb=center_cb,
                                             xhair_cb=xhair_cb, **kws)
        title =  wx.StaticText(self, label="Webcam Config", size=(285, 25))

        sizer = self.sizer # wx.BoxSizer(wx.VERTICAL)
        sizer.Add(title,       (0, 0), (1, 3),  wx.ALIGN_LEFT|wx.ALL)
        next_row = self.show_position_info(row=2)
        pack(self, sizer)
