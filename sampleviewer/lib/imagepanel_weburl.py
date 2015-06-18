"""Image Panel for Web cameras
"""

import wx
import time
import os
import numpy as np
from  cStringIO import StringIO
from  urllib import urlopen


import Image
from .imagepanel_base import ImagePanel_Base

class ImagePanel_URL(ImagePanel_Base):
    """Image Panel for webcam"""
    def __init__(self, parent, url, writer=None, autosave_file=None, **kws):
        super(ImagePanel_URL, self).__init__(parent, -1, size=(800, 600))

        self.url = url
        stream  = StringIO(urlopen(self.url).read())
        pil_image = Image.open(stream)
        width, height = pil_image.size

        self.writer = writer
        self.img_w = float(width+0.5)
        self.img_h = float(height+0.5)
        self.cam_name = url
        self.imgcount = 0
        self.imgcount_start = 0
        self.last_update = 0.0
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.onTimer, self.timer)

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


    def GrabWxImage(self, scale=1, rgb=True):
        stream  = StringIO(urlopen(self.url).read())
        wximage = wx.ImageFromStream(stream)
        return wximage.Scale(int(scale*self.img_w), int(scale*self.img_h))
