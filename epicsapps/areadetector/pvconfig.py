import wx

from epics import get_pv, poll
from epics.wx import (PVEnumChoice, PVEnumButtons,
                      PVFloatCtrl, PVTextCtrl, PVStaticText)

from wxutils import Font, pack
labstyle = wx.ALIGN_LEFT|wx.EXPAND|wx.ALIGN_CENTER_VERTICAL


PVcontrols = dict(pvenum=PVEnumChoice,
                  pvenumbuttons=PVEnumButtons,
                  pvfloat=PVFloatCtrl,
                  pvtctrl=PVTextCtrl,
                  pvtext=PVStaticText)


def pv_control(dtype):
    return PVcontrols.get(dtype, PVStaticText)


class PVConfigPanel(wx.Panel):
    """
    layout a set of PVs in a Vertical Column
    Label   Widget   [Readback]
    """
    def __init__(self, parent, prefix, pvdata, **kws):
        wx.Panel.__init__(self, parent, -1,  **kws)
        self.sizer = sizer = wx.GridBagSizer(3, 3)
        self.wids = {}
        self.prefix = prefix
        irow = -1
        for label, pvname, use_prefix, dtype, rsuff, wsize, fontsize in pvdata:
            if use_prefix:
                pvname = prefix + pvname
            get_pv(pvname)
        poll(0.02)

        for label, pvname, use_prefix, dtype, rsuff, wsize, fontsize in pvdata:
            label = '  %s' % label
            if use_prefix:
                pvname = prefix + pvname
            ctrl  = pv_control(dtype)
            opts = dict(pv=get_pv(pvname), size=(wsize, -1))

            self.wids[label] = ctrl(self, **opts)
            self.wids[label].SetFont(Font(fontsize))

            title = wx.StaticText(self, label=label, size=(8*len(label), -1),
                                  style=labstyle)
            title.SetFont(Font(fontsize))
            irow += 1
            sizer.Add(title, (irow, 0), (1, 1), labstyle)

            if rsuff:
                rlabel = label + rsuff
                rname = pvname + rsuff
                self.wids[rlabel] = PVStaticText(self, pv=get_pv(rname),
                                                 size=(wsize, -1))
                self.wids[rlabel].SetFont(Font(fontsize))
                sizer.Add(self.wids[label], (irow, 1), (1, 1), labstyle)
                sizer.Add(self.wids[rlabel], (irow, 2), (1, 1), labstyle)
            else:
                sizer.Add(self.wids[label], (irow, 1), (1, 2), labstyle)
        pack(self, sizer)
