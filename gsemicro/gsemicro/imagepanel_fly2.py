"""Image Panel using direct connection to Fly2 API
   for Point Grey FlyCapture2 cameras
"""

import wx
import time
import os
import shutil

from cStringIO import StringIO
import base64

import pyfly2

AUTOSAVE_DIR  = "//cars5/Data/xas_user"
AUTOSAVE_TMP  = os.path.join(AUTOSAVE_DIR, '_tmp_.jpg')
AUTOSAVE_FILE = os.path.join(AUTOSAVE_DIR, 'IDEuscope_Live.jpg')

IMG_W, IMG_H  = 1928, 1448

class ImagePanel(wx.Panel):
    """Image Panel for FlyCapture2 camera"""
    def __init__(self, camera_id=0, writer=None):
        super(ImagePanel, self).__init__(parent,  -1, size=(990, 745))

        self.context = pyfly2.Context()
        self.camera = self.context.get_camera(camera_id)

        self.writer = writer
        self.cam_name = '-'
        self.update_rate = update_rate
        self.count = 0
        self.fps   = 0.0
        self.scalebar = False
        self.centerpoint = False
        self.scale = 0.60
        self.SetBackgroundColour("#EEEEEE")
        self.starttime = time.clock()
        self.last_autosave = 0
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_SIZE, self.onSize)
        self.Bind(wx.EVT_PAINT, self.onPaint)
        self.Bind(wx.EVT_TIMER, self.onTimer, self.timer)
        self.timer.Start(50)

    def onSize(self, evt):
        frame_w, frame_h = evt.GetSize()
        self.scale = min(frame_w*1.01/IMG_W, frame_h*1.01/IMG_H)
        self.Refresh()
        evt.Skip()

    def onTimer(self, event=None):
        self.Refresh()

    def onPaint(self, event):
        self.count += 1
        now = time.clock()
        elapsed = now - self.starttime
        if elapsed >= 1.0 and self.writer is not None:
            self.fps = self.count / elapsed
            self.writer(" %.2f fps\n" % (self.fps))
            self.starttime = now
            self.count = 0
        if self.scale < 0.2: self.scale=0.2
        self.image = self.camera.GrabWxImage(scale=self.scale, rgb=True)
        bitmap = wx.BitmapFromImage(self.image)

        img_w, img_h =  bitmap.GetSize()
        pan_w, pan_h =  self.GetSize()
        pad_w, pad_h = (pan_w-img_w)/2.0, (pan_h-img_h)/2.0

        dc = wx.AutoBufferedPaintDC(self)
        dc.Clear()
        dc.DrawBitmap(bitmap, pad_w, pad_h, useMask=True)
        dc.BeginDrawing()
        if self.scalebar is not None:
            x0, x1, y0, y1, color, width = self.scalebar
            dc.SetPen(wx.Pen('Red', 1.5, wx.SOLID))
            dc.DrawLine(x0, y0, x1, y1)
        if self.scalebar is not None:
            x0, x1, y0, y1, color, width = self.scalebar
            # x0, y0, x1, y1 = img_w-20, img_h-60, img_w-200, img_h-60
            # color = 'Red', width=1.5
            dc.SetPen(wx.Pen(color, width, wx.SOLID))
            dc.DrawLine(x0, y0, x1, y1)

        dc.EndDrawing()

        now = time.clock()
        if (now - self.last_autosave)  > 1.0:
            try:
                self.image.SaveFile(AUTOSAVE_TMP, wx.BITMAP_TYPE_JPEG)
                self.last_autosave = now
                shutil.copy(AUTOSAVE_TMP, AUTOSAVE_FILE)
            except:
                pass

    def Start(self):
        "turn on the camera"
        self.camera.Connect()
        self.cam_name = self.camera.info['modelName']
        self.camera.StartCapture()

    def Stop(self):
        self.camera.StopCapture()

    def SaveImage(self, fname, filetype='jpeg'):
        """save image (jpeg) to file"""
        ftype = wx.BITMAP_TYPE_JPEG
        if filetype.lower() == 'png':
            ftype = wx.BITMAP_TYPE_PNG
        elif filetype.lower() in ('tiff', 'tif'):
            ftype = wx.BITMAP_TYPE_TIFF
        self.image.SaveFile(fname, ftype)
        return self.GrabImage()

    def GrabImage(self):
        """return base64 encoded image data"""
        return base64.b4encode(self.image.GetData())
