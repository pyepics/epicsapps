import wx
import time
from epics import Motor
from epics.wx import MotorPanel, EpicsFunction

from epics.wx.utils import (add_button, add_menu, popup, pack, Closure ,
                            NumericCombo, SimpleText, FileSave, FileOpen,
                            SelectWorkdir, LTEXT, CEN, LCEN, RCEN, RIGHT)

from .icons import bitmaps

ALL_EXP  = wx.ALL|wx.EXPAND|wx.ALIGN_LEFT|wx.ALIGN_TOP
LEFT_BOT = wx.ALIGN_LEFT|wx.ALIGN_BOTTOM
CEN_TOP  = wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_TOP
CEN_BOT  = wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_BOTTOM

def make_steps(prec=3, tmin=0, tmax=10, decades=7, steps=(1,2,5)):
    """automatically create list of step sizes, generally going as
        1, 2, 5, 10, 20, 50, 100, 200, 500
    using precision,
    """
    steps = []
    for i in range(decades):
        for step in (j* 10**(i-prec) for j in steps):
            if (step <= tmax and step > 0.98*tmin):
                steps.append(step)
    return steps

class ControlPanel(wx.Panel):
    motorgroups = {'fine':   ('fineX', 'fineY'),
                   'coarse': ('X', 'Y'),
                   'focus':  ('Z',),
                   'theta':  ('theta',)}

    def __init__(self, parent):
        wx.Panel.__init__(self, parent, -1, config)
        self.config = config
        self.tweaks = {}
        self.tweaklist = {}
        self.motor_wids = {}
        self.SetMinSize((280, 500))
        self.connect_motors()
        self.get_tweakvalues()

        fine_p = self.group_panel(label='Fine Stages', group='fine',
                                      precision=4,
                                      buttons=[('Zero Fine Motors',
                                                self.onZeroFineMotors)])

        coarse_p = self.group_panel(label='Coarse Stages', group='coarse')
        focus_p = self.group_panel(label='Focus', group='focus')
        theta_p = self.group_panel(label='Theta', group='theta')

        sizer = wx.BoxSizer(wx.VERTICAL)
        for panel in (fine_p, coarse_p, focus_p, theta_p):
            sizer.Add((3, 3))
            sizer.Add(panel,   0, ALL_EXP)
            sizer.Add((3, 3))
            sizer.Add(wx.StaticLine(self, size=(290, 3)), 0, CEN_TOP)
        pack(self, sizer)

    @EpicsFunction
    def connect_motors(self):
        "connect to epics motors"
        self.motors = {}
        self.sign = {None: 1}
        for pvname, val in self.config.items():
            pvname = pvname.strip()
            label = val['label']
            self.motors[label] = Motor(name=pvname)
            self.sign[label] = val['sign']

        for mname in self.motor_wids:
            self.motor_wids[mname].SelectMotor(self.motors[mname])

    def group_panel(self, label='Fine Stages', group='fine',
                    precision=3, buttons=None):
        """make motor group panel """
        motors = self.motorgroups[group]
        panel  = wx.Panel(self)

        init_tweaks = dict(fine=6, coarse=6, focus=5, theta=8)

        self.tweaks[group] = NumericCombo(panel, self.tweaklist[group],
                                          precision=precision, init=init_tweaks[group])

        slabel = wx.BoxSizer(wx.HORIZONTAL)
        slabel.Add(wx.StaticText(panel, label=" %s: " % label, size=(120,-1)),
                   1,  wx.EXPAND|LEFT_BOT)
        slabel.Add(self.tweaks[group], 0,  ALL_EXP)

        smotor = wx.BoxSizer(wx.VERTICAL)
        smotor.Add(slabel, 0, ALL_EXP)

        for mnam in motors:
            self.motor_wids[mnam] = MotorPanel(panel, label=mnam, psize='small')
            self.motor_wids[mnam].desc.SetLabel(mnam)
            smotor.Add(self.motor_wids[mnam], 0, ALL_EXP)

        if buttons is not None:
            for label, action in buttons:
                smotor.Add(add_button(panel, label, action=action))

        btnbox = self.make_button_panel(panel, group=group, dim=len(motors))
        btnbox_style = CEN_BOT
        if dim==2:
            btnbox_style = CEN_TOP

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(smotor, 0, ALL_EXP)
        sizer.Add(btnbox, 0, btnbox_style, 1)

        pack(panel, sizer)
        return panel

    def arrow(self, panel, group, name):
        "bitmap button"
        b = wx.BitmapButton(panel, -1, bitmaps[name], style=wx.NO_BORDER)
        b.Bind(wx.EVT_BUTTON, Closure(self.onMove, group=group, name=name))
        return b

    def make_button_panel(self, parent, group='', dim=2):
        panel = wx.Panel(parent)
        if dim=2:
            sizer = wx.GridSizer(3, 3, 1, 1)
            sizer.Add(self.arrow(panel, group, 'nw'), 0, ALL_EXP)
            sizer.Add(self.arrow(panel, group, 'nn'), 0, ALL_EXP)
            sizer.Add(self.arrow(panel, group, 'ne'), 0, ALL_EXP)
            sizer.Add(self.arrow(panel, group, 'ww'), 0, ALL_EXP)
            sizer.Add((2, 2))
            sizer.Add(self.arrow(panel, group, 'ee'), 0, ALL_EXP)
            sizer.Add(self.arrow(panel, group, 'sw'), 0, ALL_EXP)
            sizer.Add(self.arrow(panel, group, 'ss'), 0, ALL_EXP)
            sizer.Add(self.arrow(panel, group, 'se'), 0, ALL_EXP)
        else:
            sizer = wx.GridSizer(1, 3)
            sizer.Add(self.arrow(panel, group, 'ww'), 0, ALL_EXP)
            sizer.Add((2, 2))
            sizer.Add(self.arrow(panel, group, 'ee'), 0, ALL_EXP)

        pack(panel, sizer)
        return panel

    def onZeroFineMotors(self, event=None):
        "event handler for Zero Fine Motors"
        mot = self.motors
        mot['X'].VAL +=  self.sign['fineX'] * mot['fineX'].VAL
        mot['Y'].VAL +=  self.sign['fineY'] * mot['fineY'].VAL
        time.sleep(0.05)
        mot['fineX'].VAL = 0
        mot['fineY'].VAL = 0

    def get_tweakvalues(self):
        "get settings for tweak values for combo boxes"

        self.tweaklist['fine']   = make_steps(prec=4, tmax=2.2)
        self.tweaklist['coarse'] = make_steps(tmax=70.0)
        self.tweaklist['focus']  = make_steps(tmax=70.0)
        self.tweaklist['theta']  = make_steps(tmax= 9.0)
        self.tweaklist['theta'].extend([10, 20, 30, 45, 90, 180])


    def onMove(self, event, name=None, group=None):
        twkval = float(self.tweaks[group].GetStringSelection())
        ysign = {'n':1, 's':-1}.get(name[0], 0)
        xsign = {'e':1, 'w':-1}.get(name[1], 0)

        y = None
        mots = self.motorgroups[group]
        x = mots[0]
        if len(mots) == 2:
            y = mots[1]


        xsign = xsign * self.sign[x]
        val = float(self.motor_wids[x].drive.GetValue())
        self.motor_wids[x].drive.SetValue("%f" % (val + xsign*twkval))
        if y is not None:
            val = float(self.motor_wids[y].drive.GetValue())
            ysign = ysign * self.sign[y]
            self.motor_wids[y].drive.SetValue("%f" % (val + ysign*twkval))
        try:
            self.motors[x].TWV = twkval
            if y is not None:
                self.motors[y].TWV = twkval
        except:
            pass

    def read_position(self):
        pos = []
        for v in self.config.values():
            pos.append(float(self.motors[v['label']].VAL))
        return pos
