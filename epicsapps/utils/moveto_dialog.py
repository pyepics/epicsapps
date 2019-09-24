import wx
from wxutils import pack, Popup, Button, SimpleText 

from epics import get_pv
from epics.wx import EpicsFunction
                      
from . import GUIColors, get_pvtypes, get_pvdesc, normalize_pvname

ALL_EXP  = wx.ALL|wx.EXPAND

class MoveToDialog(wx.Dialog):
    """Full Query for Move To for a Position"""
    msg = '''Select Recent Instrument File, create a new one'''
    def __init__(self, parent, posname, instname, db, mode='move', **kws):
        self.posname = posname
        self.instname = instname
        self.mode = mode
        self.pvs = {}
        for pv in db.get_instrument(instname).pv:
            pvname = normalize_pvname(pv.name)
            self.pvs[pvname] = get_pv(pvname)
        # for pv in self.pvs.values():  pv.get()
                
        thispos = db.get_position(instname, posname)
        if thispos is None:
            return
        title = "Move Instrument %s to Position '%s'?" % (instname, posname)
        if mode == 'show':
            title = "Instrument %s  / Position '%s'" % (instname, posname)
        wx.Dialog.__init__(self, parent, wx.ID_ANY, title=title,
                           size=(500, 325))
        self.build_dialog(parent, thispos)

    @EpicsFunction
    def build_dialog(self, parent, thispos):
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
        if self.mode != 'show':
            col_labels.append('Move?')
        for titleword in col_labels:
            txt =SimpleText(self, titleword,
                            font=titlefont,
                            minsize=(100, -1),
                            colour=colors.title,
                            style=tstyle)

            sizer.Add(txt, (0, i), (1, 1), labstyle, 1)
            i = i + 1

        sizer.Add(wx.StaticLine(self, size=(450, -1),
                                style=wx.LI_HORIZONTAL),
                  (1, 0), (1, 4), wx.ALIGN_CENTER|wx.GROW|wx.ALL, 0)

        self.checkboxes = {}

        for irow, pvpos in enumerate(thispos.pv):
            pvname = pvpos.pv.name
            desc = get_pvdesc(pvname)
            if desc != pvname:
                desc = "%s (%s)" % (desc, pvname)
            curr_val = None

            if pvname in self.pvs:
                curr_val = self.pvs[pvname].get(as_string=True)
            elif pvname.endswith('.VAL') and pvname[:4] in self.pvs:
                curr_val = self.pvs[pvname[:-4]].get(as_string=True)
            elif pvname+'.VAL' in self.pvs:
                curr_val = self.pvs[pvname+'.VAL'].get(as_string=True)

            if curr_val is None:
                curr_val = 'Unknown'

            save_val = pvpos.value

            label = SimpleText(self, desc, style=tstyle,
                               colour=colors.pvname)
            curr  = SimpleText(self, curr_val, style=tstyle)
            saved = SimpleText(self, save_val, style=tstyle)
            if self.mode != 'show':
                cbox  = wx.CheckBox(self, -1, "Move")
                cbox.SetValue(True)
                self.checkboxes[pvname] = (cbox, save_val)

            sizer.Add(label, (irow+2, 0), (1, 1), labstyle,  2)
            sizer.Add(curr,  (irow+2, 1), (1, 1), rlabstyle, 2)
            sizer.Add(saved, (irow+2, 2), (1, 1), rlabstyle, 2)
            if self.mode != 'show':
                sizer.Add(cbox,  (irow+2, 3), (1, 1), rlabstyle, 2)

        sizer.Add(wx.StaticLine(self, size=(450, -1),
                                style=wx.LI_HORIZONTAL),
                  (irow+3, 0), (1, 4), wx.ALIGN_CENTER|wx.GROW|wx.ALL, 0)

        btnsizer = wx.StdDialogButtonSizer()
        btn = wx.Button(self, wx.ID_OK)
        btn.SetDefault()
        btnsizer.AddButton(btn)
        if self.mode != 'show':
            btnsizer.AddButton(wx.Button(self, wx.ID_CANCEL))

        btnsizer.Realize()
        sizer.Add(btnsizer, (irow+4, 2), (1, 2),
                  wx.ALIGN_CENTER_VERTICAL|wx.ALL, 1)
        pack(self, sizer)
        w, h = self.GetBestSize()
        w = 25*int((w + 26)/25.)
        h = 25*int((h + 26)/25.)
        self.SetSize((w, h))
