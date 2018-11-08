import time
from PIL import Image
import numpy as np

import wx

try:
    import PyCapture2
except ImportError:
    print("Cannot load PyCapture2 library")

def map_attrs(object):
    out = {}
    for attr in dir(object):
        if attr.startswith('_'):
            continue
        out[attr.lower()] = getattr(object, attr)
    return out

PYCAP2_PROPERTIES  = map_attrs(PyCapture2.PROPERTY_TYPE)
PYCAP2_FILEFORMATS = map_attrs(PyCapture2.IMAGE_FILE_FORMAT)

def unbool(val):
    return {True:1, False: 0}[bool(val)]

class Fly2Camera(object):
    """PyCapture 2Camera object"""
    def __init__(self, camera_id=0, bus_manager=None):
        if bus_manager is None:
            bus_manager = PyCapture2.BusManager()
        self.busman = bus_manager

        if camera_id is not None:
            self.Connect(camera_id=camera_id)

    def Connect(self, camera_id=0):
        self.cam = PyCapture2.Camera()
        self.cam.connect(self.busman.getCameraFromIndex(camera_id))
        self.info = self.cam.getCameraInfo()

    def StartCapture(self):
        """"""
        self.cam.startCapture()

    def StopCapture(self):
        """"""
        self.cam.stopCapture()

    def GetProperty(self, name):
        if name not in PYCAP2_PROPERTIES:
            return None
        return self.cam.getProperty(PYCAP2_PROPERTIES[name])

    def GetPropertyDict(self, name):
        p = self.getProperty(name)
        return {"type": p.type,
                "present": bool(p.present),
                "autoManualMode": bool(p.autoManualMode),
                "absControl": bool(p.absControl),
                "onOff": bool(p.onOff),
                "onePush": bool(p.onePush),
                "absValue": p.absValue,
                "valueA": p.valueA,
                "valueB": p.valueB}

    def SetPropertyValue(self, name, value, auto=False, absolute=True):
        """Set Value for property.  Supports setting the properties
        'brightness', 'sharpness', 'hue', 'saturation', 'gamma',
        'shutter', 'gain', and 'white_balance' (see note below).

        Arguments
        ---------
        name       property name ('gamma', 'gain', 'shutter', ...)
        value      value for property
        absolute   whether value is absolute (physical units) default=True
        auto       whether to set autoManualMode              default=False

        Example
        -------
             context = pyfly2.Context()
             camera  = context.get_camera(0)
             camera.Connect()
             camera.SetProperty('gain', 2.0)

        Notes
        ------
           The 'white_balance' property takes a two-element tuple for values
           for red- and blue-white balance.  Absolute control is forced to be
           False.  To set the white balance, use something like

             camera.SetProperty('white_balance', (550, 800))
        """
        if name not in PYCAP2_PROPERTIES:
            return None

        prop = self.cam.getProperty(PYCAP2_PROPERTIES[name])

        prop.onOff = 1
        prop.autoManualMode = unbool(auto)

        if name == 'white_balance':
            prop.valueA = value[0]
            prop.valueB = value[1]
            prop.absValue = 0.0
            prop.absControl = 0
        else:
            prop.absControl = unbool(absolute)
            prop.absValue = value
        self.cam.setProperty(prop)

    def SaveImageFile(self, filename, format="png"):
        """save image to disk"""
        img = self.cam.retrieveBuffer().convert(PyCapture2.PIXEL_FORMAT.RGB)
        img.save(filename, PYCAP2_FILEFORMATS[format])

    def GetSize(self):
        """returns image size"""
        img = self.cam.retrieveBuffer()
        return (img.getCols(), img.getRows())

    def GrabColor(self, format='rgb'):
        img = self.cam.retrieveBuffer()
        if format == 'bgr':
            img = img.convert(PyCapture2.PIXEL_FORMAT.BGR)
        elif format == 'rgb':
            img = img.convert(PyCapture2.PIXEL_FORMAT.RGB)

        return img

    def GrabNumPyImage(self, format='rgb'):
        """return an image as a NumPy array
        optionally specifying color
        """
        img = self.cam.retrieveBuffer()
        ncols, nrows = img.getCols(), img.getRows()
        size = ncols * nrows
        shape = (ncols, nrows)
        if format == 'bgr':
            shape = (ncols, nrows, 3)
            img = img.convert(PyCapture2.PIXEL_FORMAT.BGR)
        elif format == 'rgb':
            shape = (ncols, nrows, 3)
            img = img.convert(PyCapture2.PIXEL_FORMAT.RGB)

        return np.array(img.getData()).reshape(shape)

    def GrabWxImage(self, scale=1.00, rgb=True, quality=wx.IMAGE_QUALITY_HIGH):
        """returns a wximage
        optionally specifying scale and color
        """
        img = self.cam.retrieveBuffer()
        ncols, nrows = img.getCols(), img.getRows()
        scale = max(scale, 0.05)
        width, height = int(scale*ncols), int(scale*nrows)
        if rgb:
            img = img.convert(PyCapture2.PIXEL_FORMAT.RGB)

        return wx.Image(ncols, nrows, np.array(img.getData())).Rescale(width, height,
                                                                       quality=quality)
    def GrabPILImage(self):
        """"""
        # We import PIL here so that PIL is only a requirement if you need PIL
        img = self.cam.retrieveBuffer()
        ncols, nrows = img.getCols(), img.getRows()
        return Image.frombytes('L', (ncols, nrows), img.getData())
