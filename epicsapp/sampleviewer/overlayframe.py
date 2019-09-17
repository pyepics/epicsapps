import wx
import wx.lib.colourselect  as csel
from wx.lib.agw.floatspin import FloatSpin
from epics.wx.utils import (add_button, pack, SimpleText, FloatCtrl)

CEN = wx.ALL|wx.GROW|wx.ALIGN_CENTER
LEFT = wx.ALIGN_LEFT

class OverlayFrame(wx.Frame):
    """ settings for overlays and pixel calibration"""
    shapes = ('None', 'line', 'circle')

    def __init__(self, image_panel=None, config=None, **kws):
        wx.Frame.__init__(self, None, -1,
                          style=wx.DEFAULT_FRAME_STYLE, **kws)
        self.image_panel = image_panel
        img_x, img_y = self.image_panel.full_size
        self.wids = wids = []
        self.config = config

        panel = wx.Panel(self)
        self.SetFont(wx.Font(10, wx.SWISS, wx.NORMAL, wx.BOLD, 0, ""))

        ok_button = add_button(panel, "Apply", action=self.onApply, size=(75, -1))
        done_button = add_button(panel, "Done", action=self.onClose, size=(75, -1))

        try:
            pix_x = float(config['camera']['calib_x'])
            pix_y = float(config['camera']['calib_y'])
        except:
            pix_x = 1.000
            pix_y = 1.000
            
        olays = config['overlays']
        sbar = [float(x) for x in olays['scalebar'].split()]
        circ = [float(x) for x in olays['circle'].split()]
        
        ssiz, sx, sy, swid, scolr, scolg, scolb = sbar
        csiz, cx, cy, cwid, ccolr, ccolg, ccolb = circ
        
        scol = wx.Colour(int(scolr), int(scolg), int(scolb))
        ccol = wx.Colour(int(ccolr), int(ccolg), int(ccolb))

        opts = dict(minval=0, maxval=1, precision=3, size=(60, -1))
        wopts = dict(minval=0, maxval=10, precision=1, size=(60, -1))
        sopts = dict(minval=0, maxval=1000, precision=0, size=(60, -1))
        popts = dict(minval=-1000, maxval=1000, precision=3, size=(60, -1))

        self.pix_x = FloatCtrl(panel, value=pix_x, **popts)
        self.pix_y = FloatCtrl(panel, value=pix_y, **popts)

        self.scalebar_col  = csel.ColourSelect(panel, -1, "", scol, size=(75, 25))
        self.circle_col    = csel.ColourSelect(panel, -1, "", ccol, size=(75, 25))

        self.scalebar_size = FloatCtrl(panel, value=ssiz, **sopts)
        self.scalebar_x   = FloatCtrl(panel,  value=sx, **opts)
        self.scalebar_y   = FloatCtrl(panel,  value=sy, **opts)
        self.scalebar_wid = FloatCtrl(panel,  value=swid, **wopts)


        self.circle_size = FloatCtrl(panel,  value=csiz, **sopts)
        self.circle_x    = FloatCtrl(panel, value=cx, **opts)
        self.circle_y    = FloatCtrl(panel, value=cy, **opts)
        self.circle_wid  = FloatCtrl(panel, value=cwid, **wopts)

        sizer = wx.GridBagSizer(10, 7)
        sizer.SetVGap(5)
        sizer.SetHGap(5)

        def txt(label, size=-1):
            return SimpleText(panel, label, size=(size, -1))

        sizer.Add(txt(" Configure Image Overlays: "), (0, 0), (1, 4),  CEN, 3)
        sizer.Add(txt(" Pixel Size (um)  X, Y: "),    (1, 0), (1, 2),  LEFT, 2)
        sizer.Add(self.pix_x,                        (1, 2), (1, 1),  CEN, 1)    
        sizer.Add(self.pix_y,                        (1, 3), (1, 1),  CEN, 1)    

        sizer.Add(txt(" Object "),     (2, 0), (1, 1),  LEFT, 2)
        sizer.Add(txt("Color"),        (2, 1), (1, 1),  LEFT, 2)
        sizer.Add(txt("Size (um)"),    (2, 2), (1, 1),  LEFT, 2)
        sizer.Add(txt("X (fraction)"), (2, 3), (1, 1),  LEFT, 2)
        sizer.Add(txt("Y (fraction)"), (2, 4), (1, 1),  LEFT, 2)
        sizer.Add(txt("Line width"),   (2, 5), (1, 1),  LEFT, 2)

        sizer.Add(txt(" Scalebar "),   (3, 0), (1, 1),  LEFT, 2)
        sizer.Add(self.scalebar_col,   (3, 1), (1, 1),  CEN, 1)    
        sizer.Add(self.scalebar_size,  (3, 2), (1, 1),  CEN, 1)    
        sizer.Add(self.scalebar_x,     (3, 3), (1, 1),  CEN, 1)    
        sizer.Add(self.scalebar_y,     (3, 4), (1, 1),  CEN, 1)    
        sizer.Add(self.scalebar_wid,   (3, 5), (1, 1),  CEN, 1)    

        sizer.Add(txt(" Target "),     (4, 0), (1, 1),  LEFT, 2)
        sizer.Add(self.circle_col,     (4, 1), (1, 1),  CEN, 1)    
        sizer.Add(self.circle_size,    (4, 2), (1, 1),  CEN, 1)    
        sizer.Add(self.circle_x,       (4, 3), (1, 1),  CEN, 1)    
        sizer.Add(self.circle_y,       (4, 4), (1, 1),  CEN, 1)    
        sizer.Add(self.circle_wid,     (4, 5), (1, 1),  CEN, 1)    

        sizer.Add(wx.StaticLine(panel, size=(220, 2)), (5, 0), (1, 6), 
                  wx.ALL|wx.GROW|wx.ALIGN_CENTER,  1)    

        sizer.Add(ok_button,    (6, 0), (1, 1),  wx.ALL|wx.GROW|wx.ALIGN_CENTER,  1)    
        sizer.Add(done_button,  (6, 1), (1, 1),  wx.ALL|wx.GROW|wx.ALIGN_CENTER,  1)    

        panel.SetSizer(sizer)
        sizer.Fit(panel)
        self.SetSize((500, 225))
        self.Bind(wx.EVT_CLOSE, self.onClose)
        self.Show()
        self.Raise()

    def onApply(self, event=None):
        pix_x = float(self.pix_x.GetValue())
        pix_y = float(self.pix_y.GetValue())
        self.config['camera']['calib_x'] = "%.4f" % pix_x
        self.config['camera']['calib_y'] = "%.4f" % pix_y
        
        img_x, img_y = self.image_panel.full_size

        iscale = 0.5/abs(pix_x * img_x)

        scol = self.scalebar_col.GetColour()
        swid = self.scalebar_wid.GetValue()
        sx   = self.scalebar_x.GetValue() 
        sy   = self.scalebar_y.GetValue()
        ssiz = self.scalebar_size.GetValue()

        ccol = self.circle_col.GetColour()
        cwid = self.circle_wid.GetValue()        
        csiz = self.circle_size.GetValue()
        cx   = self.circle_x.GetValue()
        cy   = self.circle_y.GetValue()

        cargs = [cx, cy, csiz*iscale]
        sargs = [sx - ssiz*iscale, sy, sx + ssiz*iscale, sy]

        dobjs = [dict(shape='Line', width=swid, 
                      style=wx.SOLID, color=scol, args=sargs),
                 dict(shape='Circle', width=cwid, 
                    style=wx.SOLID, color=ccol, args=cargs)]
        
        ofmt = "%.1f %.3f %.3f %.1f %i %i %i"
        olays = self.config['overlays']
        olays['scalebar'] = ofmt % (ssiz, sx, sy, swid, scol[0], scol[1], scol[2])
        olays['circle']   = ofmt % (csiz, cx, cy, cwid, ccol[0], ccol[1], ccol[2])
        self.image_panel.draw_objects = dobjs

    def onClose(self, event=None):
        self.Destroy()
