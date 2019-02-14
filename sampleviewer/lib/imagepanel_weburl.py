"""Image Panel for Web cameras
"""

import wx
import time
import os
import numpy as np
from six import StringIO
# from six.moves.urllib.request import urlopen
import io
import urllib
from PIL import Image

from .imagepanel_base import ImagePanel_Base, ConfPanel_Base
from epics.wx.utils import  pack

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
        return io.BytesIO(urllib.request.urlopen(self.url).read())
    
    def Start(self):
        "turn camera on"
        self.timer.Start(65)
        #if self.autosave_thread is not None:
        #    self.autosave_thread.start()

    def Stop(self):
        "turn camera off"
        self.timer.Stop()
        self.autosave = False

    def GrabWxImage(self, scale=1, rgb=True, can_skip=True):
        try:
            wximage = wx.Image(self.read_url())
            time.sleep(0.025)
            # wximage = wx.ImageFromStream(StringIO(urlopen(self.url).read()))
            return wximage.Scale(int(scale*self.img_w), int(scale*self.img_h))
        except:
            pass

class ConfPanel_URL(ConfPanel_Base):
    def __init__(self, parent, url=None, center_cb=None, xhair_cb=None, **kws):
        super(ConfPanel_URL, self).__init__(parent, center_cb=center_cb,
                                            xhair_cb=xhair_cb,
                                            size=(280, 300))

        title =  wx.StaticText(self, label="Webcam Config", size=(285, 25))

        sizer = self.sizer # wx.BoxSizer(wx.VERTICAL)
        sizer.Add(title,       (0, 0), (1, 3),  wx.ALIGN_LEFT|wx.ALL)
        next_row = self.show_position_info(row=2)
        pack(self, sizer)
