import wx
from cStringIO import StringIO
import base64
import array

class ImageDisplayFrame(wx.Frame):
    """ basic frame for displaying image

    """
    iw, ih, pad = 600, 450, 35
    def __init__(self, **kws):
        wx.Frame.__init__(self, None, -1,
                          style=wx.DEFAULT_FRAME_STYLE, **kws)
        self.wximage = None
        iw, ih = self.iw-self.pad, self.ih-self.pad
        self.bitmap = wx.StaticBitmap(self, -1,
                          wx.BitmapFromBuffer(iw, ih,
                             array.array('B', [220]*3*iw*ih)))

        self.Bind(wx.EVT_SIZE,  self.onSize)
        self.Bind(wx.EVT_CLOSE, self.onClose)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.bitmap, 1, 
                  wx.ALL|wx.GROW|wx.ALIGN_CENTER,  3)
        self.SetSizer(sizer)
        sizer.Fit(self)
        self.Show()
        self.SetSize((self.iw, self.ih))

        self.Raise()

    def showfile(self, fname, title=None):
        imdata = StringIO(open(fname, "rb").read())
        if title is not None:
            self.SetTitle(title)
        self.wximage = wx.ImageFromStream(imdata)
        self.show_bmp(self.wximage)

    def showb64img(self, data, title=None):
        imdata = base64.b64decode(data)
        if title is not None:
            self.SetTitle(title)
        self.wximage = wx.EmptyImage(self.iw-self.pad, self.ih-self.pad)
        self.wximage.SetData(imdata)
        self.show_bmp(self.wximage)

    def onSize(self, evt):
        self.iw, self.ih = evt.GetSize()
        # print 'onSize ', self.iw, self.ih, self.pad
        if self.wximage is not None:
            self.show_bmp(self.wximage)
        evt.Skip()

    def show_bmp(self, img):
        winw, winh = self.GetSize()
        imgw, imgh = img.GetSize()
        scale = min((winw*1.0 - self.pad)/imgw, (winh*1.0 - self.pad)/imgh)
        self.bitmap.SetBitmap(wx.BitmapFromImage(img.Scale(scale*imgw, 
                                                           scale*imgh)))
        self.Refresh()

    def onClose(self, event=None):
        self.Destroy()
