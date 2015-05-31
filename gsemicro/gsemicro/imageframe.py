import wx
from cStringIO import StringIO
import base64

class ImageDisplayFrame(wx.Frame):
    """ basic frame for displaying image

    """
    iw, ih = 723, 543
    def __init__(self, **kws):
        wx.Frame.__init__(self, None, -1, size=(725, 550),
                          style=wx.DEFAULT_FRAME_STYLE, **kws)
        self.wximage = None
        self.bitmap = wx.StaticBitmap(self, -1,
                          wx.BitmapFromBuffer(self.iw, self.ih,
                             array.array('B', [220]*3*self.iw*self.ih))

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.img, 1, wx.ALL|wx.GROW, 1)
        self.Bind(wx.EVT_SIZE,  self.onSize)
        self.Bind(wx.EVT_CLOSE, self.onClose)

        self.SetSizer(sizer)
        sizer.Fit(self)
        self.Show()
        self.Raise()

    def showfile(self, fname, title=None):
        self.show_image(StringIO(open(fname, "rb").read()), title=title)

    def showb64img(self, data, title=None):
        self.show_image(base64.b64decode(data), title=title)

    def show_image(self, image, title=None):
        if title is not None:
            self.SetTitle(title)
        self.wximage = wx.ImageFromStream(image).Rescale(self.iw, self.ih)
        self.bitmap.SetBitmap(wx.BitmapFromImage(self.wximage))

    def onSize(self, evt):
        self.iw, self.ih = evt.GetSize()
        if self.wximage is not None:
            bmp = wx.BitmapFromImage(self.wximage.Rescale(self.iw, self.ih))
            self.bitmap.SetBitmap(bmp)
            self.Refresh()
        evt.Skip()

    def onClose(self, event=None):
        self.Destroy()
