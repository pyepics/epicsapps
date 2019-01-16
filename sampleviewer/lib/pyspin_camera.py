import time
import atexit
from PIL import Image
import numpy as np

import wx

try:
    import PySpin
except ImportError:
    print("Cannot load PySpin library")

def map_attrs(object):
    out = {}
    for attr in dir(object):
        if attr.startswith('_'):
            continue
        out[attr.lower()] = getattr(object, attr)
    return out

pixel_formats = {'bgr': PySpin.PixelFormat_BGR8,
                 'rgb': PySpin.PixelFormat_RGB8,
                 'mono': PySpin.PixelFormat_Mono8}


integer_props = ['Width', 'Height', 'OffsetX', 'OffsetY']

float_props = ['Gain', 'Gamma', 'ExposureTime']
balance_props = ['WhiteBalance']

all_props = balance_props + float_props + integer_props

class PySpinCamera(object):
    """PySpin Camera object"""
    def __init__(self, camera_id=0):
        self._system = PySpin.System.GetInstance()
        self._cameras = self._system.GetCameras()
        if camera_id is not None:
            self.Connect(camera_id=camera_id)
        atexit.register(self.Exit)

    def Connect(self, camera_id=0):
        self.cam = self._cameras[camera_id]
        self.cam.Init()
        self.device_id = self.cam.TLDevice.DeviceID.GetValue()
        self.device_name = self.cam.TLDevice.DeviceModelName.GetValue()
        self.device_version = self.cam.TLDevice.DeviceVersion.GetValue()
        self.nodemap_tldevice = self.cam.GetTLDeviceNodeMap()
        self.nodemap = self.cam.GetNodeMap()
        self.SetFullSize()

    def StartCapture(self):
        """start capture"""
        self.cam.Init()
        acq_mode = PySpin.CEnumerationPtr(self.nodemap.GetNode('AcquisitionMode'))
        acq_mode.SetIntValue(acq_mode.GetEntryByName('Continuous').GetValue())
        self.cam.BeginAcquisition()

    def StopCapture(self):
        """"""
        self.cam.EndAcquisition()

    def Exit(self):
        self.StopCapture()
        self.cam.DeInit()
        self._cameras.Clear()
        del self.cam
        del self.nodemap
        self._system.ReleaseInstance()

    def SetFullSize(self):
        ptr = PySpin.CIntegerPtr
        for name in ('Height', 'Width'):
            prop = ptr(self.nodemap.GetNode(name))
            prop.SetValue(prop.GetMax())
        for name in ('OffsetX', 'OffsetY'):
            prop = ptr(self.nodemap.GetNode(name))
            prop.SetValue(0)
        self.SetGamma(1.0)
        self.SetGain(1, auto=False)
        self.SetExposureTime(50.0, auto=False)

    def GetWhiteBalance(self):
        """ Get White Balance (red, blue)"""
        wb_auto = PySpin.CEnumerationPtr(self.nodemap.GetNode('BalanceWhiteAuto'))
        wb_auto.SetIntValue(wb_auto.GetEntryByName('Off').GetValue())
        wb_ratio = PySpin.CEnumerationPtr(self.nodemap.GetNode('BalanceRatioSelector'))

        # Blue
        wb_ratio.SetIntValue(wb_ratio.GetEntryByName('Blue').GetValue())
        blue = PySpin.CFloatPtr(self.nodemap.GetNode('BalanceRatioRaw')).GetValue()

        # Red
        wb_ratio.SetIntValue(wb_ratio.GetEntryByName('Red').GetValue())
        red = PySpin.CFloatPtr(self.nodemap.GetNode('BalanceRatioRaw')).GetValue()
        return blue, red

    def GetGamma(self):
        """ Get Gamma"""
        return PySpin.CFloatPtr(self.nodemap.GetNode('Gamma')).GetValue()

    def GetGain(self):
        """ Get Gain"""
        return PySpin.CFloatPtr(self.nodemap.GetNode('Gain')).GetValue()

    def GetExposureTime(self):
        """ Get Exposure Time (in milliseconds)"""
        usec = PySpin.CFloatPtr(self.nodemap.GetNode('ExposureTime')).GetValue()
        return usec * 1.e-3

    def SetWhiteBalance(self, blue, red, auto=False):
        """Set white balance blue, red values

        Arguments
        ---------
        blue     value for blue
        red      value for red
        auto     whether to set auto [default=False]

        """
        wb_auto = PySpin.CEnumerationPtr(self.nodemap.GetNode('BalanceWhiteAuto'))
        sauto = 'Off'
        if auto:
            wb_auto.SetIntValue(wb_auto.GetEntryByName('Once').GetValue())
        else:
            wb_auto.SetIntValue(wb_auto.GetEntryByName('Off').GetValue())
            wb_ratio = PySpin.CEnumerationPtr(self.nodemap.GetNode('BalanceRatioSelector'))

            # set Blue
            wb_ratio.SetIntValue(wb_ratio.GetEntryByName('Blue').GetValue())
            PySpin.CFloatPtr(self.nodemap.GetNode('BalanceRatioRaw')).SetValue(blue)

            # set Red
            wb_ratio.SetIntValue(wb_ratio.GetEntryByName('Red').GetValue())
            PySpin.CFloatPtr(self.nodemap.GetNode('BalanceRatioRaw')).SetValue(red)

    def SetGamma(self, value):
        """Set Gamma
        Arguments
        ---------
        value      gain value
        """
        PySpin.CFloatPtr(self.nodemap.GetNode('Gamma')).SetValue(value)

    def SetGain(self, value=None, auto=False):
        """Set Gain
        Arguments
        ---------
        value      gain value
        auto       whether to set to auto [default=False]
        """
        node_main = self.nodemap.GetNode('Gain')
        node_auto = PySpin.CEnumerationPtr(self.nodemap.GetNode('GainAuto'))
        sauto = 'Off'
        if auto:
            sauto = 'Continuous'
        node_auto.SetIntValue(node_auto.GetEntryByName(sauto).GetValue())
        if (not auto) and value is not None:
            PySpin.CFloatPtr(node_main).SetValue(value)
        node_auto.SetIntValue(node_auto.GetEntryByName('Off').GetValue())

    def SetExposureTime(self, value=None, auto=False):
        """Set Exposure Time
        Arguments
        ---------
        value      exposure time (in milliseconds)
        auto       whether to set to auto [default=False]
        """
        node_main = self.nodemap.GetNode('ExposureTime')
        node_auto = PySpin.CEnumerationPtr(self.nodemap.GetNode('ExposureAuto'))
        sauto = 'Off'
        if auto:
            sauto = 'Continuous'
        node_auto.SetIntValue(node_auto.GetEntryByName(sauto).GetValue())
        if (not auto) and value is not None:
            value *= 1.e3   # exposure time is in microseconds
            PySpin.CFloatPtr(node_main).SetValue(value)
        node_auto.SetIntValue(node_auto.GetEntryByName('Off').GetValue())

    def SaveImageFile(self, filename, format="jpg"):
        """save image to disk"""
        img = self.cam.GetNextImage()
        img.Convert(pixel_formats['rgb']).Save(filename)
        img.Release()

    def GetSize(self):
        """returns image size"""
        img = self.cam.GetNextImage()
        size = (img.GetHeight(), img.GetWidth())
        img.Release()
        return size

    def GrabColor(self, format='rgb'):
        img = self.cam.GetNextImage()
        if format in pixel_formats:
            out = img.Convert(pixel_formats[format], PySpin.HQ_LINEAR)
            img.Release()
            img = out
        return img

    def GrabNumPyImage(self, format='rgb'):
        """return an image as a NumPy array
        optionally specifying color
        """
        img = self.cam.GetNextImage()
        ncols, nrows = img.GetHeight(), img.GetWidth()
        print(ncols, nrows)
        size = ncols * nrows
        shape = (ncols, nrows)
        if format in ('rgb', 'bgr'):
            shape = (ncols, nrows, 3)

        out = img.Convert(pixel_formats[format], PySpin.HQ_LINEAR)
        img.Release()
        return out.GetData().reshape(shape)

    def GrabWxImage(self, scale=1.00, rgb=True, quality=wx.IMAGE_QUALITY_HIGH):
        """returns a wximage
        optionally specifying scale and color
        """
        t0 = time.time()
        img = self.cam.GetNextImage()
        t1 = time.time() -t0
        ncols, nrows = img.GetHeight(), img.GetWidth()
        scale = max(scale, 0.05)
        width, height = int(scale*nrows), int(scale*ncols)
        format = 'mono'
        if rgb:
            format = 'rgb'
        out = img.Convert(pixel_formats[format])
        img.Release()
        t2 = time.time() - t0
        wxim =  wx.Image(nrows, ncols, np.array(out.GetData())).Rescale(width, height)
        t3 = time.time() - t0
        return wxim

    #
    #,
    #                                                                  quality=quality)
    def GrabPILImage(self):
        """"""
        # We import PIL here so that PIL is only a requirement if you need PIL
        img = self.cam.GetNextImage()
        ncols, nrows = img.GetHeight(), img.GetWidth()
        out = Image.frombytes('L', (ncols, nrows), img.GetData())
        img.Release()
        return out
