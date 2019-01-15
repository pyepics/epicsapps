"""Image Panel using direct connection to PyCapture2 API
   for Point Grey FlyCapture2 cameras
"""
import numpy as np
import wx
import time
import os
from epics import PV, Device, caput, poll
from epics.wx import EpicsFunction

from .imagepanel_base import ImagePanel_Base, ConfPanel_Base
from epics.wx.utils import pack, FloatCtrl, Closure, add_button
from epics.wx import DelayedEpicsCallback

LEFT = wx.ALIGN_LEFT|wx.EXPAND

HAS_PYSPIN = False
try:
    import PySpin
    from .pyspin_camera import PySpinCamera
    HAS_PYSPIN = True
except ImportError:
    pass

is_wxPhoenix = 'phoenix' in wx.PlatformInfo

if is_wxPhoenix:
    Image = wx.Image
else:
    Image = wx.ImageFromData

class ImagePanel_PySpin(ImagePanel_Base):
    """Image Panel for Spinnaker camera"""
    def __init__(self, parent,  camera_id=0, writer=None,
                 autosave_file=None, output_pv=None, **kws):
        if not HAS_PYSPIN:
            raise ValueError("PySpin library not available")
        super(ImagePanel_PySpin, self).__init__(parent, -1,
                                              size=(800, 600),
                                              writer=writer,
                                              autosave_file=autosave_file,
                                              datapush=True, **kws)
        self.camera = PySpinCamera(camera_id=camera_id)
        self.output_pv = output_pv
        self.output_pvs = {}
        self.img_w = 800.5
        self.img_h = 600.5
        self.writer = writer
        self.cam_name = '-'
        self.confpanel = None
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.onTimer, self.timer)

    def Start(self):
        "turn camera on"
        self.camera.Connect()
        self.cam_name = self.camera.device_name

        try:
            self.camera.StartCapture()
            width, height = self.camera.GetSize()
            self.img_w = float(width+0.5)
            self.img_h = float(height+0.5)
        except:
            pass
        if self.output_pv is not None:
            for attr  in ('ArraySize0_RBV', 'ArraySize1_RBV', 'ArraySize2_RBV',
                          'ColorMode_RBV', 'ArrayData'):
                if attr not in self.output_pvs:
                    self.output_pvs[attr] = PV("%s%s" % (self.output_pv, attr))
            time.sleep(0.02)
            self.output_pvs['ColorMode_RBV'].put(2)
            self.output_pvs['ArraySize2_RBV'].put(3)
            self.output_pvs['ArraySize1_RBV'].put(int(self.img_h))
            self.output_pvs['ArraySize0_RBV'].put(int(self.img_w))

        self.timer.Start(50)

    def Stop(self):
        "turn camera off"
        self.timer.Stop()
        self.camera.StopCapture()

    def CaptureVideo(self, filename='Capture', format='MJPG', runtime=10.0):
        print(" in Capture Video!! ", runtime, filename)

    def SetExposureTime(self, exptime):
        self.camera.SetExposureTime(exptime, auto=False)
        if self.confpanel is not None:
            self.confpanel.wids['exposure'].SetValue(exptime)
            self.confpanel.wids['exposure_auto'].SetValue(0)

    def AutoSetExposureTime(self):
        """auto set exposure time"""
        count, IMAX = 0, 255.0
        self.confpanel.wids['gain_auto'].SetValue(0)
        while count < 5:
            count += 1
            img = self.GrabNumpyImage()
            imgmax = img.max()
            imgave = img.mean()
            pgain = self.camera.GetGain()
            atime = self.camera.GetExposureTime()
            if imgmax > 250:
                if  pgain > 4.0:
                    pgain = 0.75 * pgain
                    self.camera.SetGaain(pgain, auto=False)
                    self.confpanel.wids['gain'].SetValue(pgain)
                else:
                    self.SetExposureTime(0.75*atime)
            elif imgave < 100:
                if atime > 60:
                    pgain = 1.75 * pgain
                    self.camera.SetGain(pgain, auto=False)
                    self.confpanel.wids['gain'].SetValue(pgain)
                else:
                    etime = max(10, min(64, 1.75*atime))
                    self.SetExposureTime(etime)
            else:
                break
            time.sleep(0.1)

    def GrabWxImage(self, scale=1, rgb=True, can_skip=True,
                    quality=wx.IMAGE_QUALITY_HIGH):
        # print("Fly Grab Wx ", PyCapture2 )
        try:
            img = self.camera.cam.retrieveBuffer()
        except PyCapture2.Fc2error:
            time.sleep(0.025)
            img = self.camera.cam.retrieveBuffer()

        nrows = img.getRows()
        ncols = img.getCols()
        scale = max(scale, 0.05)
        width, height = int(scale*ncols), int(scale*nrows)
        if rgb:
            img = img.convert(PyCapture2.PIXEL_FORMAT.RGB)
        self.data_shape = (nrows, ncols, 3)
        self.data = np.array(img.getData())
        self.full_image = wx.Image(ncols, nrows, self.data)
        return self.full_image.Rescale(width, height, quality=quality)

    def GrabNumpyImage(self):
        return self.camera.GrabNumPyImage(format='rgb')

class ConfPanel_PySpin(ConfPanel_Base):
    def __init__(self, parent, image_panel=None, camera_id=0,
                 center_cb=None, xhair_cb=None, **kws):
        super(ConfPanel_PySpin, self).__init__(parent, center_cb=center_cb,
                                             xhair_cb=xhair_cb)
        self.image_panel = image_panel
        self.camera_id = camera_id
        self.camera = self.image_panel.camera

        wids = self.wids
        sizer = self.sizer

        self.title = self.txt("PySpin: ", size=285)
        self.title2 = self.txt(" ", size=285)

        sizer.Add(self.title, (0, 0), (1, 3), LEFT)
        sizer.Add(self.title2,(1, 0), (1, 3), LEFT)
        next_row = self.show_position_info(row=2)

        self.__initializing = True
        i = next_row + 1
        for dat in (('exposure', 'ms',  50 , 0, 70),
                    ('gain', 'dB',      0, -2, 24),
                    ('gamma', '',       1, 0.5, 4)):

            key, units, defval, minval, maxval = dat
            wids[key] = FloatCtrl(self, value=defval,
                                  minval=minval, maxval=maxval,
                                  precision=1,
                                  action=self.onValue,
                                  act_on_losefocus=True,
                                  action_kw={'prop': key}, size=(75, -1))
            label = '%s' % (key.title())
            if len(units)> 0:
                label = '%s (%s)' % (key.title(), units)
            sizer.Add(self.txt(label), (i, 0), (1, 1), LEFT)
            sizer.Add(wids[key],  (i, 1), (1, 1), LEFT)

            if key != 'gamma':
                akey = '%s_auto' % key
                wids[akey] =  wx.CheckBox(self, -1, label='auto')
                wids[akey].SetValue(0)
                wids[akey].Bind(wx.EVT_CHECKBOX, Closure(self.onAuto, prop=key))
                sizer.Add(wids[akey], (i, 2), (1, 1), LEFT)
            i = i + 1

        for color in ('blue', 'red'):
            key = 'wb_%s' % color
            wids[key] = FloatCtrl(self, value=0, maxval=1024,
                                  precision=0,
                                  action=self.onValue,
                                  act_on_losefocus=True,
                                  action_kw={'prop': key}, size=(75, -1))
            label = 'White Balance (%s)' % (color)
            sizer.Add(self.txt(label), (i, 0), (1, 1), LEFT)
            sizer.Add(wids[key],  (i, 1), (1, 1), LEFT)

            if color == 'blue':
                akey = 'wb_auto'
                wids[akey] =  wx.CheckBox(self, -1, label='auto')
                wids[akey].SetValue(0)
                wids[akey].Bind(wx.EVT_CHECKBOX, Closure(self.onAuto, prop=key))
                sizer.Add(wids[akey], (i, 2), (1, 1), LEFT)
            i += 1

        datapush_time = "%.1f" % self.image_panel.datapush_delay
        wids['dpush_time'] =  FloatCtrl(self, value=datapush_time, maxval=1e6,
                                        precision=1, minval=0,
                                        action=self.onValue, act_on_losefocus=True,
                                        action_kw={'prop':'autosave_time'}, size=(75, -1))

        label = 'AutoSave Time (sec)'
        sizer.Add(self.txt(label), (i, 0), (1, 1), LEFT)
        sizer.Add(wids['dpush_time'],  (i, 1), (1, 1), LEFT)

        # wids['datapush'].SetValue(1)
        # wids['datapush'].Bind(wx.EVT_CHECKBOX, self.onEnableDataPush)
        # sizer.Add(wids['datapush'], (i+1, 0), (1, 3), LEFT)

        pack(self, sizer)
        self.__initializing = False
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.onTimer, self.timer)
        wx.CallAfter(self.onConnect)

    def onConnect(self, **kws):

        self.wids['exposure'].SetValue(self.camera.GetExposureTime())
        self.wids['exposure_auto'].SetValue(0)

        self.wids['gamma'].SetValue(self.camera.GetGamma())

        self.wids['gain'].SetValue(self.camera.GetGain())
        self.wids['gain_auto'].SetValue(0)

        blue, red = self.camera.GetWhiteBalance()
        self.wids['wb_red'].SetValue(red)
        self.wids['wb_blue'].SetValue(blue)
        self.wids['wb_auto'].SetValue(0)
        self.timer.Start(1000)
        cinfo  = self.image_panel.camera.info
        self.title.SetLabel("Camera Model: %s" % (cinfo.modelName))
        self.title2.SetLabel("Serial #%d, Firmware %s" % (cinfo.serialNumber, cinfo.firmwareVersion))

    def onEnableDataPush(self, evt=None, **kws):
        self.image_panel.datapush = evt.IsChecked()

    def onTimer(self, evt=None, **kws):
        if self.wids['exposure_auto']:
            self.wids['exposure'].SetValue(self.camera.GetExposureTime())

        if self.wids['gain_auto']:
            self.wids['gain'].SetValue(self.camera.GetGain())

        if self.wids['wb_auto']:
            blue, red = self.camera.GetWhiteBalance()
            self.wids['wb_red'].SetValue(red)
            self.wids['wb_blue'].SetValue(blue)

    def onAuto(self, evt=None, prop=None, **kws):
        if not evt.IsChecked():
            return
        if prop == 'exposure':
            val = self.camera.GetExposureTime()
            self.camera.SetExposureTime(val, auto=True)
            time.sleep(0.25)
            self.wids['exposure'].SetValue(self.camera.GetExposureTime())
        elif prop == 'gain':
            gain = self.camera.GetGain()
            self.camera.SetGain(gain, auto=True)
            time.sleep(0.25)
            self.wids['gain'].SetValue(self.camera.GetGain())

        elif prop in ('wb_red', 'wb_blue', 'wb_auto'):
            blue, red = self.camera.GetWhiteBalance()
            print(" SET WB onAuto ", blue, red)
            # self.camera.SetWhiteBalance(blue, red, auto=True)
            time.sleep(0.25)
            blue, red = self.camera.GetWhiteBalance()
            self.wids['wb_red'].SetValue(red)
            self.wids['wb_blue'].SetValue(blue)

    def onValue(self, prop=None, value=None,  **kws):
        if self.__initializing:
            return
        if prop == 'autosave_time':
            self.image_panel.datapush_delay = float(value)

        elif prop == 'exposure':
            auto = self.wids['%s_auto' % prop].GetValue()
            self.camera.SetExposureTime(float(value), auto=auto)
        elif prop == 'gain':
            auto = self.wids['%s_auto' % prop].GetValue()
            self.camera.SetGain(float(value), auto=auto)
        elif prop == 'gamma':
            self.camera.SetGamma(float(value))
        elif prop in ('wb_red', 'wb_blue', 'wb_auto'):
            red =  self.wids['wb_red'].GetValue()
            blue = self.wids['wb_blue'].GetValue()
            auto = self.wids['wb_auto'].GetValue()
            print(" SET WB onValue ", blue, red)
            # self.camera.SetWhiteBalance(blue, red, auto=auto)
