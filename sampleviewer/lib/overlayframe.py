import wx
import wx.lib.colourselect  as csel
from wx.lib.agw.floatspin import FloatSpin
from epics.wx.utils import (add_button, pack, SimpleText, FloatCtrl)

CEN = wx.ALL|wx.GROW|wx.ALIGN_CENTER

class OverlayFrame(wx.Frame):
    """ settings for overlays and pixel calibration"""
    shapes = ('None', 'line', 'circle')

    def __init__(self, image_panel=None, **kws):
        wx.Frame.__init__(self, None, -1,
                          style=wx.DEFAULT_FRAME_STYLE, **kws)
        self.image_panel = image_panel
        self.wids = wids = []
        panel = wx.Panel(self)
        self.SetFont(wx.Font(10, wx.SWISS, wx.NORMAL, wx.BOLD, 0, ""))

        ok_button = add_button(panel, "Apply", action=self.onApply, size=(75, -1))

        self.pix_size = FloatCtrl(panel, value=self.image_panel.pixel_size, 
                                  maxval=3000, precision=2, size=(75, -1))


        sizer = wx.GridBagSizer(10, 5)
        sizer.SetVGap(5)
        sizer.SetHGap(5)

        def txt(label, size=-1):
            return SimpleText(panel, label, size=(size, -1))

        sizer.Add(txt("Configure Image Overlays: "), (0, 0), (1, 5),  CEN, 3)
        sizer.Add(txt("Pixel Size (um): "),          (1, 1), (1, 1),  CEN, 2)
        sizer.Add(self.pix_size,                (1, 2), (1, 1),  CEN,  1)    

        for i, label in enumerate(('Shape', 'Color', 'Linewidth', 'Position', '')):
            sizer.Add(txt(label), (2, i), (1, 1),  CEN, 1)

        i = 2
        for tmp in range(4):
            i = i+1
            choice = wx.Choice(panel, -1, choices=self.shapes,  size=(80, -1))
            choice.SetSelection(0)
            color = csel.ColourSelect(panel,  -1, "", (0, 0, 0), size=(30, 30))
            width = FloatSpin(panel, -1,  pos=(-1,-1), size=(45,30), value=1.5,
                              min_val=0, max_val=10, increment=0.5, digits=1)

            sizer.Add(choice, (i, 0), (1, 1), CEN, 1)
            sizer.Add(color,  (i, 1), (1, 1), CEN, 1)
            sizer.Add(width,  (i, 2), (1, 1), CEN, 1)

            self.wids.append((choice, color, width))
        i = i+1
        sizer.Add(ok_button,  (i, 1), (1, 1),  wx.ALL|wx.GROW|wx.ALIGN_CENTER,  1)    


        panel.SetSizer(sizer)
        sizer.Fit(panel)

        self.Bind(wx.EVT_CLOSE, self.onClose)
        self.Show()
        self.Raise()

    def onApply(self, event=None):
        print 'Apply Changes '
        pix = float(self.pix_size.GetValue())
        self.image_panel.pixel_size = pix



    def onClose(self, event=None):
        print 'Done '
        self.Destroy()
