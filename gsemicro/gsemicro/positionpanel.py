import wx
from collections import OrderedDict
from epics.wx.utils import add_button, add_menu, popup, pack, Closure

ALL_EXP  = wx.ALL|wx.EXPAND
CEN_ALL  = wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_CENTER_VERTICAL
LEFT_CEN = wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL
LEFT_TOP = wx.ALIGN_LEFT|wx.ALIGN_TOP
LEFT_BOT = wx.ALIGN_LEFT|wx.ALIGN_BOTTOM
CEN_TOP  = wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_TOP
CEN_BOT  = wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_BOTTOM

from .imageframe import ImageDisplayFrame

INSTRUMENT_NAME = 'IDE_SampleStage'

class PositionPanel(wx.Panel):
    """panel of position lists, with buttons"""
    def __init__(self, parent):
        wx.Panel.__init__(self, parent, -1, size=(300, 500))
        self.size = (300, 500)
        self.parent = parent
        self.image_display = None
        self.pos_name =  wx.TextCtrl(self, value="", size=(285, 25),
                                     style= wx.TE_PROCESS_ENTER)
        self.pos_name.Bind(wx.EVT_TEXT_ENTER, self.onSave1)

        tlabel = wx.StaticText(self, label="Save Position: ")

        bkws = dict(size=(60, -1))
        btn_save  = add_button(self, "Save",  action=self.onSave2, **bkws)
        btn_goto  = add_button(self, "Go To", action=self.onGo,    **bkws)
        btn_erase = add_button(self, "Erase", action=self.onErase, **bkws)
        btn_show  = add_button(self, "Show",  action=self.onShow,  **bkws)

        brow = wx.BoxSizer(wx.HORIZONTAL)
        brow.Add(btn_save,  0, ALL_EXP|wx.ALIGN_LEFT, 1)
        brow.Add(btn_goto,  0, ALL_EXP|wx.ALIGN_LEFT, 1)
        brow.Add(btn_erase, 0, ALL_EXP|wx.ALIGN_LEFT, 1)
        brow.Add(btn_show,  0, ALL_EXP|wx.ALIGN_LEFT, 1)

        self.pos_list  = wx.ListBox(self)
        self.pos_list.SetBackgroundColour(wx.Colour(253, 253, 250))
        self.pos_list.Bind(wx.EVT_LISTBOX, self.onSelect)
        self.pos_list.Bind(wx.EVT_RIGHT_DOWN, self.onRightClick)

        self.SetMinSize((200, 300))

        self.SetSize(self.size)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(tlabel,         0, wx.ALIGN_LEFT|wx.ALL)
        sizer.Add(self.pos_name,  0, wx.ALIGN_LEFT|wx.ALL)
        sizer.Add(brow,           0, wx.ALIGN_LEFT|wx.ALL)
        sizer.Add(self.pos_list,  1, ALL_EXP|wx.ALIGN_CENTER, 3)
        print(" Position Panel ", self.GetSize(), self.size)

        pack(self, sizer)

    def onSave1(self, event):
        "save from text enter"
        self.onSave(event.GetString().strip())

    def onSave2(self, event):
        "save from button push"
        self.onSave(self.pos_name.GetValue().strip())

    def onSave(self, name):
        if len(name) < 1:
            return
        if name in self.positions and self.parent.v_replace:
            ret = popup(self, "Overwrite Position %s?" % name,
                        "Veriry Overwrite Position",
                        style=wx.YES_NO|wx.NO_DEFAULT|wx.ICON_QUESTION)
            if ret != wx.ID_YES:
                return
        imgfile = '%s.jpg' % time.strftime('%b%d_%H%M%S')
        imgfile = os.path.join(self.parent.imgdir, imgfile)

        imgdata = self.parent.save_image(fname=imgfile)
        tmp_pos = self.parent.ctrlpanel.read_position()

        self.positions[name] = {'image': imgfile,
                                'timestamp': time.strftime('%b %d %H:%M:%S'),
                                'position': tmp_pos}

        if name not in self.pos_list.GetItems():
            self.pos_list.Append(name)

        self.pos_name.Clear()
        self.pos_list.SetStringSelection(name)
        # auto-save file
        self.parent.config['positions'] = self.positions
        self.parent.autosave()
        self.parent.write_htmllog(name)
        self.parent.write_message("Saved Position '%s', image in %s" % (name, fname))
        wx.CallAfter(Closure(self.onSelect, event=None, name=name))

    def onShow(self, event):
        posname = self.pos_list.GetStringSelection()
        ipos  =  self.pos_list.GetSelection()
        if posname is None or len(posname) < 1:
            return
        try:
            self.image_display.Show()
            self.image_display.Raise()
        except:
            del self.image_display
            self.image_display =  None

        if self.image_display is None:
            self.image_display = ImageDisplayFrame()
            self.image_display.Raise()

        thispos = self.positions[posname]
        thisimage = thispos['image']
        if thisimage['type'] == 'filename':
            self.image_display.showfile(thisimage['data'], title=posname)
        elif thisimage['type'] == 'b46encode':
            self.image_display.showb64img(thisimage['data'], title=posname)

    def onGo(self, event):
        posname = self.pos_list.GetStringSelection()
        if posname is None or len(posname) < 1:
            return
        pos_vals = self.positions[posname]['position']
        stage_names = self.parent.config['stages'].values()
        postext = []
        for name, val in zip(stage_names, pos_vals):
            postext.append('  %s\t= %.4f' % (name['label'], val))
        postext = '\n'.join(postext)

        if self.parent.v_move:
            ret = popup(self, "Move to %s?: \n%s" % (posname, postext),
                        'Verify Move',
                        style=wx.YES_NO|wx.ICON_QUESTION)
            if ret != wx.ID_YES:
                return
        motorwids = self.parent.ctrlpanel.motor_wids
        for name, val in zip(stage_names, pos_vals):
            motorwids[name['label']].drive.SetValue("%f" % val)
        self.parent.write_message('moved to %s' % posname)

    def onErase(self, event):
        posname = self.pos_list.GetStringSelection()
        ipos  =  self.pos_list.GetSelection()
        if posname is None or len(posname) < 1:
            return
        if self.parent.v_erase:
            if wx.ID_YES != popup(self, "Erase  %s?" % (posname),
                                  'Verify Erase',
                                  style=wx.YES_NO|wx.ICON_QUESTION):
                return
        self.positions.pop(posname)
        self.pos_list.Delete(ipos)
        self.pos_name.Clear()
        self.parent.write_message('Erased Position %s' % posname)

    def onSelect(self, event=None, name=None):
        "Event handler for selecting a named position"
        if name is None:
            name = str(event.GetString().strip())
        if name is None or name not in self.positions:
            return
        self.pos_name.SetValue(name)

    def onRightClick(self, event=None):
        menu = wx.Menu()
        # make basic widgets for popup menu
        for item, name in (('popup_up1', 'Move up'),
                           ('popup_dn1', 'Move down'),
                           ('popup_upall', 'Move to top'),
                           ('popup_dnall', 'Move to bottom')):
            setattr(self, item,  wx.NewId())
            wid = getattr(self, item)
            self.Bind(wx.EVT_MENU, self.onRightEvent, wid)
            menu.Append(wid, name)
        self.PopupMenu(menu)
        menu.Destroy()

    def onRightEvent(self, event=None):
        "popup box event handler"
        idx = self.pos_list.GetSelection()
        if idx < 0: # no item selected
            return
        wid = event.GetId()
        namelist = list(self.positions.keys())[:]
        stmp = {}
        for name in namelist:
            stmp[name] = self.positions[name]

        if wid == self.popup_up1 and idx > 0:
            namelist.insert(idx-1, namelist.pop(idx))
        elif wid == self.popup_dn1 and idx < len(namelist):
            namelist.insert(idx+1, namelist.pop(idx))
        elif wid == self.popup_upall:
            namelist.insert(0, namelist.pop(idx))
        elif wid == self.popup_dnall:
            namelist.append( namelist.pop(idx))

        newpos = {}
        for name in namelist:
            newpos[name]  = stmp[name]
        self.init_positions(newpos)
        self.autosave()

    def set_positions(self, positions):
        "set the list of position on the left-side panel"

        self.pos_list.Clear()

        self.positions = positions
        for name, val in self.positions.items():
            self.pos_list.Append(name)

    def set_positions_instdb(self):
        if self.instdb is None:
            print 'No instdb?'
            return
        positions = OrderedDict()
        iname = INSTRUMENT_NAME
        posnames =  self.instdb.get_positionlist(iname)
        for pname in posnames:
            thispos = self.instdb.get_position(iname, pname)
            image = {'type': 'b64encode', 'data':''}
            if thispos.image is not None:
                image['data'] = thispos.image
            pdat = {}
            for pvpos in thispos.pvs:
                pdat[pvpos.pv.name] =  pvpos.value
            positions[pname] = dict(position=pdat, image=image)
        self.set_positions(positions)
