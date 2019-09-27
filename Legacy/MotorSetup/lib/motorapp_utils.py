import wx
from epics.wx import EpicsFunction
from epics.wx.utils import SimpleText

class MotorUpdateDialog(wx.Dialog):
    """update selected fields from motor"""

    _fields = ('dtype', 'units', 'velo', 'vbas', 'accl', 'bdst', 'bvel',
               'bacc', 'srev', 'urev', 'prec', 'dhlm', 'dllm', 'frac',
               'eres', 'rres', 'dly', 'rdbd', 'rtry', 'ueip', 'urip',
               'ntm', 'ntmf')

    _fieldmap = {'dtype': 'DTYP', 'units': 'EGU'}

    def __init__(self, parent, epics_motor, db_motor):
        self.ready = False
        self.buildDialog(parent, epics_motor, db_motor)

    #@EpicsFunction
    def buildDialog(self, parent, epics_motor, db_motor):
        self.checkboxes = {}

        pre = wx.PreDialog()
        pre.SetExtraStyle(wx.DIALOG_EX_CONTEXTHELP)
        pre.Create(parent, -1, 'Update Motor Settings?',
                   style=wx.DEFAULT_DIALOG_STYLE)
        self.PostCreate(pre)
        
        sizer = wx.GridBagSizer(10, 4)

        labstyle  = wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL|wx.ALL
        rlabstyle = wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL|wx.ALL
        tstyle    = wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL

        label = wx.StaticText(self,
                              label="Update Motor Settings to '%s'?" % db_motor.name)
        sizer.Add(label, (0, 0), (1, 4), wx.ALIGN_CENTRE|wx.ALL, 5)


        titlefont  = self.GetFont()
        titlefont.PointSize += 1
        titlefont.SetWeight(wx.BOLD)
        # title row
        irow = 1
        for i, word in enumerate((' Field', 'Current Value',
                                 'New Value', 'Change?')):
            txt = SimpleText(self, word,
                             font=titlefont,
                             size=(100, -1),
                             colour=wx.Colour(80, 10, 10),
                             style=tstyle)

            sizer.Add(txt, (irow, i), (1, 1), labstyle, 1)

        sizer.Add(wx.StaticLine(self, size=(150, -1),
                                style=wx.LI_HORIZONTAL),
                  (irow+1, 0), (1, 4), wx.ALIGN_CENTER|wx.GROW|wx.ALL, 0)

        self.checkboxes = {}

        for irow, attr in enumerate(self._fields):
            suff = attr.upper()
            if attr in self._fieldmap:
                suff = self._fieldmap[attr]
                
            curval = epics_motor.get(suff, as_string=True)
            newval = str(getattr(db_motor, attr))
            if curval is None: curval = 'unknown'
            label = SimpleText(self, suff)
            curr  = SimpleText(self, curval)
            newv  = SimpleText(self, newval)
            cbox  = wx.CheckBox(self, -1, "Update")
            cbox.SetValue(True)
            self.checkboxes[suff] = (cbox, newval)

            sizer.Add(label, (irow+3, 0), (1, 1), labstyle,  2)
            sizer.Add(curr,  (irow+3, 1), (1, 1), rlabstyle, 2)
            sizer.Add(newv,  (irow+3, 2), (1, 1), rlabstyle, 2)
            sizer.Add(cbox,  (irow+3, 3), (1, 1), rlabstyle, 2)

        sizer.Add(wx.StaticLine(self, size=(150, -1),
                                style=wx.LI_HORIZONTAL),
                  (irow+4, 0), (1, 4), wx.ALIGN_CENTER|wx.GROW|wx.ALL, 0)

        btnsizer = wx.StdDialogButtonSizer()
        btn = wx.Button(self, wx.ID_OK)
        btn.SetDefault()
        btnsizer.AddButton(btn)
        btnsizer.AddButton(wx.Button(self, wx.ID_CANCEL))

        btnsizer.Realize()
        sizer.Add(btnsizer, (irow+5, 2), (1, 2),
                  wx.ALIGN_CENTER_VERTICAL|wx.ALL, 1)

        self.SetSizer(sizer)
        sizer.Fit(self)
        self.ready = True

        
class MotorChoiceDialog(wx.Dialog):
    """ show all motor names and descriptions, allow selection of a motor"""
    def __init__(self, parent, motorlist):

        self.selected_motor= None
        self.motor_desc = {}
        motor_names = []
        for mot in motorlist:
            motor_names.append(mot.name)
            self.motor_desc[mot.name] = mot.notes


        pre = wx.PreDialog()
        pre.SetExtraStyle(wx.DIALOG_EX_CONTEXTHELP)
        pre.Create(parent, -1, 'Select Motor Settings from Known Motor Types',
                   style=wx.DEFAULT_DIALOG_STYLE)
        self.PostCreate(pre)

        sizer = wx.GridBagSizer(5, 2)

        label = wx.StaticText(self, label="Select Settings from a Known Motor")
        sizer.Add(label, (0, 0), (1, 2), wx.ALIGN_CENTRE|wx.ALL, 5)


        mlabel = wx.StaticText(self, -1, "Motor Type:")

        self.choice = wx.Choice(self, -1, (250, 250), choices=motor_names)
        self.choice.Bind(wx.EVT_CHOICE, self._onName)
        self.choice.SetSelection(0)
        
        self.desc = wx.StaticText(self, -1, ' ',  size=(220, 150))
        
        sizer.Add(mlabel,      (1, 0), (1, 1), wx.ALIGN_CENTRE|wx.ALL, 5)
        sizer.Add(self.choice, (1, 1), (1, 1), wx.ALIGN_CENTRE|wx.ALL|wx.EXPAND, 5)
        sizer.Add(self.desc,   (2, 0), (1, 2), wx.ALIGN_CENTRE|wx.ALL, 5)

        
        line = wx.StaticLine(self, -1, size=(120,-1), style=wx.LI_HORIZONTAL)
        sizer.Add(line, (3,0), (1, 2),  wx.GROW|wx.ALIGN_CENTER, 5)

        btnsizer = wx.StdDialogButtonSizer()
        
        if wx.Platform != "__WXMSW__":
            btn = wx.ContextHelpButton(self)
            btnsizer.AddButton(btn)
        
        btn = wx.Button(self, wx.ID_OK)
        btn.SetDefault()
        btnsizer.AddButton(btn)

        btn = wx.Button(self, wx.ID_CANCEL)
        btnsizer.AddButton(btn)
        btnsizer.Realize()

        sizer.Add(btnsizer, (4, 0), (1, 2), 
                  wx.ALIGN_CENTER|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)
        
        self.SetSizer(sizer)
        sizer.Fit(self)

    def _onName(self, event=None, **kws):
        self.desc.SetLabel(self.motor_desc[event.GetString()])
        self.selected_motor = event.GetString()
        
    def getMotorName(self):
        return self.selected_motor


class SaveMotorDialog(wx.Dialog):
    """dialog for entering motor name/description"""
    def __init__(self, parent, motor):
        pre = wx.PreDialog()
        pre.SetExtraStyle(wx.DIALOG_EX_CONTEXTHELP)
        pre.Create(parent, -1, 'Save Motor Settings to DB',
                   style=wx.DEFAULT_DIALOG_STYLE)
        self.PostCreate(pre)

        sizer = wx.BoxSizer(wx.VERTICAL)

        label = wx.StaticText(self, -1, "Save Motor Settings to Database")
        label.SetHelpText("Save Motor Settings as an Example in the Database")
        sizer.Add(label, 0, wx.ALIGN_CENTRE|wx.ALL, 5)
        
        box = wx.BoxSizer(wx.HORIZONTAL)

        label = wx.StaticText(self, -1, "Motor Type:")
        label.SetHelpText("Type of Motor to save in DB")
        box.Add(label, 0, wx.ALIGN_CENTRE|wx.ALL, 5)

        self.name = wx.TextCtrl(self, -1, "", size=(200,-1))
        self.name.SetHelpText("Enter name of motor type here")
        box.Add(self.name, 1, wx.ALIGN_CENTRE|wx.ALL, 5)

        sizer.Add(box, 0, wx.GROW|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)

        box = wx.BoxSizer(wx.HORIZONTAL)

        label = wx.StaticText(self, -1, "Description:")
        label.SetHelpText("Describe Motor")
        box.Add(label, 0, wx.ALIGN_CENTRE|wx.ALL, 5)

        self.desc = wx.TextCtrl(self, -1, "", style=wx.TE_MULTILINE)
        self.desc.SetMinSize((200, 75))
        self.desc.SetHelpText("Enter motor description here")
        box.Add(self.desc, 1, wx.ALIGN_CENTRE|wx.ALL, 5)

        sizer.Add(box, 0, wx.GROW|wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)

        line = wx.StaticLine(self, -1, size=(20,-1), style=wx.LI_HORIZONTAL)
        sizer.Add(line, 0, wx.GROW|wx.ALIGN_CENTER_VERTICAL|wx.RIGHT|wx.TOP, 5)

        btnsizer = wx.StdDialogButtonSizer()
        
        if wx.Platform != "__WXMSW__":
            btn = wx.ContextHelpButton(self)
            btnsizer.AddButton(btn)
        
        btn = wx.Button(self, wx.ID_OK)
        btn.SetDefault()
        btnsizer.AddButton(btn)

        btn = wx.Button(self, wx.ID_CANCEL)
        btnsizer.AddButton(btn)
        btnsizer.Realize()

        sizer.Add(btnsizer, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 5)

        self.SetSizer(sizer)
        sizer.Fit(self)

    def GetName(self):
        return self.name.GetValue()
    def GetDesc(self):
        return self.desc.GetValue()

