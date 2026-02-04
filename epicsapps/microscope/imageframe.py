import wx
import base64
import array


class PhotoFrame(wx.Frame):
    def __init__(self, image_path=None, **kws):
        wx.Frame.__init__(self, None, -1, size=(725, 525), 
                          style=wx.DEFAULT_FRAME_STYLE, **kws)        
        self.panel = wx.Panel(self)
        self.iw = 700
        self.ih = 500
        self.image_path = None
        bitmap = wx.Bitmap(self.iw-10, self.ih-10, depth=24)
        self.static_bitmap = wx.StaticBitmap(self.panel, wx.ID_ANY, bitmap)
        if image_path is not None:
            self.showfile(image_path)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.static_bitmap, 1, wx.ALL|wx.EXPAND, 5)
        self.panel.SetSizerAndFit(sizer)
        self.Bind(wx.EVT_SIZE,  self.onSize)        
        self.Layout()
        self.Show()

    def showfile(self, image_path, title=None):
        self.image_path = image_path
        try:
            img = wx.Image(image_path, wx.BITMAP_TYPE_ANY)
            w, h = img.GetSize()
            scale = min((self.iw-5)/(w+1.0), (self.ih-5)/(h+1))
            self.img = img.Scale(int(scale*w-5), int(scale*h-5), wx.IMAGE_QUALITY_HIGH)
            self.static_bitmap.SetBitmap(wx.Bitmap(self.img))
        except:
            wx.MessageBox(f"Cannot load image file '{image_path}'", "Error", wx.OK | wx.ICON_ERROR)
            
        if title is not None:
            self.SetTitle(title)

    def onSize(self, evt):
        self.iw, self.ih = evt.GetSize()
        if self.image_path is not None:
            self.showfile(self.image_path)
        evt.Skip()            
            
        
class ImageDisplayFrame(wx.Frame):
    """ basic frame for displaying image

    """
    iw, ih, pad = 700, 550, 15
    def __init__(self, **kws):
        wx.Frame.__init__(self, None, -1, size=(700, 550), 
                          style=wx.DEFAULT_FRAME_STYLE, **kws)

        self.wximage = None
        iw, ih = self.iw-self.pad, self.ih-self.pad
        panel = wx.Panel(self)
        self.label = wx.StaticText(panel, -1, " "*200, size=(300, -1))
        bmap = wx.Bitmap(iw, ih, 8)
        self.bitmap = wx.StaticBitmap(panel, -1, bmap)

        self.Bind(wx.EVT_SIZE,  self.onSize)
        self.Bind(wx.EVT_CLOSE, self.onClose)

        sizer = wx.BoxSizer(wx.VERTICAL)

        sizer.Add(self.bitmap, 1,  wx.ALL|wx.ALIGN_CENTER,  3)
        sizer.Add(self.label, 0, wx.ALL|wx.ALIGN_CENTER,  2)

        panel.SetSizer(sizer)
        s = self.GetBestSize()
        self.SetMinSize((iw, ih))
        sizer.Fit(panel)
        self.Show()
        self.Raise()

    def showfile(self, fname, title=None, label=None):
        if title is not None:
            self.SetTitle(title)
        if label is not None:
            self.label.SetLabel(label)
        self.wximage = wx.Image(fname, wx.BITMAP_TYPE_ANY)
        print("Show File ", fname, self.wximage)
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
        print("Show BMP ", img)
        winw = max(winw, 600)
        winh = max(winh, 400)
        # imgw, imgh = img.GetSize()
        # scale = min((winw*1.0 - self.pad)/imgw, (winh*1.0 - self.pad)/imgh)
        # ximg = img.Rescale(winw-self.pad, winh-self.pad)
        self.bitmap.SetBitmap(wx.Bitmap(img))
        self.Refresh()

    def onClose(self, event=None):
        self.Destroy()
