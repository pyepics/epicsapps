import wx
import wx.lib.colourselect  as csel
from wxutils import Button, pack, SimpleText, FloatCtrl

CEN = wx.ALL|wx.GROW|wx.ALIGN_CENTER
LEFT = wx.ALIGN_LEFT

class OverlayFrame(wx.Frame):
    """ settings for overlays"""
    shapes = ('None', 'line', 'circle')

    def __init__(self, config=None, calib=(0.01, 0.01),
                 callback=None, **kws):
        wx.Frame.__init__(self, None, -1,
                          style=wx.DEFAULT_FRAME_STYLE, **kws)
        self.callback = callback
        self.config = config
        self.calib = calib
        self.wids = wids = []

        panel = wx.Panel(self)
        self.SetFont(wx.Font(10, wx.SWISS, wx.NORMAL, wx.BOLD, 0, ""))

        ok_button = Button(panel, "Apply", action=self.onApply, size=(75, -1))
        done_button = Button(panel, "Done", action=self.onClose, size=(75, -1))

        sbar = circ = None
        for overlay in self.config.get('overlays', []):
            name  = overlay[0].lower()
            if name == 'scalebar':
                sbar = [float(x) for x in overlay[1:]]
            elif name == 'circle':
                circ = [float(x) for x in overlay[1:]]

        ssiz, sx, sy, swid, scolr, scolg, scolb = sbar
        csiz, cx, cy, cwid, ccolr, ccolg, ccolb = circ

        scol = wx.Colour(int(scolr), int(scolg), int(scolb))
        ccol = wx.Colour(int(ccolr), int(ccolg), int(ccolb))

        opts = dict(minval=0, maxval=1, precision=3, size=(60, -1))
        wopts = dict(minval=0, maxval=10, precision=1, size=(60, -1))
        sopts = dict(minval=0, maxval=1000, precision=0, size=(60, -1))
        popts = dict(minval=-1000, maxval=1000, precision=3, size=(60, -1))

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

        toplabel ="Configure Image Overlays: pixel size=%.2f \u03bCm"

        sizer.Add(txt(toplabel % (abs(calib[0]))), (0, 0), (1, 4),  CEN, 3)
        sizer.Add(txt(" Object "),            (1, 0), (1, 1),  LEFT, 2)
        sizer.Add(txt("Color"),               (1, 1), (1, 1),  LEFT, 2)
        sizer.Add(txt("Size (\u03bCm)"),      (1, 2), (1, 1),  LEFT, 2)
        sizer.Add(txt("X (fraction)"),        (1, 3), (1, 1),  LEFT, 2)
        sizer.Add(txt("Y (fraction)"),        (1, 4), (1, 1),  LEFT, 2)
        sizer.Add(txt("Line width (pixels)"), (1, 5), (1, 1),  LEFT, 2)

        sizer.Add(txt(" Scalebar "),   (2, 0), (1, 1),  LEFT, 2)
        sizer.Add(self.scalebar_col,   (2, 1), (1, 1),  CEN, 1)
        sizer.Add(self.scalebar_size,  (2, 2), (1, 1),  CEN, 1)
        sizer.Add(self.scalebar_x,     (2, 3), (1, 1),  CEN, 1)
        sizer.Add(self.scalebar_y,     (2, 4), (1, 1),  CEN, 1)
        sizer.Add(self.scalebar_wid,   (2, 5), (1, 1),  CEN, 1)

        sizer.Add(txt(" Target "),     (3, 0), (1, 1),  LEFT, 2)
        sizer.Add(self.circle_col,     (3, 1), (1, 1),  CEN, 1)
        sizer.Add(self.circle_size,    (3, 2), (1, 1),  CEN, 1)
        sizer.Add(self.circle_x,       (3, 3), (1, 1),  CEN, 1)
        sizer.Add(self.circle_y,       (3, 4), (1, 1),  CEN, 1)
        sizer.Add(self.circle_wid,     (3, 5), (1, 1),  CEN, 1)

        sizer.Add(wx.StaticLine(panel, size=(220, 2)), (4, 0), (1, 6),
                  wx.ALL|wx.GROW|wx.ALIGN_CENTER,  1)

        sizer.Add(ok_button,    (5, 0), (1, 1),  wx.ALL|wx.GROW|wx.ALIGN_CENTER,  1)
        sizer.Add(done_button,  (5, 1), (1, 1),  wx.ALL|wx.GROW|wx.ALIGN_CENTER,  1)

        panel.SetSizer(sizer)
        sizer.Fit(panel)
        self.SetSize((500, 225))
        self.Bind(wx.EVT_CLOSE, self.onClose)
        self.Show()
        self.Raise()

    def onApply(self, event=None):
        if not callable(self.callback):
            return
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
        overlays = [['scalebar', ssiz, sx, sy, swid, scol[0], scol[1], scol[2]],
                    ['circle', csiz, cx, cy, cwid, ccol[0], ccol[1], ccol[2]]]
        self.callback(overlays)

    def onClose(self, event=None):
        self.Destroy()
