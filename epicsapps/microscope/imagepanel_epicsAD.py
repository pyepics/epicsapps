"""Image Panel for Epics AreaDetector
"""

import wx
import time
import os
import numpy as np
from functools import partial
from epics import PV, Device, caput, poll

from epics.wx import DelayedEpicsCallback, EpicsFunction
from epics.wx import PVEnumChoice, PVFloatCtrl, PVTextCtrl

from PIL import Image

from .imagepanel_base import ImagePanel_Base, ConfPanel_Base

from wxutils import pack, Button

class ImagePanel_EpicsAD(ImagePanel_Base):
    img_attrs = ('ArrayData', 'UniqueId_RBV', 'NDimensions_RBV',
                 'ArraySize0_RBV', 'ArraySize1_RBV', 'ArraySize2_RBV',
                 'ColorMode_RBV')

    cam_attrs = ('Acquire', 'ArrayCounter', 'ArrayCounter_RBV',
                 'DetectorState_RBV', 'NumImages', 'ColorMode',
                 'ColorMode_RBV', 'DataType_RBV', 'Gain', 'AcquireTime',
                 'AcquirePeriod', 'ImageMode', 'ArraySizeX_RBV',
                 'ArraySizeY_RBV')

    """Image Panel for FlyCapture2 camera"""
    def __init__(self, parent, prefix=None, format='JPEG',
                 writer=None, autosave_file=None, **kws):
        super(ImagePanel_EpicsAD, self).__init__(parent, -1,
                                                 size=(800, 600),
                                                 writer=writer,
                                                 autosave_file=autosave_file, **kws)

        self.format = format
        self.set_prefix(prefix)
        self.imgcount = 0
        self.imgcount_start = 0
        self.last_update = 0.0

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.onTimer, self.timer)

    def set_prefix(self, prefix):
        if prefix.endswith(':'):         prefix = prefix[:-1]
        if prefix.endswith(':image1'):   prefix = prefix[:-7]
        if prefix.endswith(':cam1'):     prefix = prefix[:-5]
        self.prefix = prefix

        self.ad_img = Device(prefix + ':image1:', delim='',
                                   attrs=self.img_attrs)
        self.ad_cam = Device(prefix + ':cam1:', delim='',
                                   attrs=self.cam_attrs)

        self.config_filesaver(prefix, self.format)

        w, h = self.GetImageSize()
        self.cam_name = prefix

    def config_filesaver(self, prefix, format):
        if not prefix.endswith(':'):  prefix = "%s:" % prefix
        if not format.endswith('1'):  format = "%s1" % format
        if not format.endswith('1:'): format = "%s:" % format

        cname = "%s%s"% (prefix, format)
        caput("%sEnableCallbacks" % cname, 1)
        thisdir = os.path.abspath(os.getcwd()).replace('\\', '/')
        # caput("%sFilePath" % cname, thisdir)
        caput("%sAutoSave" % cname, 0)
        caput("%sAutoIncrement" % cname, 0)
        caput("%sFileTemplate" % cname, "%s%s")
        if format.upper() == 'JPEG1:':
            caput("%sJPEGQuality" % cname, 90)

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

    def SetExposureTime(self, exptime):
        "set exposure time"
        self.ad_cam.AcquireTime = exptime

    def AutoSetExposureTime(self):
        """auto set exposure time"""
        count, IMAX = 0, 255.0
        while count < 8:
            img = self.GrabNumpyImage().astype(np.uint8)
            count += 1
            scale = 0
            if img.max() < 0.5*IMAX:
                scale = 1.5
            elif img.mean() > 0.50*IMAX:
                scale = 0.75
            elif img.mean() < 0.20*IMAX:
                scale = 1.25
            else:
                break
            if scale > 0:
                scale = max(0.2, min(5.0, scale))
                self.ad_cam.AcquireTime *= scale
                time.sleep(0.1)

    def GetImageSize(self):
        arrsize0 = self.ad_img.ArraySize0_RBV
        arrsize1 = self.ad_img.ArraySize1_RBV
        arrsize2 = self.ad_img.ArraySize2_RBV
        self.arrsize   = (arrsize0, arrsize1, arrsize2)
        self.colormode = self.ad_img.ColorMode_RBV

        w, h = arrsize0, arrsize1
        if self.ad_img.NDimensions_RBV == 3:
            w, h  = arrsize1, arrsize2
        self.img_w = float(w+0.5)
        self.img_h = float(h+0.5)
        return w, h


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

    def GrabWxImage(self, scale=1, rgb=True, can_skip=True):
        if self.ad_img is None or self.ad_cam is None:
            print('GrabWxImage .. no ad_img / cam', self.ad_img, self.ad_cam)
            return

        width, height = self.GetImageSize()
        imgcount = self.ad_cam.ArrayCounter_RBV
        now = time.time()
        if (can_skip and (imgcount == self.imgcount or
                          abs(now - self.last_update) < 0.025)):
            return None
        self.imgcount = imgcount
        self.last_update = time.time()

        im_mode = 'L'
        self.im_size = (self.arrsize[0], self.arrsize[1])
        if self.ad_img.ColorMode_RBV == 2:
            im_mode = 'RGB'
            self.im_size = (self.arrsize[1], self.arrsize[2])

        dcount = self.arrsize[0] * self.arrsize[1]
        if self.ad_img.NDimensions_RBV == 3:
            dcount *= self.arrsize[2]

        rawdata = self.ad_img.PV('ArrayData').get(count=dcount)
        if rawdata is None:
            return

        if (self.ad_img.ColorMode_RBV == 0 and
            isinstance(rawdata, np.ndarray) and
            rawdata.dtype != np.uint8):
            im_mode = 'I'
            rawdata = rawdata.astype(np.uint32)
        if im_mode in ('L', 'I'):
            image = wx.EmptyImage(width, height)
            imbuff = Image.frombuffer(im_mode, self.im_size, rawdata,
                                      'raw',  im_mode, 0, 1)
            image.SetData(imbuff.convert('RGB').tobytes())
        elif im_mode == 'RGB':
            rawdata.shape = (3, width, height)
            rawdata = rawdata.astype(np.uint8)
            image = wx.Image(width, height, rawdata)
        return image.Scale(int(scale*width), int(scale*height))

class ConfPanel_EpicsAD(ConfPanel_Base):
    img_attrs = ('ArrayData', 'UniqueId_RBV', 'NDimensions_RBV',
                 'ArraySize0_RBV', 'ArraySize1_RBV', 'ArraySize2_RBV',
                 'ColorMode_RBV')

    cam_attrs = ('Acquire', 'ArrayCounter', 'ArrayCounter_RBV',
                 'DetectorState_RBV',  'NumImages', 'ColorMode',
                 'DataType_RBV',  'Gain',
                 'AcquireTime', 'AcquirePeriod', 'ImageMode',
                 'MaxSizeX_RBV', 'MaxSizeY_RBV', 'TriggerMode',
                 'SizeX', 'SizeY', 'MinX', 'MinY')

    def __init__(self, parent, image_panel=None, prefix=None,
                 center_cb=None, xhair_cb=None, **kws):
        super(ConfPanel_EpicsAD, self).__init__(parent, center_cb=center_cb,
                                                xhair_cb=xhair_cb)

        wids = self.wids
        sizer = self.sizer
        self.image_panel = image_panel
        self.SetBackgroundColour('#EEFFE')
        self.title =  wx.StaticText(self, size=(285, 25),
                                    label="Epics AreaDetector")

        for key in ('imagemode', 'triggermode', 'color'):
            self.wids[key]   = PVEnumChoice(self, pv=None, size=(135, -1))

        for key in ('exptime', 'gain'):
            self.wids[key]   = PVFloatCtrl(self, pv=None, size=(135, -1), minval=0)
        self.wids['gain'].SetMax(20)

        for key in ('start', 'stop'):
            self.wids[key] =Button(self, label=key.title(), size=(65, -1),
                                   action=partial(self.onButton, key=key))

        labstyle  = wx.ALIGN_LEFT|wx.EXPAND|wx.ALIGN_BOTTOM
        ctrlstyle = wx.ALIGN_LEFT #  |wx.ALIGN_BOTTOM
        rlabstyle = wx.ALIGN_RIGHT|wx.RIGHT|wx.TOP|wx.EXPAND
        txtstyle  = wx.ALIGN_LEFT|wx.ST_NO_AUTORESIZE|wx.TE_PROCESS_ENTER


        self.wids['fullsize']= wx.StaticText(self, -1,  size=(250,-1), style=txtstyle)

        def txt(label, size=100):
            return wx.StaticText(self, label=label, size=(size, -1), style=labstyle)

        def lin(len=30, wid=2, style=wx.LI_HORIZONTAL):
            return wx.StaticLine(self, size=(len, wid), style=style)

        sizer.Add(self.title,               (0, 0), (1, 3), labstyle)
        i = next_row = self.show_position_info(row=1)
        i += 1
        sizer.Add(self.wids['fullsize'],    (i, 0), (1, 3), labstyle)
        i += 1
        sizer.Add(txt('Acquire '),          (i, 0), (1, 1), labstyle)
        sizer.Add(self.wids['start'],       (i, 1), (1, 1), ctrlstyle)
        sizer.Add(self.wids['stop'],        (i, 2), (1, 1), ctrlstyle)
        i += 1
        sizer.Add(txt('Image Mode '),       (i, 0), (1, 1), labstyle)
        sizer.Add(self.wids['imagemode'],   (i, 1), (1, 2), ctrlstyle)

        i += 1
        sizer.Add(txt('Trigger Mode '),     (i, 0), (1, 1), labstyle)
        sizer.Add(self.wids['triggermode'], (i, 1), (1, 2), ctrlstyle)

        i += 1
        sizer.Add(txt('Exposure Time '),    (i, 0), (1, 1), labstyle)
        sizer.Add(self.wids['exptime'],     (i, 1), (1, 2), ctrlstyle)

        i += 1
        sizer.Add(txt('Gain '),             (i, 0), (1, 1), labstyle)
        sizer.Add(self.wids['gain'],        (i, 1), (1, 2), ctrlstyle)

        i += 1
        sizer.Add(txt('Color Mode'),        (i, 0), (1, 1), labstyle)
        sizer.Add(self.wids['color'],       (i, 1), (1, 2), ctrlstyle)

        #  show last pixel position, move to center
        pack(self, sizer)
        self.set_prefix(prefix)

    @EpicsFunction
    def set_prefix(self, prefix):
        if prefix.endswith(':'):         prefix = prefix[:-1]
        if prefix.endswith(':image1'):   prefix = prefix[:-7]
        if prefix.endswith(':cam1'):     prefix = prefix[:-5]
        self.prefix = prefix

        self.ad_img = Device(prefix + ':image1:', delim='',
                                   attrs=self.img_attrs)
        self.ad_cam = Device(prefix + ':cam1:', delim='',
                                   attrs=self.cam_attrs)

        self.title.SetLabel("Epics AreaDetector: %s" % prefix)
        self.connect_pvs()

    @EpicsFunction
    def connect_pvs(self, verbose=True):
        if self.prefix is None or len(self.prefix) < 2:
            return

        time.sleep(0.010)
        if not self.ad_img.PV('UniqueId_RBV').connected:
            poll()
            if not self.ad_img.PV('UniqueId_RBV').connected:
                self.messag('Warning:  Camera seems to not be connected!')
                return

        self.wids['color'].SetPV(self.ad_cam.PV('ColorMode'))
        self.wids['exptime'].SetPV(self.ad_cam.PV('AcquireTime'))
        self.wids['gain'].SetPV(self.ad_cam.PV('Gain'))
        self.wids['imagemode'].SetPV(self.ad_cam.PV('ImageMode'))

        self.wids['triggermode'].SetPV(self.ad_cam.PV('TriggerMode'))

        width, height = self.image_panel.GetImageSize()
        sizelabel = 'Image Size: %i x %i pixels' % (width, height)

        self.wids['fullsize'].SetLabel(sizelabel)
        poll()

    def onBringToCenter(self, event=None,  **kws):
        if self.center_cb is not None:
            self.center_cb(event=event, **kws)

    @EpicsFunction
    def onButton(self, evt=None, key='name', **kw):
        if evt is None:
            return
        if key == 'start':
            self.n_img   = 0
            self.n_drawn = 0
            self.starttime = time.time()
            self.imgcount_start = self.ad_cam.ArrayCounter_RBV
            self.ad_cam.Acquire = 1
        elif key == 'stop':
            self.ad_cam.Acquire = 0
        elif key == 'unzoom':
            self.unZoom()
        else:
            print('unknown Entry ? ', key)
