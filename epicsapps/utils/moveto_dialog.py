from collections import namedtuple

import wx
from wxutils import pack, Popup, Button, SimpleText, OkCancel

from epics import get_pv
from epics.wx import EpicsFunction

from . import GUIColors, get_pvtypes, get_pvdesc, normalize_pvname

ALL_EXP  = wx.ALL|wx.EXPAND

class MoveToDialog(wx.Dialog):
    """Full Query for Move To for a Position"""
    msg = '''Select Recent Instrument File, create a new one'''
    def __init__(self, parent, pvdata, instname, posname, mode=None):
        self.pvdata = pvdata
        title = "Move Instrument %s to Position '%s'?" % (instname, posname)
        if mode == 'show':
            title = "Instrument %s  / Position '%s'" % (instname, posname)
        wx.Dialog.__init__(self, parent, wx.ID_ANY, title=title,
                           size=(500, 325))

        colors = GUIColors()
        self.SetFont(parent.GetFont())
        titlefont  = self.GetFont()
        titlefont.PointSize += 2
        titlefont.SetWeight(wx.BOLD)

        sizer = wx.GridBagSizer(10, 4)

        labstyle  = wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL|wx.ALL
        rlabstyle = wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL|wx.ALL
        tstyle    = wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL

        # title row
        i = 0
        col_labels = ['  PV ', 'Current Value', 'Saved Value']
        if mode != 'show':
           col_labels.append('Move?')

        for titleword in col_labels:
            txt =SimpleText(self, titleword, font=titlefont, size=(125,-1),
                            colour=colors.title, style=tstyle)
            sizer.Add(txt, (0, i), (1, 1), labstyle, 1)
            i = i + 1

        sizer.Add(wx.StaticLine(self, size=(450, -1),
                                style=wx.LI_HORIZONTAL),
                  (1, 0), (1, 4), wx.ALIGN_CENTER|wx.GROW|wx.ALL, 0)

        self.checkboxes = {}
        irow = 1
        for pvname, data in pvdata.items():
            irow += 1
            desc, save_val, curr_val = data
            label = SimpleText(self, desc, style=tstyle,
                               colour=colors.pvname)
            curr  = SimpleText(self, curr_val, style=tstyle)
            saved = SimpleText(self, save_val, style=tstyle)
            if mode != 'show':
                cbox  = wx.CheckBox(self, -1, "Move")
                cbox.SetValue(True)
                self.checkboxes[pvname] = cbox
            sizer.Add(label, (irow, 0), (1, 1), labstyle,  2)
            sizer.Add(curr,  (irow, 1), (1, 1), rlabstyle, 2)
            sizer.Add(saved, (irow, 2), (1, 1), rlabstyle, 2)
            if mode != 'show':
                sizer.Add(cbox,  (irow, 3), (1, 1), rlabstyle, 2)
        irow += 1
        sizer.Add(wx.StaticLine(self, size=(450, -1),
                                style=wx.LI_HORIZONTAL),
                  (irow, 0), (1, 4), wx.ALIGN_CENTER|wx.GROW|wx.ALL, 0)

        irow += 1
        sizer.Add(OkCancel(self), (irow, 1), (1, 2),
                  wx.ALIGN_CENTER_VERTICAL|wx.ALL, 1)
        pack(self, sizer)
        w, h = self.GetBestSize()
        w = 25*int((w + 26)/25.)
        h = 25*int((h + 26)/25.)
        self.SetSize((w, h))

    def GetResponse(self, newname=None):
        self.Raise()
        response = namedtuple('MovetoResponse', ('ok', 'values'))
        ok = False
        values = {}
        if self.ShowModal() == wx.ID_OK:
            for pvname in self.pvdata:
                if pvname in self.checkboxes:
                    if self.checkboxes[pvname].IsChecked():
                        values[pvname] = self.pvdata[pvname][1]
            ok = True

        return response(ok, values)
