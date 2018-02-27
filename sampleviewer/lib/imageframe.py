import wx
from six import StringIO
import base64
import array

class ImageDisplayFrame(wx.Frame):
    """ basic frame for displaying image

    """
    iw, ih, pad = 700, 550, 15
    def __init__(self, **kws):
        wx.Frame.__init__(self, None, -1,
                          style=wx.DEFAULT_FRAME_STYLE, **kws)
        self.wximage = None
        iw, ih = self.iw-self.pad, self.ih-self.pad
        panel = wx.Panel(self)
        self.label = wx.StaticText(panel, -1, " "*200, size=(300, -1))

        self.bitmap = wx.StaticBitmap(panel, -1,
                                      wx.BitmapFromBuffer(iw, ih,
                                                          array.array('B', [220]*3*iw*ih)))

        self.Bind(wx.EVT_SIZE,  self.onSize)
        self.Bind(wx.EVT_CLOSE, self.onClose)

        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.Add(self.bitmap, 1,
                  wx.ALL|wx.GROW|wx.ALIGN_CENTER,  3)
        sizer.Add(self.label, 0,
                  wx.ALL|wx.GROW|wx.ALIGN_CENTER,  2)

        panel.SetSizer(sizer)
        sizer.Fit(panel)
        self.SetMinSize((iw, ih))
        self.SetSize((iw, ih))
        self.Show()
        self.Raise()

    def showfile(self, fname, title=None, label=None):
        imdata = StringIO(open(fname, "rb").read())
        if title is not None:
            self.SetTitle(title)
        if label is not None:
            self.label.SetLabel(label)
        self.wximage = wx.ImageFromStream(imdata)
        self.show_bmp(self.wximage)

    def showb64img(self, data, title=None, label=None):
        imdata = base64.b64decode(data)
        if title is not None:
            self.SetTitle(title)
        if label is not None:
            self.label.SetLabel(label)
        self.wximage = wx.EmptyImage(self.iw-self.pad, self.ih-self.pad)
        self.wximage.SetData(imdata)
        self.show_bmp(self.wximage)

    def onSize(self, evt):
        self.iw, self.ih = evt.GetSize()
        if self.wximage is not None:
            self.show_bmp(self.wximage)
        evt.Skip()

    def show_bmp(self, img):
        winw, winh = self.GetSize()
        winw = max(winw, 600)
        winh = max(winh, 400)
        imgw, imgh = img.GetSize()
        scale = min((winw*1.0 - self.pad)/imgw, (winh*1.0 - self.pad)/imgh)
        self.bitmap.SetBitmap(wx.BitmapFromImage(img.Scale(scale*imgw,
                                                           scale*imgh)))
        self.Refresh()

    def onClose(self, event=None):
        self.Destroy()
