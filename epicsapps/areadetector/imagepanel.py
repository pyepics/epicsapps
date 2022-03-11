"""
Base Image Panel to be inherited by other ImagePanels
"""
import wx
import time
import numpy as np

from collections import deque
from epics import PV, Device, poll
from epics.wx import EpicsFunction, DelayedEpicsCallback
from wxutils import MenuItem

PIXEL_FMT  = "Pixel (%d, %d) Intensity=%.1f"
MAX_INT32  = 2**32
NMAX_INT32 = MAX_INT32 - 2**14

MAX_INT16  = 2**16
NMAX_INT16 = MAX_INT16 - 32

class ThumbNailImagePanel(wx.Panel):
    def __init__(self, parent, imgsize=50, size=(200, 200),
                 motion_writer=None, **kws):
        self.imgsize = max(10, imgsize)
        self.motion_writer = motion_writer
        super(ThumbNailImagePanel, self).__init__(parent, -1, size=size)
        self.contrast_levels = [1, 99.0]
        self.SetBackgroundColour("#CCBBAAA")
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.SetSize(size)
        self.data = None
        self.scale = 1.0
        self.xcen = self.ycen = self.x = self.y = 0
        self.Bind(wx.EVT_PAINT, self.onPaint)
        self.Bind(wx.EVT_MOTION, self.onMotion)

    def onPaint(self, evt=None):
        data, xcen, ycen = self.data, self.xcen, self.ycen
        if data is None or xcen is None or ycen is None:
            return
        jmin, jmax = np.percentile(data, self.contrast_levels)
        data = (np.clip(data, jmin, jmax) - jmin)/(jmax+0.001)
        h, w = data.shape

        if ycen < self.imgsize/2.0:
            hmin, hmax = 0, self.imgsize
        elif ycen > h - self.imgsize/2.0:
            hmin, hmax = h-self.imgsize, h
        else:
            hmin = int(ycen-self.imgsize/2.0)
            hmax = int(ycen+self.imgsize/2.0)
        if xcen < self.imgsize/2.0:
            wmin, wmax = 0, self.imgsize
        elif xcen > w - self.imgsize/2.0:
            wmin, wmax = w-self.imgsize, w
        else:
            wmin = int(xcen-self.imgsize/2.0)
            wmax = int(xcen+self.imgsize/2.0)

        data = data[hmin:hmax, wmin:wmax]
        hs, ws = data.shape
        self.lims = (hmin, wmin)
        if callable(self.colormap):
            data = self.colormap(data)
            if data.shape[2] == 4: # with alpha channel
                image = wx.Image(ws, hs,
                                 (data[:,:,:3]*255.).astype('uint8'),
                                 (data[:,:,3]*255.).astype('uint8'))
            else:
                image = wx.Image(ws, hs, (data*255.).astype('uint8'))
        else:
            rgb = np.zeros((self.imgsize, self.imgsize, 3), dtype='float')
            rgb[:, :, 0] = rgb[:, :, 1] = rgb[:, :, 2] = data
            image = wx.Image(self.imgsize, self.imgsize,
                             (rgb*255.).astype('uint8'))
        fh, fw = self.GetSize()
        scale = max(0.10, min(0.98*fw/(ws+0.1), 0.98*fh/(hs+0.1)))
        self.scale = scale
        image = image.Scale(int(scale*ws), int(scale*hs))
        bitmap = wx.Bitmap(image)
        bw, bh = bitmap.GetSize()
        pad_w, pad_h = int(1+(fw-bw)/2.0), int(1+(fh-bh)/2.0)
        self.pad = pad_h, pad_w
        dc = wx.AutoBufferedPaintDC(self)
        dc.Clear()
        dc.DrawBitmap(bitmap, pad_w, pad_h, useMask=True)

        if (self.y > -1 and self.y <  h and self.x > -1 and self.x < w and
            self.motion_writer is not None):
            self.show_motion()

    def show_motion(self):
        if self.motion_writer is not None:
            message = PIXEL_FMT % (self.x, self.y, self.data[self.y, self.x])
            self.motion_writer(message)

    def onMotion(self, evt=None):
        """report motion events within image"""
        evt_x, evt_y = evt.GetX(), evt.GetY()

        self.x = int(0.5 + (evt_x - self.pad[1])/self.scale) + self.lims[1]
        self.y = int(0.5 + (evt_y - self.pad[0])/self.scale) + self.lims[0]
        self.show_motion()


class ADMonoImagePanel(wx.Panel):
    """Image Panel for monochromatic Area Detector"""

    ad_attrs = ('image1:ArrayData', 'image1:ArraySize0_RBV',
                'image1:ArraySize1_RBV', 'cam1:ArrayCounter_RBV')

    def __init__(self, parent, prefix=None, writer=None,
                 motion_writer=None, draw_objects=None, rot90=0,
                 thumbnail=None,
                 contrast_level=0, size=(600, 600), **kws):

        super(ADMonoImagePanel, self).__init__(parent, -1, size=size)
        self.drawing = False
        self.adcam = None
        self.image_id = -1
        self.x = self.y = 0
        self.writer = writer
        self.motion_writer = motion_writer
        self.thumbnail = thumbnail
        self.thumbmode = 'click'
        self.scale = 0.8
        self.colormap = None
        self.contrast_levels = [contrast_level, 100.0-contrast_level]
        self.rot90 = rot90
        self.flipv = False
        self.fliph = False
        self.image = None
        self.bitmap_size = (2, 2)
        self.data = np.arange(25).reshape(5, 5)
        self.panel_size = self.GetSize()
        self.draw_objects = None
        self.SetBackgroundColour("#E4E4E4")
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.Bind(wx.EVT_SIZE, self.onSize)
        self.Bind(wx.EVT_PAINT, self.onPaint)
        if self.motion_writer is not None:
            self.Bind(wx.EVT_MOTION, self.onMotion)
        self.Bind(wx.EVT_LEFT_DOWN, self.onLeftDown)
        self.Bind(wx.EVT_RIGHT_DOWN, self.onRightDown)

        self.build_popupmenu()
        self.connect_pvs(prefix)
        self.restart_fps_counter()


    def restart_fps_counter(self, nsamples=100):
        self.capture_times = deque([], maxlen=nsamples)
        if self.writer is not None:
            self.writer("")

    def connect_pvs(self, prefix):
        self.adcam = Device(prefix,  delim='', attrs=self.ad_attrs)
        self.adcam.add_callback('cam1:ArrayCounter_RBV', self.onNewImage)

    def GetImageSize(self):
        return  (self.adcam.get('image1:ArraySize0_RBV'),
                 self.adcam.get('image1:ArraySize1_RBV'))

    def onMotion(self, evt=None):
        """report motion events within image"""
        if self.motion_writer is None and self.thumbnail is None:
            return
        if self.thumbmode == 'live':
            self.show_thumbnail(evt.GetX(), evt.GetY())

    def show_thumbnail(self, evt_x, evt_y):
        img_w, img_h = self.bitmap_size
        if self.rot90 in (1, 3):
            img_w, img_h = img_h, img_w
        pan_w, pan_h = self.panel_size
        pad_w, pad_h = (pan_w-img_w)/2.0, (pan_h-img_h)/2.0

        x = int(0.5 + (evt_x - pad_w)/self.scale)
        y = int(0.5 + (evt_y - pad_h)/self.scale)
        if self.rot90 in (1, 3):
            x, y = y, x
        self.x, self.y = x, y
        dh, dw = self.data.shape
        if y > -1 and y <  dh and x > -1 and x < dw:
            self.motion_writer(PIXEL_FMT %(x, y, self.data[y, x]))
            if self.thumbnail is not None:
                self.thumbnail.xcen = x
                self.thumbnail.ycen = y
                self.thumbnail.Refresh()
        else:
            self.motion_writer('')

    def build_popupmenu(self):
        self.popup_menu = popup = wx.Menu()
        MenuItem(self, popup, 'Follow Cursor for Thumbnail', '',
                 self.thumb_motion_mode)
        MenuItem(self, popup, 'Left Click to Show Thumbnail', '',
                 self.thumb_click_mode)

    def thumb_motion_mode(self, evt=None):
        self.thumbmode = 'live'

    def thumb_click_mode(self, evt=None):
        self.thumbmode = 'click'

    def onLeftDown(self, evt=None):
        if self.thumbmode == 'click':
            self.show_thumbnail(evt.GetX(), evt.GetY())

    def onRightDown(self, evt=None):
        wx.CallAfter(self.PopupMenu, self.popup_menu, evt.GetPosition())

    @DelayedEpicsCallback
    def onNewImage(self, pvname=None, value=None, **kws):
        if value > self.image_id and not self.drawing:
            self.drawing = True
            self.image_id = value
            self.Refresh()
            self.drawing = False


    def GrabNumpyImage(self):
        """get raw image data, as numpy ndarray, correctly shaped"""
        if True:
            data = self.adcam.PV('image1:ArrayData').get()
        else: # except:
            data = None
        if data is not None:
            w, h = self.GetImageSize()
            data = data.reshape((h, w))

            if self.flipv:
                data = data[::-1, :]
            if self.fliph:
                data = data[:, ::-1]
            if self.rot90 == 1:
                data = data.transpose()
            elif self.rot90 == 2:
                data = data[::-1, ::-1]
            elif self.rot90 == 3:
                data = data[::-1, ::-1].transpose()

            maxval = data.max()

            if maxval > NMAX_INT32:
                data[np.where(data>NMAX_INT32)] = -1
                # print("data is 32 bit")                
            elif (maxval > NMAX_INT16 and maxval < MAX_INT16 + 15): # data in 16-bit
                data[np.where(data>NMAX_INT16)] = -1
                # print("data is 16 bit")
            data[np.where(data<-1)] = -1
        poll()
        return data

    def GrabWxImage(self):
        """get wx Image:
        - scaled in size
        - color table applied
        - flipped and/or rotated
        - contrast levels set
        """
        data = self.GrabNumpyImage()
        if data is None:
            print("no data")
            return
        self.capture_times.append(time.time())
        self.data = data
        jmin, jmax = np.percentile(data, self.contrast_levels)
        if self.thumbnail is not None:
            self.thumbnail.contrast_levels = self.contrast_levels
            self.thumbnail.colormap = self.colormap

        data = (np.clip(data, jmin, jmax) - jmin)/(jmax+0.001)
        h, w = data.shape # self.GetImageSize()

        if callable(self.colormap):
            data = self.colormap(data)
            if data.shape[2] == 4: # with alpha channel
                image = wx.Image(w, h,
                                 (data[:,:,:3]*255.).astype('uint8'),
                                 (data[:,:,3]*255.).astype('uint8'))
            else:
                image = wx.Image(w, h, (data*255.).astype('uint8'))
        else:
            rgb = np.zeros((h, w, 3), dtype='float')
            rgb[:, :, 0] = rgb[:, :, 1] = rgb[:, :, 2] = data
            image = wx.Image(w, h, (rgb*255.).astype('uint8'))

        return image.Scale(int(self.scale*w), int(self.scale*h))

    def onSize(self, evt=None):
        if evt is not None:
            fh, fw = evt.GetSize()
        else:
            fh, fw = self.GetSize()

        h, w = self.GetImageSize()
        if self.rot90 in (1, 3):
            w, h = h, w

        self.scale = max(0.10, min(0.98*fw/(w+0.1), 0.98*fh/(h+0.1)))
        wx.CallAfter(self.Refresh)

    def onPaint(self, event):
        image = self.GrabWxImage()
        if image is None:
            return
        if len(self.capture_times) > 2 and self.writer is not None:
            ct = self.capture_times
            fps = (len(ct)-1) / (ct[-1]-ct[0])
            self.writer("Image %d: %.1f fps" % (self.image_id, fps))
        bitmap = wx.Bitmap(image)
        self.full_size = image.GetSize()
        bmp_w, bmp_h = self.bitmap_size = bitmap.GetSize()
        pan_w, pan_h = self.panel_size = self.GetSize()
        pad_w, pad_h = int(1+(pan_w-bmp_w)/2.0), int(1+(pan_h-bmp_h)/2.0)
        dc = wx.AutoBufferedPaintDC(self)
        dc.Clear()
        dc.DrawBitmap(bitmap, pad_w, pad_h, useMask=True)
        x, y = self.x, self.y
        dh, dw = self.data.shape
        if y > -1 and y <  dh and x > -1 and x < dw:
            self.motion_writer(PIXEL_FMT %(x, y, self.data[y, x]))
        if self.thumbnail is not None:
            self.thumbnail.data = self.data
            self.thumbnail.Refresh()


    def __draw_objects(self, dc, img_w, img_h, pad_w, pad_h):
        dc.SetBrush(wx.Brush('Black', wx.BRUSHSTYLE_TRANSPARENT))
        if self.draw_objects is not None:
            for obj in self.draw_objects:
                shape = obj.get('shape', None)
                color = obj.get('color', None)
                if color is None:
                    color = obj.get('colour', 'Black')
                color = wx.Colour(*color)
                width = obj.get('width', 1.0)
                style = obj.get('style', wx.SOLID)
                args  = obj.get('args', [0, 0, 0, 0])
                kws   = obj.get('kws', {})

                method = getattr(dc, 'Draw%s' % (shape.title()), None)
                if shape.title() == 'Line':
                    margs = [pad_w + args[0]*img_w,
                             pad_h + args[1]*img_h,
                             pad_w + args[2]*img_w,
                             pad_h + args[3]*img_h]
                elif shape.title() == 'Circle':
                    margs = [pad_w + args[0]*img_w,
                             pad_h + args[1]*img_h,  args[2]*img_w]

                if method is not None:
                    dc.SetPen(wx.Pen(color, width, style))
                    method(*margs, **kws)
