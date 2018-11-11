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

class ADMonoImagePanel(wx.Panel):
    """Image Panel for monochromatic Area Detector"""

    ad_attrs = ('image1:ArrayData',
                'image1:ArraySize0_RBV',
                'image1:ArraySize1_RBV',
                'cam1:ArrayCounter_RBV')

    def __init__(self, parent, prefix=None, writer=None,
                 draw_objects=None,
                 rot90=0, contrast_level=0, size=(600, 600), **kws):
        super(ADMonoImagePanel, self).__init__(parent, -1, size=size)

        self.drawing = False
        self.adcam = None
        self.image_id = -1

        self.writer = writer
        self.scale = 0.8
        self.colormap = None
        self.contrast_levels = [contrast_level, 100.0-contrast_level]
        self.rot90 = rot90
        self.flipv = False
        self.fliph = False
        self.image = None
        self.draw_objects = None
        self.SetBackgroundColour("#E4E4E4")
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.Bind(wx.EVT_SIZE, self.onSize)
        self.Bind(wx.EVT_PAINT, self.onPaint)
        self.connect_pvs(prefix)
        self.restart_fps_counter()

    def restart_fps_counter(self, nsamples=100):
        self.capture_times = deque([], maxlen=nsamples)
        if self.writer is not None:
            self.writer("")

    def connect_pvs(self, prefix):
        if prefix.endswith(':'):
            prefix = prefix[:-1]
        if prefix.endswith(':image1'):
            prefix = prefix[:-7]
        if prefix.endswith(':cam1'):
            prefix = prefix[:-5]
        prefix = prefix + ':'

        self.adcam = Device(prefix,  delim='', attrs=self.ad_attrs)
        self.adcam.add_callback('cam1:ArrayCounter_RBV', self.onNewImage)

    def GetImageSize(self):
        return  (self.adcam.get('image1:ArraySize0_RBV'),
                 self.adcam.get('image1:ArraySize1_RBV'))

    def onNewImage(self, pvname=None, value=None, **kws):
        if value > self.image_id and not self.drawing:
            self.image_id = value
            self.Refresh()

    def GrabNumpyImage(self):
        """get raw image data, as numpy ndarray, correctly shaped"""
        try:
            data = self.adcam.PV('image1:ArrayData').get()
        except:
            data = None
        if data is not None:
            w, h = self.GetImageSize()
            data = data.reshape((h, w))
        return data

    def GrabWxImage(self):
        """get wx Image:
        - scaled in size
        - color table applied
        - flipped and/or rotated
        - contrast levels set
        """
        data = self.GrabNumpyImage()
        if data is None:
            return
        self.capture_times.append(time.clock())

        jmin, jmax = np.percentile(data, self.contrast_levels)
        data = (np.clip(data, jmin, jmax) - jmin)/(jmax+0.001)
        w, h = self.GetImageSize()

        if callable(self.colormap):
            data = self.colormap(data)
            if data.shape[2] == 4: # with alpha channel
                image = wx.Image(w, h,
                                 (data[:,:,:3]*255.).astype('uint8'),
                                 (data[:,:,3]*255.).astype('uint8'))
            else:
                image = wx.Image(w, h, (data*255.).astype('uint8'))
        else:
            rgb = np.zeros((h, w, 3), dtype='float')
            rgb[:, :, 0] = rgb[:, :, 1] = rgb[:, :, 2] = data
            image = wx.Image(w, h, (rgb*255.).astype('uint8'))

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
