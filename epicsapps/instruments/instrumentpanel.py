#!/usr/bin/python

import time
import wx

import epics
from epics.wx import (EpicsFunction, PVText, PVFloatCtrl, PVTextCtrl,
                      PVEnumChoice, MotorPanel)
from wxutils import pack, Popup, Button, SimpleText

from ..utils import  GUIColors, get_pvtypes, get_pvdesc, normalize_pvname

ALL_EXP  = wx.ALL|wx.EXPAND

MOTOR_FIELDS = ('.SET', '.LLM', '.HLM',  '.LVIO', '.TWV', '_able.VAL',
                '.HLS', '.LLS', '.SPMG', '.DESC')

class RenameDialog(wx.Dialog):
    """Rename a Position"""
    msg = '''Select Recent Instrument File, create a new one'''
    def __init__(self, parent, posname, instname, **kws):
        self.posname = posname
        self.instname = instname
        title = "Rename Position '{posname}' for '{instname}' ?"
        wx.Dialog.__init__(self, parent, wx.ID_ANY, title=title)
        panel = wx.Panel(self)
        colors = GUIColors()

        self.SetFont(parent.GetFont())
        titlefont  = self.GetFont()
        titlefont.PointSize += 2
        titlefont.SetWeight(wx.BOLD)

        sizer = wx.GridBagSizer(10, 3)

        labstyle  = wx.ALIGN_LEFT|wx.ALL
        rlabstyle = wx.ALIGN_RIGHT|wx.ALL
        tstyle    = wx.ALIGN_LEFT

        label1  = SimpleText(panel, 'Old name= {posname}', style=tstyle)
        label2  = SimpleText(panel, 'New name= ' , style=tstyle)
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
        sizer.Add(btnsizer, (3, 0), (1, 2), wx.ALL, 1)
        pack(panel, sizer)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(panel, 0, 0, 0)
        pack(self, sizer)


class MoveToDialog(wx.Dialog):
    """Full Query for Move To for a Position"""
    msg = '''Select Recent Instrument File, create a new one'''
    def __init__(self, parent, posname, instname, db, pvs=None, mode='move', **kws):
        self.posname = posname
        self.instname = instname
        self.pvs  = pvs
        self.mode = mode
        self.db = db
        self.pvs = {}
        for pvname, dat in db.get_instrument_pvs(instname).items():
            rowid, thispv = dat
            pvname = normalize_pvname(pvname)
            self.pvs[pvname] = thispv

        thispos = db.get_position(posname, instname)
        if thispos is None:
            return
        title = f"Move Instrument {instname} to Position '{posname}'?"
        if mode == 'show':
            title = f"Instrument {instname} / Position '{posname}'"
        wx.Dialog.__init__(self, parent, wx.ID_ANY, title=title,
                           size=(700, 200))
        self.build_dialog(parent, thispos)

    @EpicsFunction
    def build_dialog(self, parent, thispos):
        colors = GUIColors()

        self.SetFont(parent.GetFont())
        titlefont  = self.GetFont()
        titlefont.PointSize += 2
        titlefont.SetWeight(wx.BOLD)

        sizer = wx.GridBagSizer(3, 3)

        labstyle  = wx.ALIGN_LEFT|wx.ALL
        rlabstyle = wx.ALIGN_RIGHT|wx.ALL
        tstyle    = wx.ALL
        # title row
        i = 0
        col_labels = ['PV Name', 'Current Value', 'Saved Value']
        if self.mode != 'show':
            col_labels.append('Move?')
        for titleword in col_labels:
            style = rlabstyle
            if 'PV' in titleword:
                style = labstyle
            txt =SimpleText(self, titleword, font=titlefont,
                            size=(125, -1),
                            colour=colors.title, style=style)
            sizer.Add(txt, (0, i), (1, 1), style, 2)
            i = i + 1

        sizer.Add(wx.StaticLine(self, size=(650, -1),
                                style=wx.LI_HORIZONTAL),
                  (1, 0), (1, 4), wx.ALIGN_CENTER|wx.GROW|wx.ALL, 0)

        self.checkboxes = {}
        irow = 0
        pos_pvs = self.db.get_position_values(thispos.name, self.instname)
        for pvname, save_val in pos_pvs.items():
            pvname = normalize_pvname(pvname)
            desc = get_pvdesc(pvname)
            if desc != pvname:
                desc = f"{desc} ({pvname})"
            curr_val = None
            if pvname in self.pvs:
                curr_val = self.pvs[pvname].get(as_string=True)

            if curr_val is None:
                # may have been removed from instrument definition
                continue
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
            irow = irow + 1

        sizer.Add(wx.StaticLine(self, size=(650, -1),
                                style=wx.LI_HORIZONTAL),
                  (irow+3, 0), (1, 4), wx.ALIGN_CENTER|wx.GROW|wx.ALL, 0)

        btnsizer = wx.StdDialogButtonSizer()
        btn = wx.Button(self, wx.ID_OK)
        btn.SetDefault()
        btnsizer.AddButton(btn)
        if self.mode != 'show':
            btnsizer.AddButton(wx.Button(self, wx.ID_CANCEL))

        btnsizer.Realize()
        sizer.Add(btnsizer, (irow+4, 2), (1, 2), wx.ALL, 1)
        pack(self, sizer)
        wc, hc = self.GetSize()
        wb, hb = self.GetBestSize()
        w = min(max(wb, wc), 700)
        h = min(max(hb, hc), 350)
        self.SetSize((25*int((w + 10)/25.), 25*int((h + 10)/25.)))

class InstrumentPanel(wx.Panel):
    """ create Panel for an instrument"""
    def __init__(self, parent, instname, db=None, writer=None,
                 pvlist=None, size=(-1, -1)):

        self.last_draw = 0
        self.instname = instname
        self.pvlist = pvlist

        self.db = db
        self.write_message = writer
        self.pvs = {}
        self.pv_components = {}

        wx.Panel.__init__(self, parent, size=size)
        for pvname in self.db.get_instrument_pvs(instname):
            self.add_pv(pvname)

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
        self.inst_title = SimpleText(toprow,  f' {instname} ',
                                     font=titlefont,
                                     colour=colors.title,
                                     minsize=(175, -1),
                                     style=wx.ALIGN_LEFT)

        self.pos_name =  wx.TextCtrl(toprow, value="", size=(300, 25),
                                     style= wx.TE_PROCESS_ENTER)
        self.pos_name.Bind(wx.EVT_TEXT_ENTER, self.onSavePosition)
        topsizer = wx.BoxSizer(wx.HORIZONTAL)
        topsizer.Add(self.inst_title, 1, wx.ALIGN_CENTER, 1)
        topsizer.Add(SimpleText(toprow, 'Save Position:', size=(150, -1)),
                     0,  wx.ALIGN_CENTER, 1)

        topsizer.Add(self.pos_name, 1, wx.GROW, 1)

        pack(toprow, topsizer)
        self.toprow = toprow

        # start a timer to check for when to fill in PV panels
        self.puttimer = wx.Timer(self)
        self.restore_complete = False
        self.restoring_pvs = []
        self.etimer_count = 0
        self.etimer_poll = 25

        self.Bind(wx.EVT_TIMER, self.onPutTimer, self.puttimer)

        rsizer = wx.BoxSizer(wx.VERTICAL)
        btn_goto = Button(rpanel, "Go To", size=(70, -1),
                              action=self.onMove)
        btn_show = Button(rpanel, "Show", size=(70, -1),
                              action=self.onShowPos)
        btn_erase = Button(rpanel, "Erase",  size=(70, -1),
                               action=self.onErase)

        brow = wx.BoxSizer(wx.HORIZONTAL)
        brow.Add(btn_goto,   0, ALL_EXP|wx.ALIGN_LEFT, 1)
        brow.Add(btn_show,  0, ALL_EXP|wx.ALIGN_LEFT, 1)
        brow.Add(btn_erase,  0, ALL_EXP|wx.ALIGN_LEFT, 1)

        self.pos_list  = wx.ListBox(rpanel, size=(225, -1))
        self.pos_list.SetBackgroundColour((240, 240, 240))
        self.pos_list.SetForegroundColour((10, 10, 10))
        self.pos_list.Bind(wx.EVT_RIGHT_DOWN, self.onRightClick)
        self.pos_list.Bind(wx.EVT_LISTBOX, self.onPosSelect)
        self.pos_list.Bind(wx.EVT_LEFT_DCLICK, self.onMove)

        self.pos_timer = wx.Timer(self.pos_list)
        self.pos_list.Bind(wx.EVT_TIMER, self.onPositionTimer, self.pos_timer)
        self.refresh_position_list()

        rsizer.Add(brow,          0, wx.ALIGN_LEFT|wx.ALL)
        rsizer.Add(self.pos_list, 1, wx.GROW|wx.ALL, 1)
        pack(rpanel, rsizer)
        self.pos_list.Disable()

        splitter.SplitVertically(self.leftpanel, rpanel, -150)

        self.leftpanel.SetMinSize((750, 150))
        rpanel.SetMinSize((150, -1))

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(splitter, 1, wx.GROW|wx.ALL, 0)

        pack(self, sizer)
        self.redraw_leftpanel()

    def onPanelExposed(self, **kws):
        # called when notebook is selected
        self.refresh_position_list()

    def onPositionTimer(self, evt=None):
        self.refresh_position_list()
        
    def refresh_position_list(self, **kws):
        new_list = [p.name for p in self.db.get_positions(self.instname)]
        old_list = self.pos_list.GetItems()

        try:
            if old_list != new_list:
                self.pos_list.Clear()
                for name in new_list:
                    self.pos_list.Append(name)
        except:
            print("could not refresh position list")

        

    def undisplay_pv(self, pvname):
        "remove pv from display"
        if pvname in self.pv_components:
            self.pv_components.pop(pvname)
            self.redraw_leftpanel()

    @EpicsFunction
    def redraw_leftpanel(self, force=False):
        """ redraws the left panel """
        if (time.time() - self.last_draw) < 0.5:
            return

        self.Freeze()
        self.Hide()
        self.leftsizer.Clear()

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
                    t0 = time.time()
                    panel = MotorPanel(self.leftpanel, pvname)
                except:
                    pass
            elif pv is not None and hasattr(pv, 'pvname') and pv.pvname not in skip:
                panel = wx.Panel(self.leftpanel)
                sizer = wx.BoxSizer(wx.HORIZONTAL)
                label = SimpleText(panel, pvname,
                                   colour=self.colors.pvname,
                                   minsize=(250,-1), style=wx.ALIGN_LEFT)
                desc = ''
                if pvname.endswith('.VAL'):
                    try:
                        desc = epics.caget(pvname[:-3] + 'DESC')
                    except:
                        pass
                dlabel = SimpleText(panel, desc,
                                    colour=self.colors.pvname,
                                    minsize=(250,-1), style=wx.ALIGN_LEFT)

                if 'enum' in pvtype:
                    ctrl = PVEnumChoice(panel, pv=pv, size=(150, -1))
                elif 'string' in pvtype: #
                    ctrl = PVTextCtrl(panel, pv=pv, size=(200, -1))
                else:
                    ctrl = PVFloatCtrl(panel, pv=pv, size=(150, -1))

                current_comps.append(ctrl)
                current_comps.append(label)

                sizer.Add(label,  0, wx.ALL, 2)
                sizer.Add(ctrl,   0, wx.ALL, 2)
                sizer.Add(dlabel, 0, wx.ALL, 2)

                if (pvtype != 'motor' and icomp < len(pvcomps)-1 and
                    pvcomps[icomp+1][1][1] != 'motor'): #  and False):
                    pass
                    a = """
                    conn, pvtype2, pv2 = pvcomps[icomp+1][1]
                    skip.append(pv2.pvname)

                    l2 = SimpleText(panel, '  %s' % pv2.pvname,
                                    colour=self.colors.pvname,
                                    minsize=(180,-1), style=wx.ALIGN_LEFT)
                    if 'enum' in pvtype2:
                        c2 = PVEnumChoice(panel, pv=pv2, size=(150, -1))
                    elif 'string' in pvtype2: #  in ('string', 'unicode'):
                        c2 = PVTextCtrl(panel, pv=pv2, size=(150, -1))
                    else:
                        c2 = PVFloatCtrl(panel, pv=pv2, size=(150, -1))

                    sizer.Add(l2, 0, wx.ALL, 2)
                    sizer.Add(c2, 0, wx.ALL, 2)
                    current_comps.append(c2)
                    current_comps.append(l2)
                    """
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
                except:
                    pass

        self.Refresh()
        self.Layout()
        self.Thaw()
        self.Show()
        self.pos_list.SetBackgroundColour(wx.WHITE)
        self.pos_list.Enable()
        self.last_draw = time.time()

    @EpicsFunction
    def add_pv(self, pvname):
        """add a PV to the left panel"""
        pvname = normalize_pvname(pvname)
        if len(self.db.pvtype_ids) < 1:
            self.db.map_pvtypes()
        pvrow = self.db.get_pv(pvname)
        pvtype = self.db.pvtype_names.get(pvrow.pvtype_id, 'numeric')
        self.pv_components[pvname] = (False, pvtype,
                                      self.db.get_pv(pvrow.name, None))
        if pvtype == 'motor':
            idot = pvname.find('.')
            for field in MOTOR_FIELDS:
                self.pvlist.connect_pv(f'{pvname[:idot]}{field}')
        self.PV_Panel(pvname)
        self.last_draw = 0.0


    def write(self, msg, status='normal'):
        if self.write_message is None:
            return
        self.write_message(msg, status=status)


    def PV_Panel(self, pvname): # , panel, sizer, current_wid=None):
        """ try to create a PV Panel for the given pv
        returns quickly for an unconnected PV, to be tried later
        by the timer"""
        pvname = str(pvname)

        if '.' not in pvname:
            pvname = '%s.VAL' % pvname

        if pvname not in self.pvlist.pvs:
            self.pvlist.connect_pv(pvname)

        if pvname in self.pvlist.pvs:
            pv = self.pvlist.pvs[pvname]
        else:
            return

        # return if not connected
        if not pv.connected:
            return

        if pvname not in self.pv_components:
            return

        # pv.get_ctrlvars()
        pvtype = self.pv_components[pvname][1]
        if pvtype is None:
            pvrow = self.db.get_pv(pvname)
            try:
                pvtype = str(db_pv.pvtype.name)
            except AttributeError:
                pass

        #   pvtype  = get_pvtypes(pv)[0]
        self.pv_components[pvname] = (True, pvtype, pv)
        self.pvs[pvname] = pv
        # self.db.set_pvtype(pvname, pvtype)

    @EpicsFunction
    def save_current_position(self, posname):
        values = {}
        for pv in self.pvs.values():
            values[pv.pvname] = pv.get(as_string=True)
        self.db.save_position(posname, self.instname, values)
        self.write("Saved position '%s' for '%s'" % (posname, self.instname))

    def onSavePosition(self, evt=None):
        posname = evt.GetString().strip()
        verify = int(self.db.get_info('verify_overwrite'))
        if verify and posname in self.pos_list.GetItems():
            pos_pvs = self.db.get_position_values(posname, self.instname)
            postext = ["Saved PV Values were:\n"]
            for pvname, save_val in pos_pvs.items():
                postext.append(f'  {pvname} = {save_val}')

            postext = '\n'.join(postext)

            ret = Popup(self, f"Overwrite {posname}?: \n{postext}",
                        'Verify Overwrite',
                        style=wx.YES_NO|wx.ICON_QUESTION)
            if ret != wx.ID_YES:
                return

        self.save_current_position(posname)
        if posname not in self.pos_list.GetItems():
            self.pos_list.Append(posname)
        evt.Skip()

    @EpicsFunction
    def restore_position(self, posname, exclude_pvs=None):
        self.restore_posname = posname
        self.write(f"Move '{self.instname}' to position '{self.restore_posname}' in progress")
        self.db.restore_position(posname, self.instname, exclude_pvs=exclude_pvs)
        self.puttimer.Start(100)

    def onPutTimer(self, evt=None):
        """Timer Event for GoTo to look if move is complete."""
        if self.db.restore_complete():
            self.puttimer.Stop()
            self.write(f"Move '{self.instname}' to position '{self.restore_posname}' complete")

    def onMove(self, evt=None):
        """ on GoTo """
        posname = self.pos_list.GetStringSelection()
        thispos = self.db.get_position(posname, self.instname)
        if thispos is None:
            return

        verify = int(self.db.get_info('verify_move'))
        if verify == 0:
            self.restore_position(posname)
        elif verify == 1:
            dlg = MoveToDialog(self, posname, self.instname, self.db, pvs=self.pvs)
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

    def onShowPos(self, evt=None):
        """ on Show Position """
        posname = self.pos_list.GetStringSelection()
        thispos = self.db.get_position(posname, self.instname)
        if thispos is None:
            return
        dlg = MoveToDialog(self, posname, self.instname, self.db,
                           pvs=self.pvs,  mode='show')
        dlg.Raise()
        if dlg.ShowModal() == wx.ID_OK:
            pass
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
            dlg = RenameDialog(self, posname, self.instname)
            dlg.Raise()
            if dlg.ShowModal() == wx.ID_OK:
                newname = dlg.newname.GetValue()
            dlg.Destroy()
            if newname is not None:
                self.db.rename_position(posname, newname, instrument=self.instname)
                namelist[idx] = newname


        self.pos_list.Clear()
        for posname in namelist:
            self.pos_list.Append(posname)

    def onErase(self, evt=None):
        posname = self.pos_list.GetStringSelection()
        verify = int(self.db.get_info('verify_erase'))

        if verify:
            ret = Popup(self, "Erase position '%s'?" % (posname),
                        'Verify Erase',
                        style=wx.YES_NO|wx.ICON_QUESTION)
            if ret != wx.ID_YES:
                return

        self.db.remove_position(posname, self.instname)
        ipos  =  self.pos_list.GetSelection()
        self.pos_list.Delete(ipos)
        self.write("Erased position '%s' for '%s'" % (posname, self.instname))
