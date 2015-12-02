import os
import wx
import wx.lib.scrolledpanel as scrolled
import json
import time
from collections import OrderedDict
from epics import caput
from epics.wx.utils import (add_button, add_menu, popup, pack, Closure,
                            SimpleText)

ALL_EXP  = wx.ALL|wx.EXPAND
CEN_ALL  = wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_CENTER_VERTICAL
LEFT_CEN = wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL
LEFT_TOP = wx.ALIGN_LEFT|wx.ALIGN_TOP
LEFT_BOT = wx.ALIGN_LEFT|wx.ALIGN_BOTTOM
CEN_TOP  = wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_TOP
CEN_BOT  = wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_BOTTOM

from .imageframe import ImageDisplayFrame

# import larch
# from  larch_plugins.epics import ScanDB, InstrumentDB
from epicsscan.scandb import ScanDB, InstrumentDB

POS_HEADER = '#SampleViewer POSITIONS FILE v1.0'
class ErasePositionsDialog(wx.Frame):
    """ Erase all positions, with check boxes for all"""
    def __init__(self, positions, instname=None, instdb=None):
        wx.Frame.__init__(self, None, -1, title="Select Positions to Erase")
        self.instname = instname
        self.instdb = instdb
        self.build_dialog(positions)

    def build_dialog(self, positions):
        self.positions = positions

        panel = scrolled.ScrolledPanel(self)
        self.checkboxes = {}
        sizer = wx.GridBagSizer(len(positions)+2, 2)
        sizer.SetVGap(2)        
        sizer.SetHGap(3)        
        sizer.Add(SimpleText(panel, ' Erase Positions?  Warning: CANNOT BE UNDONE!!',
                            colour=wx.Colour(200, 0, 0)), (0, 0), (1, 2),  LEFT_CEN, 2)
        sizer.Add(SimpleText(panel, ' Position Name'),  (1, 0), (1, 1),  LEFT_CEN, 2)
        sizer.Add(SimpleText(panel, 'Erase?'),         (1, 1), (1, 1),  LEFT_CEN, 2)
        sizer.Add(wx.StaticLine(panel, size=(300, 2)), (2, 0), (1, 2),  LEFT_CEN, 2)
        
        irow = 2
        for pname in positions:
            irow += 1
            cbox = self.checkboxes[pname] = wx.CheckBox(panel, -1, "")
            cbox.SetValue(True)
            sizer.Add(SimpleText(panel, "  %s  "%pname), (irow, 0), (1, 1),  LEFT_CEN, 2)
            sizer.Add(cbox,                      (irow, 1), (1, 1),  LEFT_CEN, 2)
        irow += 1
        sizer.Add(wx.StaticLine(panel, size=(300, 2)), (irow, 0), (1, 2),  LEFT_CEN, 2)

        pack(panel, sizer)
        panel.SetMinSize((350, 300))
        panel.SetupScrolling()
        bkws = dict(size=(55, -1))
        btn_ok     = add_button(self, "OK",  action=self.onOK, **bkws)
        btn_cancel = add_button(self, "Cancel", action=self.onCancel,  **bkws)

        brow = wx.BoxSizer(wx.HORIZONTAL)
        brow.Add(btn_ok ,     0, ALL_EXP|wx.ALIGN_LEFT, 1)
        brow.Add(btn_cancel,  0, ALL_EXP|wx.ALIGN_LEFT, 1)

        mainsizer = wx.BoxSizer(wx.VERTICAL)
        mainsizer.Add(panel, 1, 2)
        mainsizer.Add(wx.StaticLine(self, size=(300, 2)), 0, 2)
        mainsizer.Add(brow, 0, 2)
        pack(self, mainsizer)
        self.Raise()
        self.Show()
        
    def onOK(self, event=None):
        if self.instname is not None and self.instdb is not None:
            for pname, cbox in self.checkboxes.items():
                if cbox.IsChecked():
                    print 'erasing: ', pname
                    self.instdb.remove_position(self.instname, pname)
        self.Destroy()

    def onCancel(self, event=None):
        self.Destroy()
        
class PositionPanel(wx.Panel):
    """panel of position lists, with buttons"""
    def __init__(self, parent, viewer, config=None):
        wx.Panel.__init__(self, parent, -1, size=(300, 500))
        self.size = (300, 500)
        self.parent = parent
        self.viewer = viewer
        self.config = config
        self.image_display = None
        self.pos_name =  wx.TextCtrl(self, value="", size=(300, 25),
                                     style= wx.TE_PROCESS_ENTER)
        self.pos_name.Bind(wx.EVT_TEXT_ENTER, self.onSave1)

        tlabel = wx.StaticText(self, label="Save Position: ")

        bkws = dict(size=(55, -1))
        btn_goto  = add_button(self, "Go To", action=self.onGo,    **bkws)
        btn_erase = add_button(self, "Erase", action=self.onErase, **bkws)
        btn_show  = add_button(self, "Show",  action=self.onShow,  **bkws)
        # btn_many  = add_button(self, "Erase Many",  action=self.onEraseMany,  **bkws)

        brow = wx.BoxSizer(wx.HORIZONTAL)
        brow.Add(btn_goto,  0, ALL_EXP|wx.ALIGN_LEFT, 1)
        brow.Add(btn_erase, 0, ALL_EXP|wx.ALIGN_LEFT, 1)
        brow.Add(btn_show,  0, ALL_EXP|wx.ALIGN_LEFT, 1)
        # brow.Add(btn_many,  0, ALL_EXP|wx.ALIGN_LEFT, 1)

        self.pos_list  = wx.ListBox(self)
        self.pos_list.SetBackgroundColour(wx.Colour(253, 253, 250))
        self.pos_list.Bind(wx.EVT_LISTBOX, self.onSelect)
        self.pos_list.Bind(wx.EVT_RIGHT_DOWN, self.onRightClick)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(tlabel,         0, wx.ALIGN_LEFT|wx.ALL)
        sizer.Add(self.pos_name,  0, wx.ALIGN_LEFT|wx.ALL)
        sizer.Add(brow,           0, wx.ALIGN_LEFT|wx.ALL)
        sizer.Add(self.pos_list,  1, ALL_EXP|wx.ALIGN_CENTER, 3)
        # print(" Position Panel ", self.GetSize(), self.size)

        pack(self, sizer)
        self.init_scandb()
        self.last_refresh = 0
        self.get_positions_from_db()
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.onTimer, self.timer)
        self.timer.Start(3000)

    def init_scandb(self):
        dbconn = self.config
        if dbconn is not None:
            self.instname = dbconn.get('instrument', 'microscope_stages')
            if dbconn['port'] in ('', 'None', None):
                dbconn.pop('port')
            scandb = ScanDB(**dbconn)
            self.instdb = InstrumentDB(scandb)
            if self.instdb.get_instrument(self.instname) is None:
                pvs = self.viewer.config['stages'].keys()
                self.instdb.add_instrument(self.instname, pvs=pvs)
                

    def onSave1(self, event):
        "save from text enter"
        self.onSave(event.GetString().strip())

    def onSave2(self, event):
        "save from button push"
        self.onSave(self.pos_name.GetValue().strip())

    def onSave(self, name):
        if len(name) < 1:
            return

        if name in self.positions and self.viewer.v_replace:
            ret = popup(self, "Overwrite Position %s?" % name,
                        "Veriry Overwrite Position",
                        style=wx.YES_NO|wx.NO_DEFAULT|wx.ICON_QUESTION)
            if ret != wx.ID_YES:
                return

        imgfile = '%s.jpg' % time.strftime('%b%d_%H%M%S')
        imgfile = os.path.join(self.viewer.imgdir, imgfile)
        tmp_pos = self.viewer.ctrlpanel.read_position()
        imgdata, count = None, 0
        if not os.path.exists(self.viewer.imgdir):
            os.makedirs(self.viewer.imgdir)
        while imgdata is None and count <100:
            imgdata = self.viewer.save_image(imgfile)
            if imgdata is None:
                time.sleep(0.5)
            count = count + 1

        imgdata['source'] = 'SampleStage'
        imgdata['data_format'] = 'file'
        imgdata.pop('data')
        notes = json.dumps(imgdata)
        fullpath = os.path.join(os.getcwd(), imgfile)

        self.positions[name] = {'image': fullpath,
                                'timestamp': time.strftime('%b %d %H:%M:%S'),
                                'position': tmp_pos,
                                'notes':  notes}

        if name not in self.pos_list.GetItems():
            self.pos_list.Append(name)

        self.instdb.save_position(self.instname, name, tmp_pos,
                                  notes=notes, image=fullpath)
            
        self.pos_list.SetStringSelection(name)
        # auto-save file
        self.viewer.autosave(positions=self.positions)
        self.viewer.write_htmllog(name, self.positions[name])

        imgfile_exists = False
        t0 = time.time()
        if not imgfile_exists and time.time()-t0 < 10:
            imgfile_exists = os.path.exists(fullpath)
            time.sleep(0.5)
        if imgfile_exists:
            self.viewer.write_message("Saved Position '%s', image in %s" % 
                                      (name, imgfile))
        else:
            self.viewer.write_message("COULD NOT SAVE IMAGE FILE!!")

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
        try:
            notes = json.loads(thispos['notes'])
        except:
            notes = {'data_format': ''}
        if isinstance(notes, basestring): 
            notes = json.loads(notes)
        label = []
        stages  = self.viewer.config['stages']
        posvals = self.positions[posname]['position']
        for pvname, value in posvals.items():
            value = thispos['position'][pvname]
            desc = stages.get(pvname, {}).get('desc', None)
            if desc is None:
                desc = pvname
            label.append("%s=%.4f" % (desc, float(value)))
        label = ', '.join(label)
        label = '%s: %s' % (posname, label)

        data  = thispos['image']
        if str(notes['data_format']) == 'file':
            self.image_display.showfile(data, title=posname,
                                        label=label)
        elif str(notes['data_format']) == 'base64':
            size = notes.get('image_size', (800, 600))
            self.image_display.showb64img(data, size=size, 
                                          title=posname, label=label)
        else:
            print 'Cannot show image for %s' % posname

    def onGo(self, event):
        posname = self.pos_list.GetStringSelection()
        if posname is None or len(posname) < 1:
            return
        stages  = self.viewer.config['stages']
        posvals = self.positions[posname]['position']
        postext = []
        for pvname, value in posvals.items():
            label = pvname
            desc = stages.get(pvname, {}).get('desc', None)
            if desc is not None:
                label = '%s (%s)' % (desc, pvname)
            postext.append('  %s\t= %.4f' % (label, float(value)))
        postext = '\n'.join(postext)
        if self.viewer.v_move:
            ret = popup(self, "Move to %s?: \n%s" % (posname, postext),
                        'Verify Move',
                        style=wx.YES_NO|wx.ICON_QUESTION)
            if ret != wx.ID_YES:
                return
        for pvname, value in posvals.items():
            caput(pvname, value)
        self.viewer.write_message('moved to %s' % posname)

    def onErase(self, event):
        posname = self.pos_list.GetStringSelection()
        ipos  =  self.pos_list.GetSelection()
        if posname is None or len(posname) < 1:
            return
        if self.viewer.v_erase:
            if wx.ID_YES != popup(self, "Erase  %s?" % (posname),
                                  'Verify Erase',
                                  style=wx.YES_NO|wx.ICON_QUESTION):
                return
        self.instdb.remove_position(self.instname, posname)
        self.positions.pop(posname)
        self.pos_list.Delete(ipos)
        self.pos_name.Clear()
        self.viewer.write_message('Erased Position %s' % posname)

    def onEraseMany(self, event=None):
        if self.instdb is not None:
            ErasePositionsDialog(self.positions.keys(), 
                                 instname=self.instname, 
                                 instdb=self.instdb)

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
        self.viewer.autosave(positions=self.positions)

    def set_positions(self, positions):
        "set the list of position on the left-side panel"
        cur_sel = self.pos_list.GetStringSelection()
        self.pos_list.Clear()
        self.positions = positions
        for name, val in self.positions.items():
            self.pos_list.Append(name)
        if cur_sel in self.positions:
            self.pos_list.SetStringSelection(cur_sel)
        self.last_refresh = time.time()

    def onTimer(self, evt=None):
        posnames =  self.instdb.get_positionlist(self.instname)
        if (len(posnames) != len(self.posnames) or
            (time.time() - self.last_refresh) > 15.0):
            self.get_positions_from_db()

    def get_positions_from_db(self):
        if self.instdb is None:
            return
        positions = OrderedDict()
        iname = self.instname
        posnames =  self.instdb.get_positionlist(iname)
        self.posnames = posnames
        for pname in posnames:
            thispos = self.instdb.get_position(iname, pname)
            image = ''
            notes = {}
            if thispos.image is not None:
                image = thispos.image
            if thispos.notes is not None:
                notes = thispos.notes
            pdat = OrderedDict()
            for pvpos in thispos.pvs:
                pdat[pvpos.pv.name] =  pvpos.value
            positions[pname] = dict(position=pdat, image=image, notes=notes)
        self.set_positions(positions)


    def SavePositions(self, fname):
        """
        save positions to external file
        """
        out = [POS_HEADER]
        for name, val in self.positions.items():
            pos = []
            notes = val['notes']
            img =  val['image']
            ts = val.get('timestamp', '')
            for pvname, val in val['position'].items():
                pos.append((pvname, val))
            out.append(json.dumps((name, pos, notes, img, ts)))
            
        out.append('')
        out = '\n'.join(out)
        fout = open(fname, 'w')
        fout.write(out)
        fout.close()

    def LoadPositions(self, fname):
        """
        save positions to external file
        """
        try:
            fh = open(fname, 'r')
            text = fh.readlines()
            fh.close()
        except IOError:
            print 'IO Error'
            return -1
        header = text[0].replace('\n', '').replace('\r', '')
        if header != POS_HEADER:
            print 'Bad Header', header
            return -2
        for line in text[1:]:
            name, pos, notes, img, ts = json.loads(line)
            tmp_pos = OrderedDict(pos)
          
            try:
                self.positions[name] = {'image': img, 'timestamp': ts,
                                        'position': tmp_pos, 'notes': notes}
            except:
                print 'Cannot set', name, tmp_pos, notes, img
            try:
                self.instdb.save_position(self.instname, name, tmp_pos,
                                          notes=json.dumps(notes), image=img)
            except:
                print 'Could save ', name, tmp_pos, notes, img
            #print(" Import Pos ", name, img, notes)
            
        self.set_positions(self.positions)
            
        return 0
