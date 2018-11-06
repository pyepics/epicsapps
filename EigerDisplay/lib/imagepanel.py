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

    def __init__(self, parent, prefix=None, writer=None, leftdown_cb=None,
                 motion_cb=None, draw_objects=None, callback=None,
                 rot90=0, contrast_level=0, **kws):
        super(ADImagePanel, self).__init__(parent, -1, size=(400, 750))
        self.prefix = prefix
        self.img_w = 800.
        self.img_h = 600.
        self.writer = writer
        self.leftdown_cb = leftdown_cb
        self.motion_cb   = motion_cb
        self.scale = 0.60
        self.arrsize   = (0, 0, 0)
        self.contrast_levels = [contrast_level, 100.0-contrast_level]
        self.count = -1
        self.img_id = -1
        self.rot90 = rot90
        self.flipv = False
        self.fliph = False
        self.image = None
        self.drawing = False
        self.draw_objects = None
        self.callback = None
        self.SetBackgroundColour("#E4E4E4")
        self.starttime = time.clock()
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)

        self.Bind(wx.EVT_SIZE, self.onSize)
        self.Bind(wx.EVT_PAINT, self.onPaint)
        if self.leftdown_cb is not None:
            self.Bind(wx.EVT_LEFT_DOWN, self.onLeftDown)
        if self.motion_cb is not None:
            self.Bind(wx.EVT_MOTION, self.onMotion)

        self.data = None
        self.data_shape = (0, 0, 0)
        self.full_image = None
        self.full_size = None

        self.set_prefix(prefix)
        self.imgcount = 0
        self.imgcount_start = 0
        self.last_update = 0.0

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
        arrsize0 = self.ad_img.ArraySize0_RBV
        arrsize1 = self.ad_img.ArraySize1_RBV
        arrsize2 = self.ad_img.ArraySize2_RBV
        self.arrsize   = (arrsize0, arrsize1, arrsize2)
        self.colormode = self.ad_img.ColorMode_RBV

        w, h = arrsize0, arrsize1
        if self.ad_img.NDimensions_RBV == 3:
            w, h  = arrsize1, arrsize2
        self.img_w = float(w+0.05)
        self.img_h = float(h+0.05)
        return w, h

    def onNewImage(self, pvname=None, value=None, **kws):
        if value != self.img_id:
            self.img_id = value
            if not self.drawing:
                self.Refresh()

    @DelayedEpicsCallback
    def onArraySize(self, pvname=None, value=None, dim=None, **kw):
        self.arrsize[dim] = value

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

    def GrabWxImage(self, scale=1):
        if self.ad_img is None or self.ad_cam is None:
            return
        self.GetImageSize()
        imgcount = self.ad_cam.ArrayCounter_RBV
        now = time.time()
        if (imgcount == self.imgcount or abs(now - self.last_update) < 0.025):
            return None

        self.imgcount = imgcount
        self.last_update = time.time()

        im_mode = 'L'
        im_size = (self.arrsize[1], self.arrsize[0])
        imdata = None
        try:
            imdata = self.ad_img.PV('ArrayData').get(count=im_size[0]*im_size[1])
            imdata = imdata.reshape(im_size)
        except:
            return None
        if self.contrast_levels is not None:
            try:
                jmin, jmax = np.percentile(imdata, self.contrast_levels)
                imdata = np.clip(imdata, jmin, jmax)
            except:
                return

        imin, imax = 1.0*imdata.min(), 1.0*imdata.max()+1.e-9
        rgb = np.zeros((im_size[0], im_size[1], 3), dtype='uint8')
        rgb[:, :, 0] = (255*(imdata - imin)/(imax-imin)).astype('uint8')
        rgb[:, :, 1] = rgb[:, :, 2] = rgb[:, :, 0]
        image = wx.Image(self.img_w, self.img_h, rgb)

        if self.flipv:
            image = image.Mirror(False)
        if self.fliph:
            image = image.Mirror(True)
        if self.rot90 != 0:
            for i in range(self.rot90):
                image = image.Rotate90(True)
                self.img_w, self.img_h = self.img_h, self.img_w
        return image.Scale(int(scale*self.img_w), int(scale*self.img_h))

    def onSize(self, evt=None):
        if evt is not None:
            frame_w, frame_h = evt.GetSize()
        else:
            frame_w, frame_h = self.GetSize()
        self.scale = min(frame_w/self.img_w, frame_h/self.img_h)

    def onLeftDown(self, evt=None):
        """
        report left down events within image
        """
        if self.leftdown_cb is None:
            return

        evt_x, evt_y = evt.GetX(), evt.GetY()
        max_x, max_y = self.full_size
        img_w, img_h = self.bitmap_size
        pan_w, pan_h = self.panel_size
        pad_w, pad_h = (pan_w-img_w)/2.0, (pan_h-img_h)/2.0

        x = int(0.5 + (evt_x - pad_w)/self.scale)
        y = int(0.5 + (evt_y - pad_h)/self.scale)
        self.leftdown_cb(x, y, xmax=max_x, ymax=max_y)

    def onMotion(self, evt=None):
        """
        report left down events within image
        """
        if self.motion_cb is None or self.full_size is None:
            return
        evt_x, evt_y = evt.GetX(), evt.GetY()
        max_x, max_y = self.full_size
        img_w, img_h = self.bitmap_size
        pan_w, pan_h = self.panel_size
        pad_w, pad_h = (pan_w-img_w)/2.0, (pan_h-img_h)/2.0

        x = int(0.5 + (evt_x - pad_w)/self.scale)
        y = int(0.5 + (evt_y - pad_h)/self.scale)
        self.motion_cb(x, y, xmax=max_x, ymax=max_y)

    def onPaint(self, event):
        self.count += 1
        self.drawing = True

        now = time.clock()
        elapsed = now - self.starttime
        if elapsed >= 2.0 and self.writer is not None:
            self.writer("  %.2f fps" % (self.count/elapsed))
            self.starttime = now
            self.count = 0

        self.scale = max(self.scale, 0.05)
        self.image = self.GrabWxImage(scale=self.scale)
        if self.image is not None:
            self.full_size = self.image.GetSize()
            bitmap = wx.Bitmap(self.image)
            img_w, img_h = self.bitmap_size = bitmap.GetSize()
            pan_w, pan_h = self.panel_size  = self.GetSize()
            pad_w, pad_h = int(1+(pan_w-img_w)/2.0), int(1+(pan_h-img_h)/2.0)
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
