"""Image Panel for Epics AreaDetector
"""

import wx
import time
import os
import shutil
import math
import numpy as np
from threading import Thread
from cStringIO import StringIO
import base64

from epics import PV, Device, caput
from epics.wx import EpicsFunction

import Image

class ImagePanel_EpicsAD(wx.Panel):
    img_attrs = ('ArrayData', 'UniqueId_RBV', 'NDimensions_RBV',
                 'ArraySize0_RBV', 'ArraySize1_RBV', 'ArraySize2_RBV',
                 'ColorMode_RBV')

    cam_attrs = ('Acquire', 'ArrayCounter', 'ArrayCounter_RBV',
                 'DetectorState_RBV',  'NumImages', 'ColorMode',
                 'ColorMode_RBV', 
                 'DataType_RBV',  'Gain',
                 'AcquireTime', 'AcquirePeriod', 'ImageMode',
                 'ArraySizeX_RBV', 'ArraySizeY_RBV')
    
    """Image Panel for FlyCapture2 camera"""
    def __init__(self, parent, prefix=None, format='JPEG',
                 writer=None, autosave_file=None, **kws):
        super(ImagePanel_EpicsAD, self).__init__(parent, -1, size=(800, 600))

        if prefix.endswith(':'):
            prefix = prefix[:-1]
        if prefix.endswith(':image1'):
            prefix = prefix[:-7]
        if prefix.endswith(':cam1'):
            prefix = prefix[:-5]

        self.ad_img = Device(prefix + ':image1:', delim='',
                                   attrs=self.img_attrs)
        self.ad_cam = Device(prefix + ':cam1:', delim='',
                                   attrs=self.cam_attrs)

        self.config_filesaver(prefix, format)

        width = self.ad_cam.ArraySizeX_RBV
        height = self.ad_cam.ArraySizeY_RBV
       
        self.img_w = float(width+0.5)
        self.img_h = float(height+0.5)
        self.writer = writer
        self.cam_name = '-'

        self.imgcount = 0
        self.imgcount_start = 0
        self.last_update = 0.0

        self.scale = 0.60
        self.count = 0
        self.last_size = 0

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
        if autosave_file is not None:
            path, tmp = os.path.split(autosave_file)
            self.autosave_file = autosave_file
            self.autosave_tmpf = os.path.join(path, '_tmp_.jpg')
        self.autosave_thread = Thread(target=self.onAutosave)
        self.autosave_thread.daemon = True

        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.onTimer, self.timer)


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

    def onSize(self, evt):
        frame_w, frame_h = self.last_size = evt.GetSize()
        self.scale = min(frame_w/self.img_w, frame_h/self.img_h)
        self.Refresh()
        evt.Skip()

    def onTimer(self, evt=None):
        self.Refresh()

    def onLeftDown(self, evt=None):
        print 'Left Down Event: ', evt.GetX(), evt.GetY()
        print 'Left Down Panel Size:  ', self.panel_size
        print 'Left Down Last Size:   ', self.last_size
        print 'Left Down Bitmap Size: ', self.bitmap_size
        print 'Left Down Image Scale: ', self.scale

    def onPaint(self, event):
        self.count += 1
        now = time.clock()
        elapsed = now - self.starttime
        if elapsed >= 2.0 and self.writer is not None:
            self.writer(" %.2f fps\n" % (self.count/elapsed))
            self.starttime = now
            self.count = 0

        self.scale = max(self.scale, 0.05)

        img =  self.GrabWxImage(scale=self.scale, rgb=True)
        if img is None:
            return
        self.image = img
        bitmap = wx.BitmapFromImage(self.image)
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

    def Start(self):
        "turn camera on"
        # print 'Epics AD START ' # self.camera.Connect()
        # self.cam_name = self.camera.info['modelName']
        # self.camera.StartCapture()
        self.timer.Start(50)
        self.autosave_thread.start()

    def Stop(self):
        "turn camera off"
        self.timer.Stop()
        self.autosave = False
        # self.camera.StopCapture()
        self.autosave_thread.join()

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
                    shutil.copy(self.autosave_tmpf,
                                self.autosave_file)
                except:
                    pass
                tfrac, tint = math.modf(time.time())
            # sleep for most of the remaining second
            time.sleep(max(0.05, 0.75*(1.0-tfrac)))

    def SaveImage(self, fname, filetype='jpeg'):
        """save image (jpeg) to file"""
        ftype = wx.BITMAP_TYPE_JPEG
        if filetype.lower() == 'png':
            ftype = wx.BITMAP_TYPE_PNG
        elif filetype.lower() in ('tiff', 'tif'):
            ftype = wx.BITMAP_TYPE_TIFF
        ## tmpimage = self.GrabWxImage(scale=self.scale, rgb=True)
        ## tmpimage.SaveFile(fname, ftype)
        return {'image_size': tmpimage.GetSize(), 
                'image_format': 'RGB', 
                'data_format': 'base64',
                'data': base64.b64encode(tmpimage.GetData())}

    def GrabImage(self):
        """return base64 encoded image data"""
        tmpimage = self.camera.GrabWxImage(scale=1, rgb=True)
        return {'image_size': tmpimage.GetSize(), 
                'image_format': 'RGB', 
                'data_format': 'base64',
                'data': base64.b64encode(tmpimage.GetData())}

    def GetImageSize(self):
        self.arrsize = [1,1,1]
        self.arrsize[0] = self.ad_img.ArraySize0_RBV
        self.arrsize[1] = self.ad_img.ArraySize1_RBV
        self.arrsize[2] = self.ad_img.ArraySize2_RBV
        self.colormode = self.ad_img.ColorMode_RBV
        self.img_w = float(self.arrsize[0]+0.5)
        self.img_h = float(self.arrsize[1]+0.5)
        if self.colormode == 2:
            self.img_w = float(self.arrsize[1]+0.5)
            self.img_h = float(self.arrsize[2]+0.5)

    def GrabWxImage(self, scale=1, rgb=True):
        if self.ad_img is None or self.ad_cam is None:
            return

        imgdim   = self.ad_img.NDimensions_RBV
        width    = self.ad_cam.SizeX
        height   = self.ad_cam.SizeY
      
        imgcount = self.ad_cam.ArrayCounter_RBV
        now = time.time()
        if (imgcount == self.imgcount or abs(now - self.last_update) < 0.025):
            return None
        self.imgcount = imgcount
        self.last_update = time.time()

        arrsize = [1,1,1]
        arrsize[0] = self.ad_img.ArraySize0_RBV
        arrsize[1] = self.ad_img.ArraySize1_RBV
        arrsize[2] = self.ad_img.ArraySize2_RBV

        colormode = self.ad_img.ColorMode_RBV
        im_mode = 'L'
        self.im_size = (arrsize[0], arrsize[1])
        if colormode == 2:
            im_mode = 'RGB'
            self.im_size = (arrsize[1], arrsize[2])
        
        dcount = arrsize[0] * arrsize[1]
        if imgdim == 3:
            dcount *= arrsize[2]

        rawdata = self.ad_img.PV('ArrayData').get(count=dcount)
        
        print "==== GrabImage ", im_mode, colormode, width, height, rawdata.dtype

        if (colormode == 0 and isinstance(rawdata, np.ndarray) and
            rawdata.dtype != np.uint8):
            im_mode = 'I'
            rawdata = rawdata.astype(np.uint32)

        print "==== GrabImage ", im_mode, width, height, rawdata[:4]
        if im_mode in ('L', 'I'):
            image = wx.EmptyImage(width, height)
            imbuff = Image.frombuffer(im_mode, self.im_size, rawdata,
                                      'raw',  im_mode, 0, 1)
            image.SetData(imbuff.convert('RGB').tostring())

        elif im_mode == 'RGB':
            rawdata.shape = (3, width, height)
            image = wx.ImageFromData(width, height, rawdata)

        return image.Scale(int(self.scale*width), int(self.scale*height))


xx = """
cname = "%s%s1:"% (self.cam_adpref, self.cam_adform.upper())
            caput("%sFileName" % cname, fname, wait=True)
            time.sleep(0.03)
            caput("%sWriteFile" % cname, 1, wait=True)
            time.sleep(0.05)
            img_ok = False
            t0 = time.time()
            while not img_ok:
                if time.time()-t0 > 15:
                    break
                try:
                    out = open(fname, "rb")
                    imgdata = base64.b64encode(out.read())
                    out.close()
                    img_ok = True
                except:
                    pass
                time.sleep(0.05)

    @EpicsFunction
    def Start(self):
        if not self.cam_adpref.endswith(':'):
            self.cam_adpref = "%s:" % self.cam_adpref
        cname = "%s%s1:"% (self.cam_adpref, self.cam_adform.upper())
        caput("%sEnableCallbacks" % cname, 1)
        thisdir = os.path.abspath(os.getcwd())
        thisdir = thisdir.replace('\\', '/').replace('T:/', '/Volumes/Data/')

        caput("%sFilePath" % cname, thisdir)
        caput("%sAutoSave" % cname, 0)
        caput("%sAutoIncrement" % cname, 0)
        caput("%sFileTemplate" % cname, "%s%s")
        if self.cam_adform.upper() == 'JPEG':
            caput("%sJPEGQuality" % cname, 90)
"""

