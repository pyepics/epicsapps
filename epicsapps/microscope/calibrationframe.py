import wx
import wx.lib.colourselect  as csel
from wxutils import Button, pack, SimpleText, FloatCtrl

CEN = wx.ALL|wx.GROW|wx.ALIGN_CENTER
LEFT = wx.ALIGN_LEFT

class CalibrationFrame(wx.Frame):
    """ calibration frame """

    def __init__(self, calibrations, current, callback=None, **kws):
        wx.Frame.__init__(self, None, -1, style=wx.DEFAULT_FRAME_STYLE, **kws)
        self.calibrations = {}
        self.calibrations.update(calibrations)
        self.current = current
        self.callback = callback
        calnames= list(calibrations.keys())
        calib = self.calibrations[current]
        panel = wx.Panel(self)
        self.SetFont(wx.Font(10, wx.SWISS, wx.NORMAL, wx.BOLD, 0, ""))

        ok_button = Button(panel, "Apply", action=self.onApply, size=(75, -1))
        done_button = Button(panel, "Done", action=self.onClose, size=(75, -1))

        self.calname = wx.ComboBox(panel, choices=calnames, value=current,
                                   size=(150, -1), style=wx.TE_PROCESS_ENTER)

        opts = dict(minval=-500.0, maxval=500.0, precision=4, size=(75, -1),
                    action=self.onCalibXY)
        self.calib_x = FloatCtrl(panel, value=calib[0], **opts)
        self.calib_y = FloatCtrl(panel, value=calib[1], **opts)

        sizer = wx.GridBagSizer(10, 3)
        sizer.SetVGap(5)
        sizer.SetHGap(5)

        def txt(label, size=-1):
            return SimpleText(panel, label, size=(size, -1))

        toplabel ="Calibration Settings: "

        sizer.Add(txt(" Calibration Settings"), (0, 0), (1, 4),  LEFT, 3)
        sizer.Add(txt(" Calibration Name  "),   (1, 0), (1, 1),  LEFT, 2)
        sizer.Add(txt(" X Size (mm):"),         (1, 1), (1, 1),  LEFT, 2)
        sizer.Add(txt(" Y Size (mm):"),         (1, 2), (1, 1),  LEFT, 2)
        sizer.Add(self.calname,                 (2, 0), (1, 1),  LEFT, 2)
        sizer.Add(self.calib_x,                 (2, 1), (1, 1),  LEFT, 2)
        sizer.Add(self.calib_y,                 (2, 2), (1, 1),  LEFT, 2)

        sizer.Add(wx.StaticLine(panel, size=(3400, 2)), (3, 0), (1, 4),
                  wx.ALL|wx.GROW|wx.ALIGN_CENTER,  1)

        sizer.Add(ok_button,    (4, 0), (1, 1),  wx.ALL|wx.GROW|wx.ALIGN_CENTER,  1)
        sizer.Add(done_button,  (4, 1), (1, 1),  wx.ALL|wx.GROW|wx.ALIGN_CENTER,  1)

        panel.SetSizer(sizer)
        sizer.Fit(panel)
        self.SetSize((400, 225))
        self.calname.Bind(wx.EVT_COMBOBOX, self.onCalibSelection)
        self.calname.Bind(wx.EVT_TEXT_ENTER, self.onCalibSelection)


        self.Bind(wx.EVT_CLOSE, self.onClose)
        self.Show()
        self.Raise()

    def onCalibSelection(self, event=None, **kws):
        name = self.calname.GetValue()
        # print(" On Calib selection ", name)
        if name not in self.calibrations:
            x, y = self.calib_x.GetValue(), self.calib_y.GetValue()
            self.calibrations[name] = [float(x), float(y)]
        else:
            calib = self.calibrations[name]
            self.calib_x.SetValue(calib[0])
            self.calib_y.SetValue(calib[1])

    def onCalibXY(self, event=None, **kws):
        try:
            name = self.calname.GetValue()
            x, y = self.calib_x.GetValue(), self.calib_y.GetValue()
            self.calibrations[name] = (x, y)
        except AttributeError:
            pass

    def onApply(self, event=None):
        if callable(self.callback):
            self.callback(self.calibrations, self.calname.GetValue())

    def onClose(self, event=None):
        self.Destroy()
