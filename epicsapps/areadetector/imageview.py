"""
Simple Image Viewing Window
"""
import wx

class ImageView(wx.Window):
    def __init__(self, parent, id=-1, pos=wx.DefaultPosition,
                 size=wx.DefaultSize, onzoom=None, onshow=None,
                 onprofile=None, **kw):
        wx.Window.__init__(self, parent, id, pos, size, **kw)

        self.image = None
        self.bmp = None
        self.can_resize = True
        self.SetBackgroundColour('#EEEEEE')
        self.Bind(wx.EVT_PAINT, self.DrawImage)
        self.Bind(wx.EVT_SIZE, self.OnSize)
        self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)
        self.Bind(wx.EVT_LEFT_UP, self.OnLeftUp)
        self.Bind(wx.EVT_MOTION, self.OnMotion)

        self.cursor_mode = 'zoom'
        self.onzoom = onzoom
        self.onshow = onshow
        self.onprofile = onprofile
        self.flipv = False
        self.fliph = False
        self.rot90 = 0
        self.zoom_box = None
        self.prof_line = None
        self.xy_init = None
        self.win_size = 1, 1

    def OnLeftDown(self, event=None):
        if self.cursor_mode in ('zoom', 'profile'):
            self.zoom_box = None
            self.prof_line = None
            self.xy_init = (event.GetX(), event.GetY())
            self.Refresh()

        #  elif self.cursor_mode == 'show':
        xoff = (self.win_size[0] - self.img_size[0])/2.0
        yoff = (self.win_size[1] - self.img_size[1])/2.0
        x = (event.GetX() - xoff)/ (1.0*self.img_size[0])
        y = (event.GetY() - yoff)/ (1.0*self.img_size[1])
        if hasattr(self.onshow, '__call__'):
            self.onshow(x, y)

    def OnLeftUp(self, event=None):
        """action on left up -- send fractional coordinates of image
        to onzoom or onprofile method"""
        # get offset of image within window and image size as floating point
        xoff  = (self.win_size[0] - self.img_size[0])/2.0
        yoff  = (self.win_size[1] - self.img_size[1])/2.0
        xsize = 1.0*self.img_size[0]
        ysize = 1.0*self.img_size[1]

        # make sure rot90 is either 0 or 1, adjusting flipv/fliph if needed
        self.rot90 = self.rot90 % 4
        if self.rot90 > 1:
            self.flipv, self.fliph = not self.flipv, not self.fliph
            self.rot90 = self.rot90 - 2

        if self.cursor_mode == 'zoom':
            if hasattr(self.onzoom, '__call__') and self.zoom_box is not None:
                x0  = (self.zoom_box[0] - xoff)/ xsize
                xw  =  self.zoom_box[2] / xsize
                y0  = (self.zoom_box[1] - yoff)/ ysize
                yw  =  self.zoom_box[3] / ysize
                if self.flipv:
                    y0 = 1-y0-yw
                if self.fliph:
                    x0 = 1-x0-xw
                if self.rot90 == 1:
                    x0, xw, y0, yw = y0, yw, 1-x0-xw, xw
                x1, y1 = x0+xw, y0+yw
                x0, y0 = max(0, min(1, x0)), max(0, min(1, y0))
                x1, y1 = max(0, min(1, x1)), max(0, min(1, y1))
                xw, yw = x1-x0, y1-y0
                self.onzoom(x0, y0, xw, yw)

        elif self.cursor_mode == 'profile':
            if hasattr(self.onprofile, '__call__') and self.prof_line is not None:
                x0  = (self.prof_line[0] - xoff) / xsize
                y0  = (self.prof_line[1] - yoff) / ysize
                x1  = (self.prof_line[2] - xoff) / xsize
                y1  = (self.prof_line[3] - yoff) / ysize
                if self.flipv:
                    y0, y1 = (1-y1), (1-y0)
                if self.fliph:
                    x0, x1 = (1-x1), (1-x0)
                if self.rot90 == 1:
                    x0, x1, y0, y1 = y0, y1, (1-x0), (1-x1)
                x0, y0 = max(0, min(1, x0)), max(0, min(1, y0))
                x1, y1 = max(0, min(1, x1)), max(0, min(1, y1))
                self.onprofile(x0, y0, x1, y1)
        self.zoom_box = None
        self.prof_line = None
        self.xy_init = None

    def OnMotion(self, event=None):
        if self.xy_init is None:
            return
        xi, yi = self.xy_init
        xe, ye = (event.GetX(), event.GetY())
        if self.cursor_mode == 'profile':
            self.updateDynamicBox((xi, yi, xe, ye))
        elif self.cursor_mode == 'zoom':
            x, w = min(xe, xi), abs(xe-xi)
            y, h = min(ye, yi), abs(ye-yi)
            self.updateDynamicBox((x, y, w, h))

    def updateDynamicBox(self, bbox, erase=False):
        "common dynamic update of zoom box or profile line"
        zdc = wx.ClientDC(self)
        zdc.SetLogicalFunction(wx.XOR)
        zdc.SetBrush(wx.TRANSPARENT_BRUSH)
        zdc.SetPen(wx.Pen('White', 2, wx.SOLID))
        zdc.ResetBoundingBox()
        if self.cursor_mode == 'profile':
            if self.prof_line is not None:
                zdc.DrawLine(*self.prof_line)
            if not erase:
                self.prof_line = bbox
                zdc.DrawLine(*self.prof_line)
        elif self.cursor_mode == 'zoom':
            if self.zoom_box is not None:
                zdc.DrawRectangle(*self.zoom_box)
            if not erase:
                self.zoom_box = bbox
                zdc.DrawRectangle(*self.zoom_box)

    def SetValue(self, image):
        self.image = image
        self.Refresh()

    def OnSize(self, event):
        if self.can_resize:
            self.DrawImage(size=event.GetSize())
            self.Refresh()
        event.Skip()

    def DrawImage(self, event=None, isize=None, size=None):
        if event is None:
            return
        if not hasattr(self, 'image') or self.image is None:
            return

        if size is None:   size = self.GetSize()
        try:
            w_win, h_win = size
        except:
            return

        img = self.image

        if isize is not None:
            w_img, h_img = isize
        elif img.IsOk():
            w_img = img.GetWidth()
            h_img = img.GetHeight()
        else:
            return

        xscale = float(w_win) / w_img
        yscale = float(h_win) / h_img

        scale = yscale
        if xscale < yscale:
            scale = xscale

        w_scaled = int(scale * w_img)
        h_scaled = int(scale * h_img)
        w_pad    = (w_win - w_scaled)/2
        h_pad    = (h_win - h_scaled)/2
        self.img_size = w_scaled, h_scaled
        self.win_size = w_win, h_win
        if self.flipv:
            img = img.Mirror(False)
        if self.fliph:
            img = img.Mirror(True)
        if self.rot90 != 0:
            for i in range(self.rot90):
                img = img.Rotate90(True)

        if w_scaled != w_img or h_scaled!=h_img:
            img = img.Scale(w_scaled, h_scaled)
        #dc = wx.PaintDC(self)
        #dc.DrawBitmap(wx.BitmapFromImage(img), w_pad, h_pad, useMask=True)
        dc = wx.BufferedPaintDC(self, wx.Bitmap(img))
        if self.zoom_box is not None:
            self.updateDynamicBox(self.zoom_box, erase=True)
        elif self.prof_line is not None:
            self.updateDynamicBox(self.prof_line, erase=True)
