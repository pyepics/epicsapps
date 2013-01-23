#!/usr/bin/python

import wx
from wx._core import PyDeadObjectError

import time
import epics
from epics.wx import (EpicsFunction, PVText, PVFloatCtrl, PVTextCtrl,
                      PVEnumChoice, MotorPanel)
from epics.wx.utils import  pack, popup, add_button, SimpleText
from epics.wx.ordereddict import OrderedDict

from utils import ALL_EXP , GUIColors, get_pvtypes, get_pvdesc

MOTOR_FIELDS = ('SET', 'disabled', 'LLM', 'HLM',  'LVIO', 'TWV',
                'HLS', 'LLS', 'SPMG', 'DESC')

def normalize_pvname(pvname):
    pvname = str(pvname)
    if '.' not in pvname:
        pvname = '%s.VAL' % pvname
    return pvname

class RenameDialog(wx.Dialog):
    """Rename a Position"""
    msg = '''Select Recent Instrument File, create a new one'''
    def __init__(self, parent, posname, inst, **kws):
        self.posname = posname
        self.inst = inst
        title = "Rename Position '%s' for '%s' ?" % (posname, inst.name)
        wx.Dialog.__init__(self, parent, wx.ID_ANY, title=title)
        panel = wx.Panel(self)
        colors = GUIColors()

        self.SetFont(parent.GetFont())
        titlefont  = self.GetFont()
        titlefont.PointSize += 2
        titlefont.SetWeight(wx.BOLD)

        panel.SetBackgroundColour(colors.bg)
        sizer = wx.GridBagSizer(10, 3)

        labstyle  = wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL|wx.ALL
        rlabstyle = wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL|wx.ALL
        tstyle    = wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL

        label1  = SimpleText(panel, 'Old name = %s' % posname, style=tstyle)
        label2  = SimpleText(panel, 'New name = ' , style=tstyle)
        self.newname =  wx.TextCtrl(panel, value=posname, size=(225, 25))

        sizer.Add(label1, (0, 0), (1, 2), labstyle, 1)
        sizer.Add(label2, (1, 0), (1, 1), labstyle, 1)
        sizer.Add(self.newname, (1, 1), (1, 1), labstyle, 1)

        sizer.Add(wx.StaticLine(panel, size=(250, -1),
                                style=wx.LI_HORIZONTAL),
                  (2, 0), (1, 2), wx.ALIGN_CENTER|wx.GROW|wx.ALL, 0)

        btnsizer = wx.StdDialogButtonSizer()
        btn = wx.Button(panel, wx.ID_OK)
        btn.SetDefault()
        btnsizer.AddButton(btn)
        btnsizer.AddButton(wx.Button(panel, wx.ID_CANCEL))

        btnsizer.Realize()
        sizer.Add(btnsizer, (3, 0), (1, 2),
                  wx.ALIGN_CENTER_VERTICAL|wx.ALL, 1)
        pack(panel, sizer)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(panel, 0, 0, 0)
        pack(self, sizer)

class MoveToDialog(wx.Dialog):
    """Full Query for Move To for a Position"""
    msg = '''Select Recent Instrument File, create a new one'''
    def __init__(self, parent, posname, inst, db, pvs, pvdesc=None, **kws):
        self.posname = posname
        self.inst = inst
        self.pvs  = pvs
        if pvdesc is None:
            pvdesc = {}
            
        thispos = db.get_position(posname, inst)
        if thispos is None:
            return

        title = "Move Instrument %s to Position '%s'?" % (inst.name, posname)
        wx.Dialog.__init__(self, parent, wx.ID_ANY, title=title)
        self.build_dialog(parent, thispos)

    @EpicsFunction
    def build_dialog(self, parent, thispos):
        panel = wx.Panel(self)
        colors = GUIColors()

        self.SetFont(parent.GetFont())
        titlefont  = self.GetFont()
        titlefont.PointSize += 2
        titlefont.SetWeight(wx.BOLD)

        panel.SetBackgroundColour(colors.bg)
        sizer = wx.GridBagSizer(10, 4)

        labstyle  = wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL|wx.ALL
        rlabstyle = wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL|wx.ALL
        tstyle    = wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL
        # title row
        i = 0
        for titleword in ('  PV ', 'Current Value',
                          'Saved Value', 'Move?'):
            txt =SimpleText(panel, titleword,
                            font=titlefont,
                            minsize=(100, -1),
                            colour=colors.title,
                            style=tstyle)

            sizer.Add(txt, (0, i), (1, 1), labstyle, 1)
            i = i + 1

        sizer.Add(wx.StaticLine(panel, size=(150, -1),
                                style=wx.LI_HORIZONTAL),
                  (1, 0), (1, 4), wx.ALIGN_CENTER|wx.GROW|wx.ALL, 0)

        self.checkboxes = {}
        for irow, pvpos in enumerate(thispos.pvs):
            pvname = pvpos.pv.name
            desc = get_pvdesc(pvname)
            if desc != pvname:
                desc = "%s (%s)" % (desc, pvname)
                
            curr_val = self.pvs[pvname].get(as_string=True)
            if curr_val is None:
                curr_val = 'Unknown'
            save_val = pvpos.value

            label = SimpleText(panel, desc, style=tstyle,
                               colour=colors.pvname)
            curr  = SimpleText(panel, curr_val, style=tstyle)
            saved = SimpleText(panel, save_val, style=tstyle)
            cbox  = wx.CheckBox(panel, -1, "Move")
            cbox.SetValue(True)
            self.checkboxes[pvname] = (cbox, save_val)

            sizer.Add(label, (irow+2, 0), (1, 1), labstyle,  2)
            sizer.Add(curr,  (irow+2, 1), (1, 1), rlabstyle, 2)
            sizer.Add(saved, (irow+2, 2), (1, 1), rlabstyle, 2)
            sizer.Add(cbox,  (irow+2, 3), (1, 1), rlabstyle, 2)

        sizer.Add(wx.StaticLine(panel, size=(150, -1),
                                style=wx.LI_HORIZONTAL),
                  (irow+3, 0), (1, 4), wx.ALIGN_CENTER|wx.GROW|wx.ALL, 0)

        btnsizer = wx.StdDialogButtonSizer()
        btn = wx.Button(panel, wx.ID_OK)
        btn.SetDefault()
        btnsizer.AddButton(btn)
        btnsizer.AddButton(wx.Button(panel, wx.ID_CANCEL))

        btnsizer.Realize()
        sizer.Add(btnsizer, (irow+4, 2), (1, 2),
                  wx.ALIGN_CENTER_VERTICAL|wx.ALL, 1)
        pack(panel, sizer)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(panel, 0, 0, 0)
        pack(self, sizer)

class InstrumentPanel(wx.Panel):
    """ create Panel for an instrument"""
    def __init__(self, parent, inst, db=None, writer=None,
                 pvlist = None, size=(-1, -1)):
        self.last_draw = 0
        self.inst = inst
        self.pvlist = pvlist
        self.db   = db
        self.write_message = writer
        self.pvs  = {}
        self.pvdesc = {}
        self.pv_components  = OrderedDict()

        wx.Panel.__init__(self, parent, size=size)

        #for p in self.db.get_ordered_instpvs(inst):
        #    self.add_pv(p.pv.name)


        self.colors = colors = GUIColors()
        self.parent = parent
        self.SetFont(parent.GetFont())
        titlefont  = self.GetFont()
        titlefont.PointSize += 2
        titlefont.SetWeight(wx.BOLD)

        splitter = wx.SplitterWindow(self, -1,
                                     style=wx.SP_3D|wx.SP_BORDER|wx.SP_LIVE_UPDATE)

        rpanel = wx.Panel(splitter, style=wx.BORDER_SUNKEN, size=(-1, 225))
        self.leftpanel = wx.Panel(splitter, style=wx.BORDER_SUNKEN, size=(-1,325))

        # self.leftsizer = wx.GridBagSizer(12, 4)
        self.leftsizer = wx.BoxSizer(wx.VERTICAL)

        splitter.SetMinimumPaneSize(225)

        toprow = wx.Panel(self.leftpanel)

        self.inst_title = SimpleText(toprow,  ' %s ' % inst.name,
                                     font=titlefont,
                                     colour=colors.title,
                                     minsize=(150, -1),
                                     style=wx.ALIGN_LEFT|wx.ALIGN_BOTTOM)


        self.pos_name =  wx.TextCtrl(toprow, value="", size=(250, 25),
                                     style= wx.TE_PROCESS_ENTER)
        self.pos_name.Bind(wx.EVT_TEXT_ENTER, self.onSavePosition)

        topsizer = wx.BoxSizer(wx.HORIZONTAL)
        topsizer.Add(self.inst_title, 0, wx.ALIGN_CENTER|wx.ALIGN_CENTER_VERTICAL, 1)
        topsizer.Add(SimpleText(toprow, 'Save Current Position:',
                                minsize=(180, -1),
                                style=wx.ALIGN_CENTER), 1,
                     wx.ALIGN_CENTER_VERTICAL|wx.ALL, 1)

        topsizer.Add(self.pos_name, 0,
                     wx.GROW|wx.ALIGN_RIGHT|wx.ALIGN_CENTER_VERTICAL, 1)

        pack(toprow, topsizer)
        self.toprow = toprow

        # start a timer to check for when to fill in PV panels
        timer_id = wx.NewId()
        # self.etimer = wx.Timer(self)
        self.etimer2 = wx.Timer(self)
        self.puttimer = wx.Timer(self)
        self.etimer_count = 0
        self.etimer_poll = 25

        # self.Bind(wx.EVT_TIMER, self.OnConnectTimer, self.etimer)
        self.Bind(wx.EVT_TIMER, self.OnEtimer2, self.etimer2)
        
        self.Bind(wx.EVT_TIMER, self.OnPutTimer, self.puttimer)

        rsizer = wx.BoxSizer(wx.VERTICAL)
        btn_goto = add_button(rpanel, "Go To", size=(70, -1),
                              action=self.OnMove)
        btn_erase = add_button(rpanel, "Erase",  size=(70, -1),
                               action=self.onErase)

        brow = wx.BoxSizer(wx.HORIZONTAL)
        brow.Add(btn_goto,   0, ALL_EXP|wx.ALIGN_LEFT, 1)
        brow.Add(btn_erase,  0, ALL_EXP|wx.ALIGN_LEFT, 1)

        self.pos_list  = wx.ListBox(rpanel, size=(225, -1))
        self.pos_list.SetBackgroundColour(wx.WHITE)
        self.pos_list.Bind(wx.EVT_RIGHT_DOWN, self.onRightClick)
        self.pos_list.Bind(wx.EVT_LISTBOX, self.onPosSelect)
        self.pos_list.Bind(wx.EVT_LEFT_DCLICK, self.OnMove)

        self.pos_list.Clear()
        for pos in inst.positions:
            self.pos_list.Append(pos.name)

        rsizer.Add(brow,          0, wx.ALIGN_LEFT|wx.ALL)
        rsizer.Add(self.pos_list, 1, wx.EXPAND|wx.ALIGN_CENTER, 1)
        pack(rpanel, rsizer)


        splitter.SplitVertically(self.leftpanel, rpanel, -150)

        self.leftpanel.SetMinSize((750, 150))
        rpanel.SetMinSize((150, -1))

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(splitter, 1, wx.GROW|wx.ALL, 0)
        pack(self, sizer)
        print ' start etimer2 for ' , self.inst.name, time.ctime()
        self.etimer2.Start(1)

    def undisplay_pv(self, pvname):
        "remove pv from display"
        if pvname in self.pv_components:
            self.pv_components.pop(pvname)
            self.redraw_leftpanel()

        # @EpicsFunction
    def redraw_leftpanel(self, force=False):
        """ redraws the left panel """
        if (time.time() - self.last_draw) < 0.5:
            return

        print 'redraw left! ', time.ctime()

        self.Freeze()
        self.Hide()
        self.leftsizer.Clear()

        # print 'redraw left 1 ', time.ctime()
        self.leftsizer.Add(self.toprow, 0, wx.ALIGN_LEFT|wx.TOP, 2)

        current_comps = [self.toprow]
        pvcomps = list(self.pv_components.items())

        skip = []
        for icomp, val in enumerate(pvcomps):
            pvname, comp = val
            connected, pvtype, pv = comp
            grow = 0
            panel = None
            if pvtype == 'motor':
                try:
                    #print 'MotorPanel create ', self.inst.name, pvname
                    t0 = time.time()
                    panel = MotorPanel(self.leftpanel, pvname)
                    #print 'MotorPanel done ', time.time()-t0
                except PyDeadObjectError:
                    #print 'Error making motorpanel'
                    pass
            elif pv is not None and hasattr(pv, 'pvname') and pv.pvname not in skip:
                panel = wx.Panel(self.leftpanel)
                sizer = wx.BoxSizer(wx.HORIZONTAL)

                label = SimpleText(panel, '  %s' % pvname,
                                   colour=self.colors.pvname,
                                   minsize=(180,-1), style=wx.ALIGN_LEFT)

                if pvtype == 'enum':
                    ctrl = PVEnumChoice(panel, pv=pv, size=(120, -1))
                elif pvtype in ('string', 'unicode'):
                    ctrl = PVTextCtrl(panel, pv=pv, size=(120, -1))
                else:
                    ctrl = PVFloatCtrl(panel, pv=pv, size=(120, -1))

                current_comps.append(ctrl)
                current_comps.append(label)

                sizer.Add(label, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 2)
                sizer.Add(ctrl,  0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 2)

                if (pvtype != 'motor' and icomp < len(pvcomps)-1 and
                    pvcomps[icomp+1][1][1] != 'motor'): #  and False):
                    conn, pvtype2, pv2 = pvcomps[icomp+1][1]
                    skip.append(pv2.pvname)

                    l2 = SimpleText(panel, '  %s' % pv2.pvname,
                                    colour=self.colors.pvname,
                                    minsize=(180,-1), style=wx.ALIGN_LEFT)
                    if pvtype2 == 'enum':
                        c2 = PVEnumChoice(panel, pv=pv2, size=(120, -1))
                    elif pvtype2 in ('string', 'unicode'):
                        c2 = PVTextCtrl(panel, pv=pv2, size=(120, -1))
                    else:
                        c2 = PVFloatCtrl(panel, pv=pv2, size=(120, -1))

                    sizer.Add(l2, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 2)
                    sizer.Add(c2, 0, wx.ALIGN_CENTER_VERTICAL|wx.ALL, 2)
                    current_comps.append(c2)
                    current_comps.append(l2)
                pack(panel, sizer)

            if panel is not None:
                current_comps.append(panel)
                self.leftsizer.Add(panel, 0,  wx.ALIGN_LEFT|wx.TOP|wx.ALL|wx.GROW, 1)


        pack(self.leftpanel, self.leftsizer)

        for wid in self.leftpanel.Children:
            if wid not in current_comps and wid != self.toprow:
                try:
                    time.sleep(0.010)
                    wid.Destroy()
                except PyDeadObjectError:
                    pass

        self.Refresh()
        self.Layout()
        self.Thaw()
        self.Show()
        print 'redraw left End ', time.ctime()
        self.last_draw = time.time()


    def add_pv(self, pvname):
        """add a PV to the left panel"""
        pvname = normalize_pvname(pvname)
        # print 'add pv ', pvname, self.inst.name
        self.pv_components[pvname] = (False, None, None)
        db_pv = self.db.get_pv(pvname)
        if db_pv.pvtype.name == 'motor':
            idot = pvname.find('.')
            for ext in MOTOR_FIELDS:
                self.pvlist.connect_pv('%s.%s' % (pvname[:idot], ext))
        # self.PV_Panel(pvname)                


    def write(self, msg, status='normal'):
        if self.write_message is None:
            return
        self.write_message(msg, status=status)

    def OnPutTimer(self, evt=None):
        """Timer Event for GoTo to look if move is complete."""
        if self.db.restore_complete():
            self.puttimer.Stop()

    def OnConnectTimer(self, evt=None):
        """Timer Event: look for uncompleted PV panels
        and try to create them ...
        """
        if all([comp[0] for comp in self.pv_components.values()]): # "all connected"
            # self.etimer.Stop()
            self.etimer2.Stop()
            self.redraw_leftpanel()
            # return
        # if we've done 20 rounds, there are probably
        # really unconnected PVs -- let's slow down.

    def OnEtimer2(self, evt=None):
        print 'etimer2 event ', self.inst.name, time.ctime()
        for pvname in self.pv_components:
            self.PV_Panel(pvname)        

        if all([comp[0] for comp in self.pv_components.values()]): # "all connected"
            print 'Etimer2 --> draw left ', self.inst.name, time.ctime()
            self.redraw_leftpanel()
            self.etimer2.Stop()


    def PV_Panel(self, pvname): # , panel, sizer, current_wid=None):
        """ try to create a PV Panel for the given pv
        returns quickly for an unconnected PV, to be tried later
        by the timer"""
        pvname = str(pvname)

        if '.' not in pvname:
            pvname = '%s.VAL' % pvname

        if pvname not in self.pvlist.pvs:
            self.pvlist.connect_pv(pvname)
        
        # print 'PV Panel ', self.inst.name, pvname, len(self.pvlist.pvs), time.ctime()
        if pvname in self.pvlist.pvs:
            pv = self.pvlist.pvs[pvname]
        else:
            # print 'pvname not yet in pvlist ? ', pvname, len(self.pvlist.pvs)
            return

        # return if not connected
        if not pv.connected:
            print 'pv not connected'
            return

        if pvname not in self.pv_components:
            print 'pv not in components', pvname
            return

        # pv.get_ctrlvars()
        pvtype = self.pv_components[pvname][1]
        if pvtype is None:
            db_pv = self.db.get_pv(pvname)
            try:
                pvtype = str(db_pv.pvtype.name)
            except AttributeError:
                pass

        #   pvtype  = get_pvtypes(pv)[0]
        self.pv_components[pvname] = (True, pvtype, pv)

        # self.db.set_pvtype(pvname, pvtype)
            
    @EpicsFunction
    def save_current_position(self, posname):
        values = {}
        for pv in self.pvs.values():
            values[pv.pvname] = pv.get(as_string=True)
        self.db.save_position(posname, self.inst, values)
        self.write("Saved position '%s' for '%s'" % (posname, self.inst.name))

    def onSavePosition(self, evt=None):
        posname = evt.GetString()
        verify = int(self.db.get_info('verify_overwrite'))
        if verify and posname in self.pos_list.GetItems():

            thispos = self.db.get_position(posname, self.inst)
            postext = ["\nSaved Values were:\n"]
            for pvpos in thispos.pvs:
                postext.append('  %s= %s' % (pvpos.pv.name, pvpos.value))
            postext = '\n'.join(postext)

            ret = popup(self, "Overwrite %s?: \n%s" % (posname, postext),
                        'Verify Overwrite',
                        style=wx.YES_NO|wx.ICON_QUESTION)
            if ret != wx.ID_YES:
                return

        self.save_current_position(posname)
        if posname not in self.pos_list.GetItems():
            self.pos_list.Append(posname)

    @EpicsFunction
    def restore_position(self, posname, exclude_pvs=None, timeout=60.0):
        self.db.restore_position(posname, self.inst,
                                 exclude_pvs=exclude_pvs)
        msg= "Moving to '%s' to position '%s'" % (self.inst.name, posname)
        if exclude_pvs is not None and len(exclude_pvs) > 0:
            msg = "%s (Partial: %i PVs not restored)" % (msg, len(exclude_pvs))
        self.write(msg)
        self.puttimer.Start(50)

    def OnMove(self, evt=None):
        """ on GoTo """
        posname = self.pos_list.GetStringSelection()
        thispos = self.db.get_position(posname, self.inst)
        if thispos is None:
            return

        verify = int(self.db.get_info('verify_move'))
        if verify == 0:
            self.restore_position(posname)
        elif verify == 1:
            dlg = MoveToDialog(self, posname, self.inst, self.db,
                               self.pvs, pvdesc=self.pvdesc)
            dlg.Raise()
            if dlg.ShowModal() == wx.ID_OK:
                exclude_pvs = []
                for pvname, data, in dlg.checkboxes.items():
                    if not data[0].IsChecked():
                        exclude_pvs.append(pvname)
                self.restore_position(posname, exclude_pvs=exclude_pvs)
            else:
                return
            dlg.Destroy()

    def onPosSelect(self, evt=None):
        "  " 
        if evt is not None:
            self.pos_name.SetValue(evt.GetString())
            evt.Skip()

        
    def onRightClick(self, evt=None):
        menu = wx.Menu()
        if not hasattr(self, 'popup_up1'):
            for item in ('popup_up1', 'popup_dn1',
                         'popup_upall', 'popup_dnall',
                         'popup_rename'):
                setattr(self, item,  wx.NewId())
                self.Bind(wx.EVT_MENU, self.onPosRightEvent,
                          id=getattr(self, item))

        menu.Append(self.popup_rename, "Rename Position")
        menu.Append(self.popup_up1, "Move up")
        menu.Append(self.popup_dn1, "Move down")
        menu.Append(self.popup_upall, "Move to top")
        menu.Append(self.popup_dnall, "Move to bottom")
        self.PopupMenu(menu)
        menu.Destroy()

    def onPosRightEvent(self, event=None, posname=None):
        idx = self.pos_list.GetSelection()
        if idx < 0: # no item selected
            return

        wid = event.GetId()
        namelist = self.pos_list.GetItems()
        if wid == self.popup_up1 and idx > 0:
            namelist.insert(idx-1, namelist.pop(idx))
        elif wid == self.popup_dn1 and idx < len(namelist):
            namelist.insert(idx+1, namelist.pop(idx))
        elif wid == self.popup_upall:
            namelist.insert(0, namelist.pop(idx))
        elif wid == self.popup_dnall:
            namelist.append( namelist.pop(idx))
        elif wid == self.popup_rename:
            posname = namelist[idx]
            newname = None
            dlg = RenameDialog(self, posname, self.inst)
            dlg.Raise()
            if dlg.ShowModal() == wx.ID_OK:
                newname = dlg.newname.GetValue()
            dlg.Destroy()
            if newname is not None:
                self.db.rename_position(posname, newname, instrument=self.inst)
                namelist[idx] = newname


        self.pos_list.Clear()
        for posname in namelist:
            self.pos_list.Append(posname)

    def onErase(self, evt=None):
        posname = self.pos_list.GetStringSelection()
        verify = int(self.db.get_info('verify_erase'))

        if verify:
            ret = popup(self, "Erase position '%s'?" % (posname),
                        'Verify Erase',
                        style=wx.YES_NO|wx.ICON_QUESTION)
            if ret != wx.ID_YES:
                return

        self.db.remove_position(posname, self.inst)
        ipos  =  self.pos_list.GetSelection()
        self.pos_list.Delete(ipos)
        self.write("Erased position '%s' for '%s'" % (posname, self.inst.name))


