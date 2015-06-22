"""Image Panel using direct connection to Fly2 API
   for Point Grey FlyCapture2 cameras
"""

import wx
import time

from .imagepanel_base import ImagePanel_Base
from epics.wx.utils import  pack, FloatCtrl, Closure

HAS_FLY2 = False
try:
    import pyfly2
    HAS_FLY2 = True
except ImportError:
    pass

class ImagePanel_Fly2(ImagePanel_Base):
    """Image Panel for FlyCapture2 camera"""
    def __init__(self, parent,  camera_id=0, writer=None,
                 autosave_file=None, **kws):
        super(ImagePanel_Fly2, self).__init__(parent, -1,
                                              size=(800, 600),
                                              writer=writer,
                                              autosave_file=autosave_file)

        self.context = pyfly2.Context()
        self.camera = self.context.get_camera(camera_id)
        self.img_w = 800.5
        self.img_h = 600.5
        self.writer = writer
        self.cam_name = '-'

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.onTimer, self.timer)

    def Start(self):
        "turn camera on"
        self.camera.Connect()
        self.cam_name = self.camera.info['modelName']
        try:
            self.camera.StartCapture()
            width, height = self.camera.GetSize()
            self.img_w = float(width+0.5)
            self.img_h = float(height+0.5)
        except:
            pass



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

    def GrabWxImage(self, scale=1, rgb=True):
        return self.camera.GrabWxImage(scale=scale, rgb=rgb)


class ConfPanel_Fly2(wx.Panel):
    def __init__(self, parent, image_panel=None, camera_id=0, **kws):
        super(ConfPanel_Fly2, self).__init__(parent, -1, size=(280, 300))
        self.image_panel = image_panel
        self.camera_id   = camera_id

        def txt(label, size=150):
            return wx.StaticText(self, label=label, size=(size, -1),
                                 style=wx.ALIGN_LEFT|wx.EXPAND)

        self.wids = wids = {}
        
        sizer = wx.GridBagSizer(10, 4)
        sizer.SetVGap(5)
        sizer.SetHGap(5)

        self.title = txt("Fly2Capture: ", size=285)
        
        sizer.Add(self.title, (0, 0), (1, 3), wx.ALIGN_LEFT|wx.EXPAND)        

        sizer.Add(txt('Property'), (1, 0), (1, 1), wx.ALIGN_LEFT|wx.EXPAND)
        sizer.Add(txt('Value', size=75),    (1, 1), (1, 1), wx.ALIGN_LEFT|wx.EXPAND)
        sizer.Add(txt('Auto', size=35),     (1, 2), (1, 1), wx.ALIGN_LEFT|wx.EXPAND)

        sizer.Add(wx.StaticLine(self, size=(3-5, 3), style=wx.ALIGN_CENTER|wx.EXPAND),
                  (2, 0), (1, 3), wx.ALIGN_CENTER|wx.EXPAND)
        
        
        i = 3
        for dat in (('Shutter speed (ms)', 60), ('Gain', 20),
                    ('Brightness', 100), ('Sharpness', 100), ('Hue', 100),
                    ('Saturation', 100), ('Gamma', 100),
                    ('White Balance (blue)', 1000),
                    ('White Balance (red)', 1000)):
            
            key, maxval = dat
            akey = 'auto_%s' % key
            wids[key] = FloatCtrl(self, value=0, maxval=maxval,
                                  precision=1,
                                  action=self.onValue,
                                  act_on_losefocus=True,
                                  action_kw={'property': key}, size=(35, -1))
            wids[akey] =  wx.CheckBox(self, -1, label='')
            wids[akey].SetValue(0)
            
            wids[akey].Bind(wx.EVT_CHECKBOX, Closure(self.onAuto, properyy=key))

            sizer.Add(txt(key),   (i, 0), (1, 1), wx.ALIGN_LEFT|wx.EXPAND)
            sizer.Add(wids[key],  (i, 1), (1, 1), wx.ALIGN_LEFT|wx.EXPAND)
            sizer.Add(wids[akey], (i, 2), (1, 1), wx.ALIGN_LEFT|wx.EXPAND)
            i = i + 1
            
        pack(self, sizer)

        wx.CallAfter(self.onConnect)
        
    def onConnect(self, **kws):
        print 'Connect Camera ', kws

    def onAuto(self, evt=None, property=None, **kws):
        print 'onAuto ', property, evt

    def onValue(self, evt=None, property=None, **kws):
        print 'onValue ', property, evt
        
