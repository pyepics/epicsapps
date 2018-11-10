"""
Base Image Panel to be inherited by other ImagePanels
"""

import wx
import time
import numpy as np
import os
import shutil
import math
from threading import Thread
from six import StringIO
import base64
from collections import deque
from epics import PV, Device, caput, poll
from epics.wx import EpicsFunction, DelayedEpicsCallback

from matplotlib.cm import coolwarm, viridis, gray, coolwarm_r, viridis_r, gray_r

class ADImagePanel(wx.Panel):
    """Image Panel for Area Detector"""

    img_attrs = ('ArrayData', 'UniqueId_RBV', 'NDimensions_RBV',
                 'ArraySize0_RBV', 'ArraySize1_RBV', 'ArraySize2_RBV',
                 'ColorMode_RBV')

    cam_attrs = ('Acquire', 'ArrayCounter', 'ArrayCounter_RBV',
                 'DetectorState_RBV', 'NumImages', 'ColorMode',
                 'ColorMode_RBV', 'DataType_RBV', 'Gain', 'AcquireTime',
                 'AcquirePeriod', 'ImageMode', 'ArraySizeX_RBV',
                 'ArraySizeY_RBV')

    def __init__(self, parent, prefix=None, writer=None,
                 draw_objects=None,
                 rot90=0, contrast_level=0, **kws):
        self.drawing = False
        super(ADImagePanel, self).__init__(parent, -1, size=(400, 750))
        self.prefix = prefix
        self.image_id = -1
        self.writer = writer
        self.scale = 0.8
        self.ad_img = None
        self.arrsize   = (0, 0, 0)
        self.contrast_levels = [contrast_level, 100.0-contrast_level]
        self.rot90 = rot90
        self.flipv = False
        self.fliph = False
        self.image = None
        self.draw_objects = None
        self.SetBackgroundColour("#E4E4E4")
        self.starttime = time.clock()
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.Bind(wx.EVT_SIZE, self.onSize)
        self.Bind(wx.EVT_PAINT, self.onPaint)

        self.set_prefix(prefix)
        self.restart_fps_counter()

    def restart_fps_counter(self, nsamples=100):
        self.capture_times = deque([], maxlen=nsamples)
        if self.writer is not None:
            self.writer("")

    def set_prefix(self, prefix):
        if prefix.endswith(':'):
            prefix = prefix[:-1]
        if prefix.endswith(':image1'):
            prefix = prefix[:-7]
        if prefix.endswith(':cam1'):
            prefix = prefix[:-5]
        self.prefix = prefix

        self.ad_img = Device(prefix + ':image1:', delim='', attrs=self.img_attrs)
        self.ad_cam = Device(prefix + ':cam1:', delim='', attrs=self.cam_attrs)

        self.ad_cam._pvs['ArrayCounter_RBV'].add_callback(self.onNewImage)
        self.ad_img.add_callback('ArraySize0_RBV', self.onArraySize, dim=0)
        self.ad_img.add_callback('ArraySize1_RBV', self.onArraySize, dim=1)

    def GetImageSize(self):
        return self.ad_img.ArraySize0_RBV, self.ad_img.ArraySize1_RBV

    def onNewImage(self, pvname=None, value=None, **kws):
        if value > self.image_id and not self.drawing:
            self.image_id = value
            self.Refresh()

    @DelayedEpicsCallback
    def onArraySize(self, pvname=None, value=None, dim=None, **kw):
        self.arrsize[dim] = value

    def GrabWxImage(self):
        try:
            data = self.ad_img.PV('ArrayData').get()
        except:
            return
        if data is None:
            return
        self.capture_times.append(time.time())

        jmin, jmax = np.percentile(data, self.contrast_levels)
        data = np.clip(data, jmin, jmax) - jmin
        data = (data*255./(jmax+0.001)).astype('uint8')

        w, h = self.GetImageSize()
        data = data.reshape((h, w))

        rgb = np.zeros((h, w, 3), dtype='uint8')
        rgb[:, :, 0] = rgb[:, :, 1] = rgb[:, :, 2] = data

        image = wx.Image(w, h, rgb)
        if self.flipv:
            image = image.Mirror(False)
        if self.fliph:
            image = image.Mirror(True)
        if self.rot90 != 0:
            for i in range(self.rot90):
                image = image.Rotate90(True)
                w, h = h, w
        return image.Scale(int(self.scale*w), int(self.scale*h))

    def onSize(self, evt=None):
        if evt is not None:
            fh, fw = evt.GetSize()
        else:
            fh, fw = self.GetSize()
        w, h = self.GetImageSize()
        self.scale = max(0.10, min(fw/(w+5.0), fh/(h+5.0)))

    def onPaint(self, event):
        self.drawing = True
        image = self.GrabWxImage()
        if image is not None:
            if len(self.capture_times) > 2 and self.writer is not None:
                ct = self.capture_times
                fps = (ct[-1]-ct[0]) / (len(ct)-1)
                self.writer("Image %d: %.1f fps" % (self.image_id, fps))

            bitmap = wx.Bitmap(image)
            bmp_w, bmp_h = bitmap.GetSize()
            pan_w, pan_h = self.GetSize()
            pad_w, pad_h = int(1+(pan_w-bmp_w)/2.0), int(1+(pan_h-bmp_h)/2.0)
            dc = wx.AutoBufferedPaintDC(self)
            dc.Clear()
            dc.DrawBitmap(bitmap, pad_w, pad_h, useMask=True)
            # self.__draw_objects(dc, img_w, img_h, pad_w, pad_h)
        self.drawing = False

    def __draw_objects(self, dc, img_w, img_h, pad_w, pad_h):
        dc.SetBrush(wx.Brush('Black', wx.BRUSHSTYLE_TRANSPARENT))
        if self.draw_objects is not None:
            for obj in self.draw_objects:
                shape = obj.get('shape', None)
                color = obj.get('color', None)
                if color is None:
                    color = obj.get('colour', 'Black')
                color = wx.Colour(*color)
                width = obj.get('width', 1.0)
                style = obj.get('style', wx.SOLID)
                args  = obj.get('args', [])
                kws   = obj.get('kws', {})

                method = getattr(dc, 'Draw%s' % (shape.title()), None)
                if shape.title() == 'Line':
                    args = [pad_w + args[0]*img_w,
                            pad_h + args[1]*img_h,
                            pad_w + args[2]*img_w,
                            pad_h + args[3]*img_h]
                elif shape.title() == 'Circle':
                    args = [pad_w + args[0]*img_w,
                            pad_h + args[1]*img_h,  args[2]*img_w]

                if method is not None:
                    dc.SetPen(wx.Pen(color, width, style))
                    method(*args, **kws)
