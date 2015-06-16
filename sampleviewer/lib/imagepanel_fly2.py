"""Image Panel using direct connection to Fly2 API
   for Point Grey FlyCapture2 cameras
"""

import wx
import time

from .imagepanel_base import ImagePanel_Base

HAS_FLY2 = False
try:
    import pyfly2
    HAS_FLY2 = True
except ImportError:
    pass

class ImagePanel_Fly2(ImagePanel_Base):
    """Image Panel for FlyCapture2 camera"""
    def __init__(self, parent,  camera_id=0, writer=None,
                 autosave_file=None, **kws):
        super(ImagePanel_Fly2, self).__init__(parent, -1, size=(800, 600))
        # 964, 724))

        self.context = pyfly2.Context()
        self.camera = self.context.get_camera(camera_id)
        self.img_w = 800.5
        self.img_h = 600.5
        self.writer = writer
        self.cam_name = '-'

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.onTimer, self.timer)

    def Start(self):
        "turn camera on"
        self.camera.Connect()
        self.cam_name = self.camera.info['modelName']
        self.camera.StartCapture()

        width, height = self.camera.GetSize()
        self.img_w = float(width+0.5)
        self.img_h = float(height+0.5)

        self.timer.Start(50)
        if self.autosave_thread is not None:
            self.autosave_thread.start()

    def Stop(self):
        "turn camera off"
        self.timer.Stop()
        self.autosave = False
        self.camera.StopCapture()
        if self.autosave_thread is not None:
            self.autosave_thread.join()

    def GrabWxImage(self, scale=1, rgb=True):
        return self.camera.GrabWxImage(scale=scale, rgb=rgb)

