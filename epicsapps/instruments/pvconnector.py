import time
import wx
import epics
from epics.wx import EpicsFunction, DelayedEpicsCallback
from epics import Motor

from .utils import MOTOR_FIELDS, normalize_pvname

class PVNameCtrl(wx.TextCtrl):
    """Text Control for an Epics PV that should try to be connected.
    this must be used with a EpicsPVList

    on <<return>> or <<lose focus>>, this tries to connect to the
    PV named in the widget.  If provided, the action provided is run.
    """
    def __init__(self, panel, value='', pvlist=None,  action=None, **kws):
        self.pvlist = pvlist
        self.action = action
        wx.TextCtrl.__init__(self, panel, wx.ID_ANY, value=value, **kws)
        self.Bind(wx.EVT_CHAR, self.onChar)
        self.Bind(wx.EVT_KILL_FOCUS, self.onFocus)

    def onFocus(self, evt=None):
        if self.pvlist is not None:
            self.pvlist.connect_pv(self.Value, action=self.action,
                                   wid=self.GetId())
        evt.Skip()

    def onChar(self, event):
        key   = event.GetKeyCode()
        value = wx.TextCtrl.GetValue(self).strip()
        pos   = wx.TextCtrl.GetSelection(self)
        if key == wx.WXK_RETURN and self.pvlist is not None:
            self.pvlist.connect_pv(value, action=self.action,
                                   wid=self.GetId())
        event.Skip()

class EpicsPVList(object):
    """a wx class to hold a list of PVs, and
    handle the connection of new PVs.

    The main attribute is '.pvs', a dictionary of PVs, with
    pvname keys.

    The main way to use this is with the PVNameCtrl above

    """
    def __init__(self, parent, timeout=10):
        self.pvs = {}
        self.in_progress = {}
        self.timeout = timeout
        self.etimer = wx.Timer(parent)
        parent.Bind(wx.EVT_TIMER, self.onTimer, self.etimer)
        self.need_connecting = []

    def onTimer(self, event=None):
        "timer event handler: looks for in_progress, may timeout"
        time.sleep(0.01)
        if len(self.in_progress) == 0:
            return
        for pvname in self.in_progress:
            wid, action, xtime = self.in_progress[pvname]
            if action is not None:
                self.__connect(pvname)
            if time.time() - xtime > self.timeout:
                self.in_progress.pop(pvname)

    def init_connect(self, pvname, is_motor=False):
        """try to connect epics PV, executing
        action(wid=wid, pvname=pvname, pv=pv)
        """
        if pvname is None or len(pvname) < 1:
            return
        pvname = normalize_pvname(pvname)

        if pvname in self.pvs:
            return
        self.pvs[pvname] = epics.get_pv(pvname, form='native')
        self.in_progress[pvname] = (None, None, time.time())
        if is_motor:
            prefix = pvname.replace('.VAL', '')
            for field in MOTOR_FIELDS:
                fname = f"{prefix}{field}"
                self.pvs[fname] = epics.get_pv(fname, form='native')
                self.in_progress[fname] = (None, None, time.time())

    def show_unconnected(self):
        all = 0
        unconn =  []
        for name, pv in self.pvs.items():
            all += 1
            if not pv.connected:
                unconn.append(name)
            time.sleep(0.002)
        print("%d unconnected PVs of %d total" % (len(unconn), all))
        s = ''
        for n in unconn:
            if len(s) > 1:
                s = "%s, %s" % (s, n)
            else:
                s = n
            if len(s)  > 60:
                print("  %s" % s)
                s = ''
        if len(s) > 0:
            print("  %s" % s)


    # @EpicsFunction
    def connect_pv(self, pvname, is_motor=False, wid=None, action=None):
        """try to connect epics PV, executing
        action(wid=wid, pvname=pvname, pv=pv)
        """
        # print(" connect_pv " ,  pvname)
        if pvname is None or len(pvname) < 1:
            return
        if '.' not in pvname:
            pvname = '%s.VAL' % pvname
        pvname = str(pvname)
        if pvname in self.pvs:
            return
        if pvname not in self.pvs:
            self.pvs[pvname] = epics.get_pv(pvname, form='native', timeout=1.0)
            self.in_progress[pvname] = (wid, action, time.time())
#         if is_motor:
#             idot = pvname.find('.')
#             basname = pvname[:idot]
#             for ext in MOTOR_FIELDS:
#                 pvname = "%s%s" % (basname, ext)
#                 self.pvs[pvname] = epics.get_pv(pvname)
#                 self.in_progress[pvname] = (wid, action, time.time())

    @EpicsFunction
    def add_pv(self, pv, wid=None, action=None):
        """add an already connected PV to the pvlist"""
        if isinstance(pv, epics.PV) and pv not in self.pvs:
            self.pvs[pv.pvname] = pv

    @EpicsFunction
    def __connect(self, pvname):
        """if a new epics PV has connected, run the requested action"""

        if pvname not in self.pvs:
            self.pvs[pvname] = epics.get_pv(pvname, form='native', timeout=2.0)
        pv = self.pvs[pvname]
        if not self.pvs[pvname].connected:
            return

        try:
            wid, action, itime = self.in_progress.pop(pvname)
        except KeyError:
            wid, action, itime = None, None, 0
        pv.get_ctrlvars()

        if hasattr(action, '__call__'):
            action(wid=wid, pvname=pvname, pv=self.pvs[pvname])
