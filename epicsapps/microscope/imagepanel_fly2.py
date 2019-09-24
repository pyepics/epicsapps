"""Image Panel using direct connection to PyCapture2 API
   for Point Grey FlyCapture2 cameras
"""
import numpy as np
import wx
import time
import os
from functools import partial
from epics import PV, Device, caput, poll
from epics.wx import DelayedEpicsCallback, EpicsFunction

from wxutils import pack, FloatCtrl

from .imagepanel_base import ImagePanel_Base, ConfPanel_Base

LEFT = wx.ALIGN_LEFT|wx.EXPAND

HAS_FLY2 = False
try:
    import PyCapture2
    from .fly2_camera import Fly2Camera
    HAS_FLY2 = True
except ImportError:
    pass

class ImagePanel_Fly2(ImagePanel_Base):
    """Image Panel for FlyCapture2 camera"""
    def __init__(self, parent,  camera_id=0, writer=None,
                 autosave_file=None, output_pv=None, **kws):
        if not HAS_FLY2:
            raise ValueError("PyCapture2 library not available")
        super(ImagePanel_Fly2, self).__init__(parent, -1,
                                              size=(800, 600),
                                              writer=writer,
                                              autosave_file=autosave_file,
                                              datapush=True, **kws)
        self.camera = Fly2Camera(camera_id=camera_id)
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

    def Stop(self):
        "turn camera off"
        self.timer.Stop()
        self.camera.StopCapture()

    def CaptureVideo(self, filename='Capture', format='MJPG', runtime=10.0):
        print(" in Capture Video!! ", runtime, filename)
        # print(" Current folder ", os.getcwd())
        framerate = 15.0
        numImages = max(15, 1 + runtime*framerate)
        self.Stop()
        time.sleep(0.02)
        t0 = time.time()
        avi = PyCapture2.AVIRecorder()
        self.camera.StartCapture()
        for i in range(numImages):
            try:
                image = self.camera.cam.retrieveBuffer()
            except PyCapture2.Fc2error as fc2Err:
                print( "dropped frame:", fc2Err)
                continue
            if i == 0:
                if format == "AVI":
                    avi.AVIOpen(filename, framerate)
                elif format == "MJPG":
                    print(" Open MJPG video")
                    avi.MJPGOpen(filename, framerate, 75)
                elif format == "H264":
                    avi.H264Open(filename, framerate, image.getCols(), image.getRows(), 1000000)
                else:
                    print("Specified format is not available.")
                    return
            # print(i, image)
            avi.append(image)
        print("saved file %s time = %.1f " % (filename, time.time()-t0))
        avi.close()
        self.Stop()
        self.Start()

    def SetExposureTime(self, exptime):
        self.camera.SetPropertyValue('shutter', exptime, auto=False)
        if self.confpanel is not None:
            self.confpanel.wids['shutter'].SetValue(exptime)
            self.confpanel.wids['shutter_auto'].SetValue(0)

    def AutoSetExposureTime(self):
        """auto set exposure time"""
        count, IMAX = 0, 255.0
        self.confpanel.wids['gain_auto'].SetValue(0)
        while count < 5:
            count += 1
            img = self.GrabNumpyImage()
            imgmax = img.max()
            imgave = img.mean()
            pgain = self.camera.GetProperty('gain').absValue
            atime = self.camera.GetProperty('shutter').absValue
            # print(" autoexposure ", count, imgmax, imgave, pgain, atime)
            if imgmax > 250:
                if  pgain > 4.0:
                    pgain = 0.75 * pgain
                    self.camera.SetPropertyValue('gain', pgain, auto=False)
                    self.confpanel.wids['gain'].SetValue(pgain)
                else:
                    self.SetExposureTime(0.75*atime)
            elif imgave < 100:
                if atime > 60:
                    pgain = 1.75 * pgain
                    self.camera.SetPropertyValue('gain', pgain, auto=False)
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
        # print("Fly Grab Wx ", img, nrows, ncols)
        self.data_shape = (nrows, ncols, 3)
        self.data = np.array(img.getData())
        self.full_image = wx.Image(ncols, nrows, self.data)
        return self.full_image.Rescale(width, height, quality=quality)

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
                                  action_kws={'prop': key}, size=(75, -1))
            label = '%s' % (key.title())
            if len(units)> 0:
                label = '%s (%s)' % (key.title(), units)
            sizer.Add(self.txt(label), (i, 0), (1, 1), LEFT)
            sizer.Add(wids[key],  (i, 1), (1, 1), LEFT)

            akey = '%s_auto' % key
            wids[akey] =  wx.CheckBox(self, -1, label='auto')
            wids[akey].SetValue(0)
            wids[akey].Bind(wx.EVT_CHECKBOX, partial(self.onAuto, prop=key))
            sizer.Add(wids[akey], (i, 2), (1, 1), LEFT)
            i = i + 1

        for color in ('blue', 'red'):
            key = 'wb_%s' % color
            wids[key] = FloatCtrl(self, value=0, maxval=1024,
                                  precision=0,
                                  action=self.onValue,
                                  act_on_losefocus=True,
                                  action_kws={'prop': key}, size=(75, -1))
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

        datapush_time = "%.1f" % self.image_panel.datapush_delay
        wids['dpush_time'] =  FloatCtrl(self, value=datapush_time, maxval=1e6,
                                        precision=1, minval=0,
                                        action=self.onValue, act_on_losefocus=True,
                                        action_kws={'prop':'autosave_time'}, size=(75, -1))

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

    def onEnableDataPush(self, evt=None, **kws):
        self.image_panel.datapush = evt.IsChecked()

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
        if prop == 'autosave_time':
            self.image_panel.datapush_delay = float(value)
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


class ImagePanel_Fly2AD(ImagePanel_Base):
    img_attrs = ('ArrayData',
                 'ArraySize0_RBV', 'ArraySize1_RBV', 'ArraySize2_RBV',
                 'ColorMode_RBV')

    """Image Panel for FlyCapture2 camera"""
    def __init__(self, parent, prefix=None, format='JPEG',
                 writer=None, autosave_file=None, **kws):
        super(ImagePanel_Fly2AD, self).__init__(parent, -1,
                                                size=(800, 600),
                                                writer=writer,
                                                autosave_file=False, **kws)

        self.format = format
        self.set_prefix(prefix)
        self.imgcount = 0
        self.imgcount_start = 0
        self.last_update = 0.0

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.onTimer, self.timer)

    def set_prefix(self, prefix):
        self.prefix = prefix
        self.ad_img = Device(prefix, delim='',
                             attrs=self.img_attrs)
        w, h = self.GetImageSize()
        self.cam_name = prefix

    def config_filesaver(self, prefix, format):
        pass

    def Start(self):
        "turn camera on"
        self.timer.Start(100)

    def Stop(self):
        "turn camera off"
        self.timer.Stop()

    def SetExposureTime(self, exptime):
        "set exposure time"
        pass

    def AutoSetExposureTime(self):
        """auto set exposure time"""
        pass

    def GetImageSize(self):
        arrsize0 = self.ad_img.ArraySize0_RBV
        arrsize1 = self.ad_img.ArraySize1_RBV
        arrsize2 = self.ad_img.ArraySize2_RBV
        self.arrsize   = (arrsize0, arrsize1, arrsize2)
        self.colormode = self.ad_img.ColorMode_RBV

        w, h  = arrsize1, arrsize2
        self.img_w = float(w+0.5)
        self.img_h = float(h+0.5)
        return w, h

    def GrabNumpyImage(self):
        return self.ad_img.PV('ArrayData')

    def GrabWxImage(self, scale=1, rgb=True, can_skip=True):
        if self.ad_img is None:
            print( 'GrabWxImage .. no ad_img ', self.ad_img)
            return

        width, height = self.GetImageSize()
        now = time.time()
        if (can_skip and (abs(now - self.last_update) < 0.15)):
            return None
        self.last_update = time.time()

        im_mode = 'RGB'
        self.im_size = (self.arrsize[1], self.arrsize[2])

        dcount = self.arrsize[0] * self.arrsize[1] * self.arrsize[2]

        rawdata = self.ad_img.PV('ArrayData').get(count=dcount)
        time.sleep(0.1)
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

class ConfPanel_Fly2AD(ConfPanel_Base):
    img_attrs = ('ArrayData', 'ArraySize0_RBV', 'ArraySize1_RBV',
                 'ArraySize2_RBV', 'ColorMode_RBV')

    def __init__(self, parent, image_panel=None, prefix=None,
                 center_cb=None, xhair_cb=None, **kws):
        super(ConfPanel_Fly2AD, self).__init__(parent, center_cb=center_cb,
                                                xhair_cb=xhair_cb)

        sizer = self.sizer
        self.image_panel = image_panel
        self.SetBackgroundColour('#EEFFE')
        self.title =  wx.StaticText(self, size=(285, 25),
                                    label="Fly2 Camera Mirror")
        labstyle  = wx.ALIGN_LEFT|wx.EXPAND|wx.ALIGN_BOTTOM
        sizer.Add(self.title,               (0, 0), (1, 3), labstyle)
        pack(self, sizer)
        self.set_prefix(prefix)

    @EpicsFunction
    def set_prefix(self, prefix):
        self.prefix = prefix
        self.ad_img = Device(prefix + ':image1:', delim='',
                             attrs=self.img_attrs)
        self.title.SetLabel("Fly2AD: %s" % prefix)
        self.connect_pvs()

    @EpicsFunction
    def connect_pvs(self, verbose=True):
        if self.prefix is None or len(self.prefix) < 2:
            return

        time.sleep(0.025)
        if not self.ad_img.PV('ColorMode_RBV').connected:
            poll()
            if not self.ad_img.PV('ColorMode_RBV').connected:
                return
        poll()
