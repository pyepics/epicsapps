"""Image Panel using direct connection to PyCapture2 API
   for Point Grey FlyCapture2 cameras
"""
import numpy as np
import wx
import time
import os
from functools import partial

from epics import get_pv, Device, caput, poll

from epics.wx import DelayedEpicsCallback, EpicsFunction

from wxutils import FloatSpin, FloatCtrl, pack, Button

from .imagepanel_base import ImagePanel_Base, ConfPanel_Base

LEFT = wx.ALIGN_LEFT|wx.EXPAND

HAS_PYSPIN = False
#try:
import PySpin
from .pyspin_camera import PySpinCamera
#HAS_PYSPIN = True
#except ImportError:
#    print("no pyspin imported?")

MAX_EXPOSURE_TIME = 58

class ImagePanel_PySpin(ImagePanel_Base):
    """Image Panel for Spinnaker camera"""
    def __init__(self, parent,  camera_id=0, writer=None,
                 autosave_file=None, output_pv=None, **kws):
        # if not HAS_PYSPIN:
        #     raise ValueError("PySpin library not available")
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
        print("IMAGE PANEL PYSPIN ", self.camera)
        self.confpanel = None
        self.capture_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.onTimer, self.capture_timer)

    def Start(self):
        "turn camera on"
        self.camera.Connect()
        self.cam_name = self.camera.device_name
        if True: #try:
            self.camera.StartCapture()
            height, width = self.camera.GetSize()
            self.img_w = float(width+0.5)
            self.img_h = float(height+0.5)
        # except:
        #    pass
        if self.output_pv is not None:
            for attr  in ('ArraySize0_RBV', 'ArraySize1_RBV', 'ArraySize2_RBV',
                          'ColorMode_RBV', 'ArrayData'):
                if attr not in self.output_pvs:
                    self.output_pvs[attr] = get_pv("%s%s" % (self.output_pv, attr))
            time.sleep(0.02)
            self.output_pvs['ColorMode_RBV'].put(2)
            self.output_pvs['ArraySize2_RBV'].put(3)
            self.output_pvs['ArraySize1_RBV'].put(int(self.img_h))
            self.output_pvs['ArraySize0_RBV'].put(int(self.img_w))
        self.capture_timer.Start(50)

    def Stop(self):
        "turn camera off"
        self.capture_timer.Stop()
        self.camera.StopCapture()

    def CaptureVideo(self, filename='Capture', format='MJPG', runtime=10.0):
        print(" in Capture Video!! ", runtime, filename)

    def SetExposureTime(self, exptime):
        self.camera.SetExposureTime(exptime, auto=False)
        if self.confpanel is not None:
            self.confpanel.wids['exposure'].SetValue(exptime)
            self.confpanel.wids['exposure_auto'].SetValue(0)

    def GetExposureGain(self):
        "get current exposure time and gain as dict"
        pgain = self.camera.GetGain()
        atime = self.camera.GetExposureTime()
        return {'exposure_time': atime, 'gain': pgain}

    def SetExposureGain(self, dat):
        "set current exposure time and gain from dict"
        self.SetExposureTime(dat['exposure_time'])
        self.camera.SetGain(dat['gain'], auto=False)

    def AutoSetExposureTime(self):
        """auto set exposure time"""
        count, IMAX = 0, 255.0
        self.confpanel.wids['gain_auto'].SetValue(0)
        while count < 5:
            count += 1
            img = self.GrabNumpyImage()
            imgmin, imgmax = np.percentile(img, [1, 99])
            imgave = img.mean()
            pgain = self.camera.GetGain()
            atime = self.camera.GetExposureTime()
            if imgmax > 250:
                if  pgain > 4.0:
                    pgain = 0.75 * pgain
                    self.camera.SetGain(pgain, auto=False)
                    self.confpanel.wids['gain'].SetValue(pgain)
                else:
                    self.SetExposureTime(0.75*atime)
            elif imgave < 100:
                if atime > 45:
                    pgain = 1.75 * pgain
                    self.camera.SetGain(pgain, auto=False)
                    self.confpanel.wids['gain'].SetValue(pgain)
                else:
                    etime = max(10, min(50, 1.75*atime))
                    self.SetExposureTime(etime)
            else:
                break
            time.sleep(0.1)

    def GrabWxImage(self, scale=1, rgb=True, can_skip=True,
                    quality=wx.IMAGE_QUALITY_HIGH):
        if True: # try:
            wximg = self.camera.GrabWxImage(scale=scale, rgb=rgb,
                                            quality=quality)
        # except:
        #     return
        # self.data = self.camera.data
        return wximg

    def GrabNumpyImage(self):
        self.data = self.camera.GrabNumPyImage(format='rgb')
        return self.data

class ConfPanel_PySpin(ConfPanel_Base):
    def __init__(self, parent, image_panel=None, camera_id=0,
                 center_cb=None, xhair_cb=None, **kws):
        super(ConfPanel_PySpin, self).__init__(parent, center_cb=center_cb,
                                             xhair_cb=xhair_cb, **kws)
        self.image_panel = image_panel
        self.camera_id = camera_id
        self.camera = self.image_panel.camera

        wids = self.wids
        sizer = self.sizer
        with_color_conv = False
        self.framerate_set_count = 0

        self.title = self.txt("PySpinnaker: ", size=285)
        next_row = self.show_position_info(row=0)

        self.__initializing = True
        i = next_row + 1

        sizer.Add(self.title,          (i,  0), (1, 3), LEFT)
        
        i += 1
        for dat in (('exposure', 'ms',  50, 0.03, MAX_EXPOSURE_TIME),
                    ('gain', 'dB',      5,  0, 40)):
            # ('gamma', '',       1, 0.5, 4)):

            key, units, defval, minval, maxval = dat
            wids[key] = FloatCtrl(self, value=defval,
                                  minval=minval, maxval=maxval,
                                  precision=2,
                                  action=self.onValue,
                                  act_on_losefocus=True,
                                  action_kws={'prop': key}, size=(75, -1))
            label = '%s' % (key.title())
            if len(units)> 0:
                label = '%s (%s)' % (key.title(), units)
            sizer.Add(self.txt(label), (i, 0), (1, 1), LEFT)
            sizer.Add(wids[key],  (i, 1), (1, 1), LEFT)

            if key != 'gamma':
                akey = '%s_auto' % key
                wids[akey] =  wx.CheckBox(self, -1, label='auto')
                wids[akey].SetValue(0)
                wids[akey].Bind(wx.EVT_CHECKBOX, partial(self.onAuto, prop=key))
                sizer.Add(wids[akey], (i, 2), (1, 1), LEFT)
            i = i + 1

        for color in ('blue', 'red'):
            key = 'wb_%s' % color
            wids[key] = FloatCtrl(self, value=0, minval=0.3, maxval=4,
                                  precision=3,
                                  action=self.onValue,
                                  act_on_losefocus=True,
                                  action_kws={'prop': key}, size=(75, -1))
            # wids[key].Disable()
            label = 'White Balance (%s)' % (color)
            sizer.Add(self.txt(label), (i, 0), (1, 1), LEFT)
            sizer.Add(wids[key],  (i, 1), (1, 1), LEFT)
            if color == 'blue':
                akey = 'wb_auto'
                wids[akey] =  wx.CheckBox(self, -1, label='auto')
                wids[akey].SetValue(0)
                wids[akey].Bind(wx.EVT_CHECKBOX, partial(self.onAuto, prop=key))
                sizer.Add(wids[akey], (i, 2), (1, 1), LEFT)
            i += 1

        # sizer.Add(btn_start,          (i, 0), (1, 2), LEFT)

        pack(self, sizer)
        self.__initializing = False
        self.read_props_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.onTimer, self.read_props_timer)
        wx.CallAfter(self.onConnect)


    def onRestart(self, event=None, **kws):
        self.camera.cam.EndAcquisition()
        time.sleep(0.25)
        self.camera.cam.BeginAcquisition()
        self.onConnect()

    def onColorConv(self, event=None):
        try:
            val = self.wids['color_conv'].GetStringSelection()
            self.camera.SetConvertMethod(val)
        except:
            pass

    def onConnect(self, **kws):
        self.wids['exposure'].SetValue(min(MAX_EXPOSURE_TIME, self.camera.GetExposureTime()))
        self.wids['exposure_auto'].SetValue(0)
        self.wids['gain'].SetValue(self.camera.GetGain())
        self.wids['gain_auto'].SetValue(0)

        blue, red = self.camera.GetWhiteBalance()
        self.wids['wb_red'].SetValue(red)
        self.wids['wb_blue'].SetValue(blue)
        self.wids['wb_auto'].SetValue(0)
        self.read_props_timer.Start(3000)
        self.title.SetLabel("Camera Model: %s" % (self.camera.device_name))
        # self.title2.SetLabel("Serial #: %s" % (self.camera.device_id))
        # self.title3.SetLabel("Firmware: %s" % (self.camera.device_version))

        self.camera.SetFramerate(14.5)
        self.framerate_set_count = 0
        self.camera.SetExposureTime(30, auto=False)

    def onEnableDataPush(self, evt=None, **kws):
        self.image_panel.datapush = evt.IsChecked()

    def onTimer(self, evt=None, **kws):
        # print(" Timer ",  self.camera.GetExposureTime(),
        #       self.camera.GetGain(), self.image_panel.fps_current)

        if (self.image_panel.fps_current > 16.0 and
            self.framerate_set_count < 2):
            self.camera.SetFramerate(14.5)
            self.framerate_set_count += 1
            time.sleep(0.5)

        if self.wids['exposure_auto'].GetValue():
            cam_val = self.camera.GetExposureTime()
            wid_val = self.wids['exposure'].GetValue()
            if int(100.0*abs(cam_val - wid_val)) > 3:
                self.wids['exposure'].SetValue(cam_val)

        if self.wids['gain_auto'].GetValue():
            cam_val = self.camera.GetGain()
            wid_val = self.wids['gain'].GetValue()
            if int(100.0*abs(cam_val - wid_val)) > 3:
                self.wids['gain'].SetValue(cam_val)

        if self.wids['wb_auto'].GetValue():
            blue, red = self.camera.GetWhiteBalance()
            wblue = self.wids['wb_blue'].GetValue()
            wred = self.wids['wb_red'].GetValue()
            if self.wids['wb_auto'].GetValue(): # force setting
                wblue = wred = -1.
                self.wids['wb_auto'].SetValue(0)
            if int(100.0*abs(blue - wblue)) > 3:
                self.wids['wb_blue'].SetValue(blue)
            if int(100.0*abs(red - wred)) > 3:
                self.wids['wb_red'].SetValue(red)

    def onAuto(self, evt=None, prop=None, **kws):
        if not evt.IsChecked():
            return
        if prop == 'exposure':
            for i in range(4):
                val = min(MAX_EXPOSURE_TIME, self.camera.GetExposureTime()) - 1.0
                self.camera.SetExposureTime(val, auto=False)
                time.sleep(0.25)
                self.wids['exposure'].SetValue(self.camera.GetExposureTime())
            self.camera.SetExposureTime(val, auto=False)
        elif prop == 'gain':
            gain = self.camera.GetGain()
            self.camera.SetGain(gain, auto=True)
            time.sleep(0.1)
        elif prop in ('wb_red', 'wb_blue', 'wb_auto'):
            for i in range(4):
                red = self.wids['wb_red'].GetValue()
                blue = self.wids['wb_blue'].GetValue()
                try:
                    self.camera.SetWhiteBalance(blue, red, auto=True)
                except:
                    pass
                time.sleep(0.25)
                self.camera.SetWhiteBalance(blue, red, auto=False)

    def onValue(self, prop=None, value=None,  **kws):
        if self.__initializing:
            return
        if prop == 'autosave_time':
            self.image_panel.datapush_delay = float(value)
        elif prop == 'exposure':
            self.wids['%s_auto' % prop].SetValue(0)
            self.camera.SetExposureTime(float(value), auto=False)
        elif prop == 'gain':
            self.wids['%s_auto' % prop].SetValue(0)
            self.camera.SetGain(float(value), auto=False)
        elif prop in ('wb_red', 'wb_blue'):
            self.wids['wb_auto'].SetValue(0)
            red =  self.wids['wb_red'].GetValue()
            blue = self.wids['wb_blue'].GetValue()
            try:
                self.camera.SetWhiteBalance(blue, red, auto=False)
            except:
                pass
