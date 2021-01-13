"""
Image Panel for JPEG Images sent over ZeroMQ
as published by the default ImagePanel
"""

import wx
import time
import os
import sys
import json
import numpy as np
import io
import zmq
import base64

from PIL import Image

from wxutils import  pack

from .imagepanel_base import ImagePanel_Base, ConfPanel_Base

class ImagePanel_ZMQ(ImagePanel_Base):
    """Image Panel for JPEGs sent by ZeroMQ"""
    def __init__(self, parent, host=None, port=17166, **kws):
        super(ImagePanel_ZMQ, self).__init__(parent, -1,
                                                 size=(800, 600),
                                                 publish_jpeg=False)
        self.ctx = zmq.Context()
        self.connstr = "tcp://%s:%s" % (host, port)
        self.socket = self.ctx.socket(zmq.REQ)
        self.socket.setsockopt(zmq.SNDTIMEO, 500)
        self.socket.setsockopt(zmq.RCVTIMEO, 500)
        self.socket.setsockopt(zmq.LINGER, 500)
        self.socket.setsockopt(zmq.CONNECT_TIMEOUT, 500)

        self.socket.connect(self.connstr)
        self.connected = True
        
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.onTimer, self.timer)

        self.Start()
        
    def connect(self):
        if self.host is None or self.port is None:
            return 
        self.connected = True
        time.sleep(1)
        
    def reconnect(self):
        self.socket.close()

        self.socket = self.ctx.socket(zmq.REQ)
        self.socket.setsockopt(zmq.RCVTIMEO, 500)
        self.socket.setsockopt(zmq.LINGER, 0)
        self.socket.setsockopt(zmq.CONNECT_TIMEOUT, 500)
        self.socket.connect(self.connstr)
    
        
    def Start(self):
        "turn camera on"
        self.timer.Start(100)

    def Stop(self):
        "turn camera off"
        self.timer.Stop()
        self.autosave = False

    def GrabWxImage(self, scale=1, rgb=True, can_skip=True):
        if not self.connected:
            return
        time.sleep(0.1)
        try:
            self.socket.send(b'send image')
            sdata = self.socket.recv_json()
        except:
            et, ev, tb = sys.exc_info()
            print("Failed to get image: ", et, ev)
            time.sleep(2)
            return None
            

        # print(" -> Grab Imag: got data: ", sdata.keys())        
        imgdat = sdata.get('image', None)
        if imgdat is None:
            print("no image")
            return
        tmp = io.BytesIO()
        tmp.write(base64.b64decode(imgdat.encode('utf-8')))
        tmp.seek(0)
        wximage = wx.Image(tmp)
        return wximage.Scale(int(scale*self.img_w), int(scale*self.img_h))

class ConfPanel_ZMQ(ConfPanel_Base):
    def __init__(self, parent, url=None, center_cb=None, xhair_cb=None, **kws):
        super(ConfPanel_ZMQ, self).__init__(parent, center_cb=center_cb,
                                            xhair_cb=xhair_cb,
                                            size=(280, 300))

        title =  wx.StaticText(self, label="JPEG Config", size=(285, 25))

        sizer = self.sizer
        sizer.Add(title,       (0, 0), (1, 3),  wx.ALIGN_LEFT|wx.ALL)
        next_row = self.show_position_info(row=2)
        pack(self, sizer)
