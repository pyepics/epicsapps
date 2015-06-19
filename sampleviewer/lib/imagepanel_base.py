"""
Base Image Panel to be inherited by other ImagePanels
"""

import wx
import time
import os
import shutil
import math
from threading import Thread
from cStringIO import StringIO
import base64

class ImagePanel_Base(wx.Panel):
    """Image Panel for FlyCapture2 camera"""

    def Start(self):
        "turn camera on"
        raise NotImplementedError('must provide Start()')

    def Stop(self):
        "turn camera off"
        raise NotImplementedError('must provide Stop()')

    def GrabWxImage(self, scale=1, rgb=True):
        "grab Wx Image, with scale and rgb=True/False"
        raise NotImplementedError('must provide GrabWxImage()')


    def __init__(self, parent,  camera_id=0, writer=None,
                 autosave_file=None, **kws):
        super(ImagePanel_Base, self).__init__(parent, -1, size=(800, 600))
        self.img_w = 800.5
        self.img_h = 600.5
        self.writer = writer
        self.cam_name = '-'
        self.scale = 0.60
        self.count = 0

        self.scalebar = None
        self.circle  = None
        self.SetBackgroundColour("#EEEEEE")
        self.starttime = time.clock()
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)

        self.Bind(wx.EVT_SIZE, self.onSize)
        self.Bind(wx.EVT_PAINT, self.onPaint)
        self.Bind(wx.EVT_LEFT_DOWN, self.onLeftDown)

        self.autosave = True
        self.last_autosave = 0
        self.autosave_tmpf = None
        self.autosave_file = None
        self.autosave_thread = None
        self.full_size = None
        if autosave_file is not None:
            path, tmp = os.path.split(autosave_file)
            self.autosave_file = autosave_file
            self.autosave_tmpf = os.path.join(path, '_tmp_.jpg')
            self.autosave_thread = Thread(target=self.onAutosave)
            self.autosave_thread.daemon = True

    def onSize(self, evt):
        frame_w, frame_h = evt.GetSize()
        self.scale = min(frame_w/self.img_w, frame_h/self.img_h)
        self.Refresh()
        evt.Skip()

    def onTimer(self, evt=None):
        self.Refresh()

    def onLeftDown(self, evt=None):
        """
        report left down events within image
        """
        evt_x, evt_y = evt.GetX(), evt.GetY()
        max_x, max_y = self.full_size
        img_w, img_h = self.bitmap_size
        pan_w, pan_h = self.panel_size
        pad_w, pad_h = (pan_w-img_w)/2.0, (pan_h-img_h)/2.0

        x = int(0.5 + (evt_x - pad_w)/self.scale)
        y = int(0.5 + (evt_y - pad_h)/self.scale)
        fmt  = 'LeftDown at Pixel (%i, %i) of (%i, %i)'
        if x > 0 and x < max_x and y > 0 and y < max_y:
            print fmt % (x, y, max_x, max_y)
        return (x, y)

    def onPaint(self, event):
        self.count += 1
        now = time.clock()
        elapsed = now - self.starttime
        if elapsed >= 2.0 and self.writer is not None:
            self.writer(" %.2f fps\n" % (self.count/elapsed))
            self.starttime = now
            self.count = 0

        self.scale = max(self.scale, 0.05)
        self.image = self.GrabWxImage(scale=self.scale, rgb=True)
        if self.full_size is None:
            img = self.GrabWxImage(scale=1.0, rgb=True)            
            self.full_size = img.GetSize()
            
        try:
            bitmap = wx.BitmapFromImage(self.image)
        except ValueError:
            return

        img_w, img_h = self.bitmap_size = bitmap.GetSize()
        pan_w, pan_h = self.panel_size = self.GetSize()
        pad_w, pad_h = (pan_w-img_w)/2.0, (pan_h-img_h)/2.0

        dc = wx.AutoBufferedPaintDC(self)
        dc.Clear()
        dc.DrawBitmap(bitmap, pad_w, pad_h, useMask=True)
        dc.BeginDrawing()
        if self.scalebar is not None:
            x0, x1, y0, y1, color, width = self.scalebar
            # x0, y0, x1, y1 = img_w-20, img_h-60, img_w-200, img_h-60
            # color = 'Red', width=1.5
            dc.SetPen(wx.Pen('Red', 1.5, wx.SOLID))
            dc.DrawLine(x0, y0, x1, y1)
        if self.circle is not None:
            x0, y0, rad, color, width = self.circle
            dc.SetPen(wx.Pen(color, width, wx.SOLID))
            dc.DrawCircle(x0, y0, rad)
        dc.EndDrawing()

    def onAutosave(self):
        "autosave process, run in separate thread"
        # set autosave to False to abort autosaving
        while self.autosave:
            tfrac, tint = math.modf(time.time())
            if tint != self.last_autosave:
                self.last_autosave = tint
                try:
                    self.image.SaveFile(self.autosave_tmpf,
                                        wx.BITMAP_TYPE_JPEG)
                    shutil.copy(self.autosave_tmpf, self.autosave_file)
                except:
                    pass
                tfrac, tint = math.modf(time.time())
            # sleep for most of the remaining second
            time.sleep(max(0.05, 0.75*(1.0-tfrac)))


    def SaveImage(self, fname, filetype='jpeg'):
        """save image (jpeg) to file,
        return dictionary of image data, suitable for serialization
        """
        ftype = wx.BITMAP_TYPE_JPEG
        if filetype.lower() == 'png':
            ftype = wx.BITMAP_TYPE_PNG
        elif filetype.lower() in ('tiff', 'tif'):
            ftype = wx.BITMAP_TYPE_TIFF
        tmpimage = self.GrabWxImage(scale=1, rgb=True)
        tmpimage.SaveFile(fname, ftype)
        return self.image2dict(tmpimage)

    def image2dict(self, img=None):
        "return dictionary of image data, suitable for serialization"
        if img is None:
            img = self.GrabWxImage(scale=1, rgb=True)
        _size = img.GetSize()
        size = (_size[0], _size[1])
        return {'image_size': size, 
                'image_format': 'RGB', 
                'data_format': 'base64',
                'data': base64.b64encode(img.GetData())}
