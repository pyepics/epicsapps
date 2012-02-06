""" Simple Image Viewing Window
"""

import wx

class ImageView(wx.Window):
    def __init__(self, parent, id=-1, pos=wx.DefaultPosition,
                 size=wx.DefaultSize, onzoom=None, onshow=None,
                 onprofile=None, **kw):
        wx.Window.__init__(self, parent, id, pos, size, **kw)
        
        self.image = None
        self.SetBackgroundColour('#EEEEEE')
        self.can_resize = True
        self.Bind(wx.EVT_PAINT, self.OnPaint)
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
        self.zoom_coords = None
        
    def OnLeftDown(self, event=None):
        if self.cursor_mode in ('zoom', 'profile'):
            self.zoom_box = None
            self.prof_line = None
            self.zoom_coords = [event.x, event.y]
            self.Refresh()

        elif self.cursor_mode == 'show':
            xoff = (self.win_size[0] - self.img_size[0])/2.0
            yoff = (self.win_size[1] - self.img_size[1])/2.0
            x = (event.x - xoff)/ (1.0*self.img_size[0])
            y = (event.y - yoff)/ (1.0*self.img_size[1])
            if hasattr(self.onshow, '__call__'):
                self.onshow(x, y)

                
    def OnLeftUp(self, event=None):
        if self.cursor_mode == 'zoom':
            self.zoom_coords = None
            if hasattr(self.onzoom, '__call__') and self.zoom_box is not None:
                xoff = (self.win_size[0] - self.img_size[0])/2.0
                yoff = (self.win_size[1] - self.img_size[1])/2.0
                x0  = (self.zoom_box[0] - xoff)/ (1.0*self.img_size[0])
                y0  = (self.zoom_box[1] - yoff)/ (1.0*self.img_size[1])
                x1  =  self.zoom_box[2] / (1.0*self.img_size[0])
                y1  =  self.zoom_box[3] / (1.0*self.img_size[1])
                self.onzoom(x0, y0, x1, y1)
            self.zoom_box = None
        elif self.cursor_mode == 'profile':
            # print 'draw profile',  
            # print (event.x, event.y) , self.zoom_coords,  self.prof_line

            if hasattr(self.onprofile, '__call__') and self.prof_line is not None:
                xoff = (self.win_size[0] - self.img_size[0])/2.0
                yoff = (self.win_size[1] - self.img_size[1])/2.0

                px0 = self.zoom_coords[0]
                py0 = self.zoom_coords[1]
                px1 = event.x
                py1 = event.y
                x0  = (px0 - xoff) / (1.0*self.img_size[0])
                y0  = (py0 - yoff) / (1.0*self.img_size[1])
                x1  = (px1 - xoff) / (1.0*self.img_size[0])
                y1  = (py1 - yoff) / (1.0*self.img_size[1])

                self.onprofile(x0, y0, x1, y1)

            self.zoom_box = None
            self.zoom_coords = None
            self.prof_line = None
            
    def OnMotion(self, event=None):
        if self.zoom_coords is None: 
            return

        if self.cursor_mode == 'zoom':
            x0 = min(event.x, self.zoom_coords[0])
            y0 = min(event.y, self.zoom_coords[1])
            w  = abs(event.x - self.zoom_coords[0])
            h  = abs(event.y - self.zoom_coords[1])

            zdc = wx.ClientDC(self)
            zdc.SetLogicalFunction(wx.XOR)
            zdc.SetBrush(wx.TRANSPARENT_BRUSH)
            zdc.SetPen(wx.Pen('White', 2, wx.SOLID))
            pen = zdc.GetPen()

            zdc.ResetBoundingBox()
            zdc.BeginDrawing()

            if self.zoom_box is not None:
                zdc.DrawRectangle(*self.zoom_box)
            self.zoom_box = (x0, y0, w, h)
            zdc.DrawRectangle(*self.zoom_box)
            zdc.EndDrawing()

        elif self.cursor_mode == 'profile':
            x0, y0 = self.zoom_coords
            zdc = wx.ClientDC(self)
            zdc.SetLogicalFunction(wx.XOR)
            zdc.SetBrush(wx.TRANSPARENT_BRUSH)
            zdc.SetPen(wx.Pen('White', 2, wx.SOLID))
            pen = zdc.GetPen()
            zdc.ResetBoundingBox()
            zdc.BeginDrawing()

            if self.prof_line is not None:
                zdc.DrawLine(*self.prof_line)
            self.prof_line = (x0, y0, event.x, event.y)
            zdc.DrawLine(*self.prof_line)
            zdc.EndDrawing()
        
    def SetValue(self, image):
        self.image = image
        self.Refresh()
    
    def OnSize(self, event):
        if self.can_resize:
            self.DrawImage(size=event.GetSize())
            self.Refresh()
        event.Skip()

    def OnPaint(self, event):
        self.DrawImage()

    def DrawImage(self, dc=None, isize=None, size=None):
        if not hasattr(self, 'image') or self.image is None:
            return

        if size is None:
            size = self.GetSize()
        try:
            wwidth, wheight = size
        except:
            return

        image = self.image
        bmp = None
        if isize is not None:
            iwidth, iheight = isize
        elif image.IsOk():
            iwidth = image.GetWidth()   
            iheight = image.GetHeight()
        else:
            bmp = wx.ArtProvider.GetBitmap(wx.ART_MISSING_IMAGE,
                                           wx.ART_MESSAGE_BOX, (64,64))
            iwidth  = bmp.GetWidth()
            iheight = bmp.GetHeight()
  
        xfactor = float(wwidth) / iwidth
        yfactor = float(wheight) / iheight

        scale = yfactor
        if xfactor < yfactor:
            scale = xfactor

        owidth = int(scale*iwidth)
        oheight = int(scale*iheight)
        diffx = (wwidth - owidth)/2   # center calc
        diffy = (wheight - oheight)/2   # center calc
        self.img_size = owidth, oheight
        self.win_size = wwidth, wheight

        if self.flipv:
            image = image.Mirror(False)
        if self.fliph:
            image = image.Mirror(True)
        if self.rot90 != 0:
            if self.rot90 == 3:
                image = image.Rotate90(False)
            elif self.rot90 == 1:
                image = image.Rotate90(True)
            elif self.rot90 == 2:
                image = image.Rotate90(True).Rotate90(True)

        if bmp is None:
            if owidth!=iwidth or oheight!=iheight:
                image = image.Scale(owidth, oheight)
            bmp = image.ConvertToBitmap()
        if dc is None:
            try:
                dc = wx.PaintDC(self)
            except:
                pass
        if dc is not None:
            dc.DrawBitmap(bmp, diffx, diffy, useMask=True)


        if self.zoom_box is not None or self.prof_line is not None:
            zdc = wx.ClientDC(self)
            zdc.SetLogicalFunction(wx.XOR)
            zdc.SetBrush(wx.TRANSPARENT_BRUSH)
            zdc.SetPen(wx.Pen('White', 2, wx.SOLID))
            pen = zdc.GetPen()

            zdc.ResetBoundingBox()
            zdc.BeginDrawing()
            if self.zoom_box is not None:
                zdc.DrawRectangle(*self.zoom_box)
            if self.prof_line is not None:
                zdc.DrawLine(*self.prof_line)

            zdc.EndDrawing()
            
