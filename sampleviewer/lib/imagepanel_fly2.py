"""Image Panel using direct connection to PyCapture2 API
   for Point Grey FlyCapture2 cameras
"""
import numpy as np
import wx
import time

from epics import PV
from .imagepanel_base import ImagePanel_Base, ConfPanel_Base
from epics.wx.utils import pack, FloatCtrl, Closure, add_button
from epics.wx import DelayedEpicsCallback

LEFT = wx.ALIGN_LEFT|wx.EXPAND

HAS_FLY2 = False
try:
    import PyCapture2
    import fly2_camera
    HAS_FLY2 = True
except ImportError:
    pass

is_wxPhoenix = 'phoenix' in wx.PlatformInfo

if is_wxPhoenix:
    Image = wx.Image
else:
    Image = wx.ImageFromData

class ImagePanel_Fly2(ImagePanel_Base):
    """Image Panel for FlyCapture2 camera"""
    def __init__(self, parent,  camera_id=0, writer=None,
                 autosave_file=None, output_pv=None, **kws):
        if not HAS_FLY2:
            raise ValueError("PyCapture2 library not available")
        super(ImagePanel_Fly2, self).__init__(parent, -1,
                                              size=(800, 600),
                                              writer=writer,
                                              autosave_file=autosave_file, **kws)
        self.camera = fly2_camera.Fly2Camera(camera_id=camera_id)
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
        self.cam_name = self.camera.info.modelName

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
        if self.autosave_thread is not None:
            self.autosave_thread.start()

    def Stop(self):
        "turn camera off"
        self.timer.Stop()
        self.autosave = False
        self.camera.StopCapture()
        if self.autosave_thread is not None:
            self.autosave_thread.join()

    def SetExposureTime(self, exptime):
        self.camera.SetPropertyValue('shutter', exptime, auto=False)
        if self.confpanel is not None:
            self.confpanel.wids['shutter'].SetValue(exptime)
            self.confpanel.wids['shutter_auto'].SetValue(0)


    def AutoSetExposureTime(self):
        """auto set exposure time"""
        count, IMAX = 0, 255.0
        while count < 10:
            img = self.GrabNumpyImage()

            count += 1
            scale = 0
            if img.max() < 0.30*IMAX:
                scale = 1.5
            elif img.mean() > 0.70*IMAX:
                scale = 0.85
            elif img.mean() < 0.3*IMAX:
                scale = 1.5
            else:
                # print "auto set exposure done"
                break
            if scale > 0:
                scale = max(0.2, min(5.0, scale))
                atime = self.camera.GetProperty('shutter').absValue
                etime = atime*scale
                pgain = self.camera.GetProperty('gain')
                gain = pgain.absValue
                if etime > 64: # max exposure time
                    gain *= etime/64.0
                    etime = 64.0
                self.SetExposureTime(etime)
                self.camera.SetPropertyValue('gain', gain, auto=False)
                self.confpanel.wids['gain'].SetValue(gain)
                self.confpanel.wids['gain_auto'].SetValue(0)
                time.sleep(0.1)

    def GrabWxImage(self, scale=1, rgb=True, can_skip=True,
                    quality=wx.IMAGE_QUALITY_HIGH):
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
        return wx.Image(ncols, nrows, self.data).Rescale(width, height,
                                                        quality=quality)

    def GrabNumpyImage(self):
        return self.camera.GrabNumPyImage(format='rgb')

class ConfPanel_Fly2(ConfPanel_Base):
    def __init__(self, parent, image_panel=None, camera_id=0,
                 center_cb=None, xhair_cb=None, **kws):
        super(ConfPanel_Fly2, self).__init__(parent, center_cb=center_cb,
                                             xhair_cb=xhair_cb)
        self.image_panel = image_panel
        self.camera_id = camera_id
        self.camera = self.image_panel.camera

        wids = self.wids
        sizer = self.sizer

        self.title = self.txt("PyCapture2: ", size=285)
        self.title2 = self.txt(" ", size=285)

        sizer.Add(self.title, (0, 0), (1, 3), LEFT)
        sizer.Add(self.title2,(1, 0), (1, 3), LEFT)
        next_row = self.show_position_info(row=2)

        self.__initializing = True
        i = next_row + 1
        #('Sharpness', '%', 100), ('Hue', 'deg', 100), ('Saturation', '%', 100),
        for dat in (('shutter', 'ms',  50 , 0, 70),
                    ('gain', 'dB',      0, -2, 24),
                    # ('brightness', '%', 0,  0,  6),
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

        pack(self, sizer)
        self.__initializing = False
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.onTimer, self.timer)
        wx.CallAfter(self.onConnect)

    def onConnect(self, **kws):
        for prop in ('shutter', 'gain', 'gamma'): # , 'brightness'):
            p = self.camera.GetProperty(prop)
            self.wids[prop].SetValue(p.absValue)
            akey = '%s_auto' % prop
            self.wids[akey].SetValue({False: 0, True: 1}[p.autoManualMode])

        p = self.camera.GetProperty('white_balance')
        self.wids['wb_red'].SetValue(p.valueA)
        self.wids['wb_blue'].SetValue(p.valueB)
        self.wids['wb_auto'].SetValue({False: 0, True: 1}[p.autoManualMode])
        self.timer.Start(1000)
        cinfo  = self.image_panel.camera.info
        self.title.SetLabel("Camera Model: %s" % (cinfo.modelName))
        self.title2.SetLabel("Serial #%d, Firmware %s" % (cinfo.serialNumber, cinfo.firmwareVersion))
        # print( "Camera info: ")
        # for a in dir(cinfo):
        # if a.startswith('__'):
        #         continue
        #     print(a, getattr(cinfo, a, '??'))

    def onTimer(self, evt=None, **kws):
        for prop in ('shutter', 'gain', 'gamma', 'white_balance'):
            try:
                p = self.camera.GetProperty(prop)
            except:
                return
            if p.autoManualMode:
                if  prop == 'white_balance':
                    self.wids['wb_red'].SetValue(p.valueA)
                    self.wids['wb_blue'].SetValue(p.valueB)
                else:
                    self.wids[prop].SetValue(p.absValue)

    def onAuto(self, evt=None, prop=None, **kws):
        if not evt.IsChecked():
            return
        if prop in ('wb_red', 'wb_blue', 'wb_auto'):
            prop = 'white_balance'
        try:
            if prop in ('shutter', 'gain', 'gamma'): # , 'brightness'):
                p = self.camera.GetProperty(prop)
                self.camera.SetPropertyValue(prop, p.absValue, auto=True)
                time.sleep(0.5)
                p = self.camera.GetProperty(prop)
                self.wids[prop].SetValue(p.absValue)
            elif prop == 'white_balance':
                red =  self.wids['wb_red'].GetValue()
                blue = self.wids['wb_blue'].GetValue()
                self.camera.SetPropertyValue(prop, (red, blue), auto=True)
                time.sleep(0.5)
                p = self.camera.GetProperty(prop)
                self.wids['wb_red'].SetValue(p.valueA)
                self.wids['wb_blue'].SetValue(p.valueB)
        except:
            return

    def onValue(self, prop=None, value=None,  **kws):
        if self.__initializing:
            return
        if prop in ('wb_red', 'wb_blue', 'wb_auto'):
            prop = 'white_balance'
        try:
            if prop in ('shutter', 'gain', 'gamma'): # , 'brightness'):
                auto = self.wids['%s_auto' % prop].GetValue()
                self.camera.SetPropertyValue(prop, float(value), auto=auto)
            elif prop == 'white_balance':
                red =  self.wids['wb_red'].GetValue()
                blue = self.wids['wb_blue'].GetValue()
                auto = self.wids['wb_auto'].GetValue()
                self.camera.SetPropertyValue(prop, (red, blue), auto=auto)
        except:
            return
