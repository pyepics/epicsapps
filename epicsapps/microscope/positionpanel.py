import sys
import os
import wx
import wx.lib.scrolledpanel as scrolled
import wx.dataview as dv
import json
import numpy as np
import time
from datetime import datetime
from epics import caput, get_pv
from epics.wx import EpicsFunction

from functools import partial

from wxutils import (SimpleText, FloatCtrl, MenuItem, Popup, pack,
                     Button, GUIColors, FRAMESTYLE, LEFT, CEN)
DVSTYLE = dv.DV_VERT_RULES|dv.DV_ROW_LINES|dv.DV_MULTIPLE

def add_button(parent, label, size=(-1, -1), action=None):
    "add simple button with bound action"
    thisb = wx.Button(parent, label=label, size=size)
    if hasattr(action, '__call__'):
        parent.Bind(wx.EVT_BUTTON, action, thisb)
    return thisb


from ..instruments import InstrumentDB

from ..utils import MoveToDialog, normalize_pvname, get_pvdesc

from lmfit import Parameters, minimize
from .transformations import superimposition_matrix
from .imageframe import ImageDisplayFrame

ALL_EXP  = wx.ALL|wx.EXPAND
CEN_ALL  = wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_CENTER_VERTICAL
LEFT_CEN = wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL
LEFT_TOP = wx.ALIGN_LEFT|wx.ALIGN_TOP
LEFT_BOT = wx.ALIGN_LEFT|wx.ALIGN_BOTTOM
CEN_TOP  = wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_TOP
CEN_BOT  = wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_BOTTOM

warn_msg = ' Note: ERASING CANNOT BE UNDONE!! Use "Export Positions" to Save!'

def read_xyz(instdb, name, xyz_stages):
    """
    read XYZ Positions from instrument
    returns dictionary of PositionName: (x, y, z)
    """
    out = {}
    for row in instdb.get_positions(name, reverse=True):
        vals =  instdb.get_position_values(row.name, name)
        out[row.name]  = [vals[pos] for pos in xyz_stages]
    return out

def params2rotmatrix(params, mat):
    """--private--  turn fitting parameters
    into rotation matrix
    """
    mat[0][1] = params['c01'].value
    mat[1][0] = params['c10'].value
    mat[0][2] = params['c02'].value
    mat[2][0] = params['c20'].value
    mat[1][2] = params['c12'].value
    mat[2][1] = params['c21'].value
    return mat
#enddef

def resid_rotmatrix(params, mat, v1, v2):
    "--private-- resdiual function for fit"
    mat = params2rotmatrix(params, mat)
    return (v2 - np.dot(mat, v1)).flatten()
#enddef

def calc_rotmatrix(d1, d2):
    """get best-fit rotation matrix to transform coordinates
    from 1st position dict into the 2nd position dict
    """
    labels = []
    d2keys = d2.keys()
    for x in d1.keys():
        if x in d2keys:
            labels.append(x)
        #endif
    #endfor
    labels.sort()
    if len(labels) < 6:
        print( """Error: need at least 6 saved positions
  in common to calculate rotation matrix""")

        return None, None, None
    #endif
    print("Calculate Rotation Matrix with Positions:", labels)
    v1 = np.ones((4, len(labels)))
    v2 = np.ones((4, len(labels)))
    for i, label in enumerate(labels):
        v1[0, i] = d1[label][0]
        v1[1, i] = d1[label][1]
        v1[2, i] = d1[label][2]
        v2[0, i] = d2[label][0]
        v2[1, i] = d2[label][1]
        v2[2, i] = d2[label][2]
    #endfor

    # get initial rotation matrix, assuming that
    # there are orthogonal coordinate systems.
    mat = superimposition_matrix(v1, v2, scale=True)

    params = Parameters()
    params.add('c10', mat[1][0], vary=True)
    params.add('c01', mat[0][1], vary=True)
    params.add('c20', mat[2][0], vary=True)
    params.add('c02', mat[0][2], vary=True)
    params.add('c12', mat[1][2], vary=True)
    params.add('c21', mat[2][1], vary=True)

    fit_result = minimize(resid_rotmatrix, params, args=(mat, v1, v2))
    mat = params2rotmatrix(params, mat)
    return mat, v1, v2

def make_uscope_rotation(instdb,
                         offline_inst='IDE_Microscope',
                         offline_xyz=('13IDE:m1.VAL', '13IDE:m2.VAL', '13IDE:m3.VAL'),
                         online_inst='IDE_SampleStage',
                         online_xyz=('13XRM:m5.VAL', '13XRM:m6.VAL', '13XRM:m4.VAL')):
    """
    Calculate and store the rotation maxtrix needed to convert
    positions from the GSECARS offline microscope (OSCAR)
    to the SampleStage in the microprobe station.

    This calculates the rotation matrix based on all position
    names that occur in the Position List for both instruments.

    Note:
        The result is saved as a json dictionary to the config table
    """
    pos_us = read_xyz(instdb, offline_inst, offline_xyz)
    pos_ss = read_xyz(instdb, online_inst, online_xyz)
    # print('pos us: ', pos_us['A2'])
    # print('pos ss: ', pos_ss['A2'])
    # calculate the rotation matrix
    mat_us2ss, v1, v2 = calc_rotmatrix(pos_us, pos_ss)
    if mat_us2ss is None:
        return
    #endif
    uscope = instdb.get_instrument(offline_inst)
    sample = instdb.get_instrument(online_inst)

    uname = uscope.name.replace(' ', '_')
    sname = sample.name.replace(' ', '_')
    conf_us2ss = "CoordTrans:%s:%s" % (uname, sname)

    us2ss = dict(source=offline_xyz, dest=online_xyz,
                 rotmat=mat_us2ss.tolist())
    instdb.set_config(conf_us2ss, json.dumps(us2ss))

    # calculate the rotation matrix going the other way
    mat_ss2us, v1, v2 = calc_rotmatrix(pos_ss, pos_us)
    conf_ss2us = "CoordTrans:%s:%s" % (sname, uname)
    ss2us = dict(source=online_xyz, dest=offline_xyz,
                 rotmat=mat_ss2us.tolist())
    print("Saving Calibration %s" %  conf_ss2us)
    instdb.set_config(conf_ss2us, json.dumps(ss2us))

######################

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
        sizer = wx.GridBagSizer(2, 3)
        bkws = dict(size=(95, -1))
        btn_ok   = Button(panel, "Erase Selected",   action=self.onOK, **bkws)
        btn_all  = Button(panel, "Select All",    action=self.onAll, **bkws)
        btn_none = Button(panel, "Select None",   action=self.onNone,  **bkws)

        brow = wx.BoxSizer(wx.HORIZONTAL)
        brow.Add(btn_all ,  0, ALL_EXP|wx.ALIGN_LEFT, 1)
        brow.Add(btn_none,  0, ALL_EXP|wx.ALIGN_LEFT, 1)
        brow.Add(btn_ok ,   0, ALL_EXP|wx.ALIGN_LEFT, 1)

        sizer.Add(SimpleText(panel, ' Note: ERASING POSITIONS CANNOT BE UNDONE!! Use "Export Positions" to Save!',
                            colour=wx.Colour(200, 0, 0)), (0, 0), (1, 2),  LEFT_CEN, 2)
        sizer.Add(SimpleText(panel, ' Use "Export Positions" to Save Positions!',
                            colour=wx.Colour(200, 0, 0)), (1, 0), (1, 2),  LEFT_CEN, 2)

        sizer.Add(brow,  (2, 0), (1, 3),  LEFT_CEN, 2)

        sizer.Add(SimpleText(panel, ' Position Name'), (3, 0), (1, 1),  LEFT_CEN, 2)
        sizer.Add(SimpleText(panel, 'Erase?'),         (3, 1), (1, 1),  LEFT_CEN, 2)
        sizer.Add(SimpleText(panel, ' Position Name'), (3, 2), (1, 1),  LEFT_CEN, 2)
        sizer.Add(SimpleText(panel, 'Erase?'),         (3, 3), (1, 1),  LEFT_CEN, 2)
        sizer.Add(wx.StaticLine(panel, size=(500, 2)), (4, 0), (1, 4),  LEFT_CEN, 2)

        irow = 4
        for ip, pname in enumerate(positions):
            cbox = self.checkboxes[pname] = wx.CheckBox(panel, -1, "")
            cbox.SetValue(True)

            if ip % 2 == 0:
                irow += 1
                icol = 0
            else:
                icol = 2
            sizer.Add(SimpleText(panel, "  %s  "%pname), (irow, icol),   (1, 1),  LEFT_CEN, 2)
            sizer.Add(cbox,                              (irow, icol+1), (1, 1),  LEFT_CEN, 2)
        irow += 1
        sizer.Add(wx.StaticLine(panel, size=(500, 2)), (irow, 0), (1, 4),  LEFT_CEN, 2)

        pack(panel, sizer)
        panel.SetupScrolling()

        mainsizer = wx.BoxSizer(wx.VERTICAL)
        mainsizer.Add(panel, 1,  ALL_EXP|wx.GROW|wx.ALIGN_LEFT, 1)
        pack(self, mainsizer)
        self.SetSize((625, 750))
        self.Raise()
        self.Show()

    def onAll(self, event=None):
        for cbox in self.checkboxes.values():
            cbox.SetValue(True)

    def onNone(self, event=None):
        for cbox in self.checkboxes.values():
            cbox.SetValue(False)

    def onOK(self, event=None):
        if self.instname is not None and self.instdb is not None:
            for pname, cbox in self.checkboxes.items():
                if cbox.IsChecked():
                    self.instdb.remove_position(self.instname, pname)
        self.Destroy()

    def onCancel(self, event=None):
        self.Destroy()

#### Erase Many

class PositionModel(dv.DataViewIndexListModel):
    def __init__(self, instdb, instname='SampleStage'):
        dv.DataViewIndexListModel.__init__(self, 0)
        self.instdb = instdb
        self.instname = instname
        self.data = []
        self.posvals = {}
        self.read_data()

    def read_data(self):
        self.data = []
        poslist = self.instdb.get_positions(self.instname)
        for pos in poslist:
            posname = pos.name
            erase = True
            if posname in self.posvals:
                erase = self.posvals[posname]
            self.data.append([posname, erase])
            self.posvals[posname] = erase
        if len(self.data) > 0:
            self.Reset(len(self.data))

    def select_all(self, erase=True):
        for posname in self.posvals:
            self.posvals[posname] = erase
        self.read_data()

    def select_above(self, item):
        itemname = self.GetValue(item, 0)
        val = True
        for posname, _x in self.data:
            self.posvals[posname] = val
            if posname == itemname:
                val = False
        self.read_data()

    def GetColumnType(self, col):
        if col == 1:
            return "bool"
        return "string"

    def GetValueByRow(self, row, col):
        try:
            return self.data[row][col]
        except:
            return None

    def SetValueByRow(self, value, row, col):
        self.data[row][col] = value
        return True

    def GetColumnCount(self):
        try:
            return len(self.data[0])
        except:
            return 0

    def GetCount(self):
        return len(self.data)

    def Compare(self, item1, item2, col, ascending):
        """help for sorting data"""
        if not ascending: # swap sort order?
            item2, item1 = item1, item2
        row1 = self.GetRow(item1)
        row2 = self.GetRow(item2)
        if col == 1:
            return cmp(int(self.data[row1][col]), int(self.data[row2][col]))
        else:
            return cmp(self.data[row1][col], self.data[row2][col])

    def DeleteRows(self, rows):
        rows = list(rows)
        rows.sort(reverse=True)
        for row in rows:
            del self.data[row]
            self.RowDeleted(row)

    def AddRow(self, value):
        self.data.append(value)
        self.RowAppended()


class EraseManyPositionsFrame(wx.Frame) :
    """Erase Many Positions"""
    def __init__(self, instdb, instname, pos=(-1, -1), size=(625, 550), _larch=None):
        self.instname = instname
        self.instdb = instdb
        self.last_refresh = time.monotonic() - 100.0
        self.Font10=wx.Font(10, wx.SWISS, wx.NORMAL, wx.BOLD, 0, "")
        titlefont = wx.Font(12, wx.SWISS, wx.NORMAL, wx.BOLD, 0, "")

        wx.Frame.__init__(self, None, -1,
                          title="Erase Many Positions",
                          style=FRAMESTYLE, size=size)

        self.dvc = dv.DataViewCtrl(self, style=DVSTYLE)
        self.dvc.SetMinSize((600, 350))

        self.SetFont(self.Font10)
        panel = wx.Panel(self, size=(650, -1))
        panel.SetBackgroundColour(wx.Colour(240, 240, 230))

        self.model = PositionModel(self.instdb, instname=self.instname)
        self.dvc.AssociateModel(self.model)

        sizer = wx.GridBagSizer(3, 2)

        irow = 0
        sizer.Add(add_button(panel, label='Select All', size=(150, -1),
                             action=self.onSelAll),
                  (irow, 0), (1, 1), LEFT, 2)
        sizer.Add(add_button(panel, label='Select None', size=(150, -1),
                             action=self.onSelNone),
                  (irow, 1), (1, 1), LEFT, 2)
        sizer.Add(add_button(panel, label='Select All Above Highlighted', size=(250, -1),
                             action=self.onSelAbove),
                  (irow, 2), (1, 2), LEFT, 2)

        irow += 1
        sizer.Add(add_button(panel, label='Erase Selected', size=(150, -1),
                             action=self.onErase),
                  (irow, 0), (1, 1), LEFT, 2)

        warn = SimpleText(panel, warn_msg, size=(450, -1),
                          colour=wx.Colour(200, 0, 0))

        sizer.Add(warn, (irow, 1), (1, 3),  LEFT_CEN, 2)

        pack(panel, sizer)

        for icol, dat in enumerate((('Position Name',  400, 'text'),
                                    ('Erase? ',        100, 'bool'))):
            label, width, dtype = dat
            method = self.dvc.AppendTextColumn
            kws = {}
            if dtype == 'bool':
                method = self.dvc.AppendToggleColumn
                kws = {'mode': dv.DATAVIEW_CELL_ACTIVATABLE}
            method(label, icol, width=width, **kws)
            c = self.dvc.Columns[icol]
            c.Alignment = wx.ALIGN_LEFT
            c.Sortable = False

        mainsizer = wx.BoxSizer(wx.VERTICAL)
        mainsizer.Add(panel,    0, LEFT|wx.GROW, 1)
        mainsizer.Add(self.dvc, 1, LEFT|wx.GROW, 1)

        pack(self, mainsizer)
        if len(self.model.data) > 0:
            self.dvc.EnsureVisible(self.model.GetItem(0))
        self.Bind(wx.EVT_CLOSE, self.onClose)
        self.Show()
        self.Raise()

    def onClose(self, event=None):
        self.Destroy()

    def onRefresh(self, event=None):
        self.update()

    def onErase(self, event=None):
        for posname, erase in reversed(self.model.data):
            if erase:
                self.instdb.remove_position(self.instname, posname)
        self.update()

    def onSelAll(self, event=None):
        self.model.select_all(True)

    def onSelNone(self, event=None):
        self.model.select_all(False)

    def onSelAbove(self, event=None):
        if self.dvc.HasSelection():
            self.model.select_above(self.dvc.GetSelection())

    def update(self):
        self.model.read_data()
        self.Refresh()
        item0 = None
        try:
            item0 = self.model.GetItem(0)
        except:
            print("Could not get any items")
        if item0 is not None:
            self.dvc.EnsureVisible(self.model.GetItem(0))


class TransferPositionsDialog(wx.Frame):
    """ transfer positions from offline microscope"""
    def __init__(self, offline, instname=None, instdb=None, parent=None):
        wx.Frame.__init__(self, None, -1, title="Copy Positions from Offline Microscope")
        self.offline = offline
        self.instname = instname
        self.parent = parent
        self.instdb = instdb
        self.build_dialog()

    def build_dialog(self):
        positions  = self.instdb.get_position_values(self.offline, reverse=True)
        panel = scrolled.ScrolledPanel(self)
        self.checkboxes = {}
        sizer = wx.GridBagSizer(len(positions)+5, 4)
        sizer.SetVGap(2)
        sizer.SetHGap(3)
        bkws = dict(size=(95, -1))
        btn_ok   = Button(panel, "Copy Selected", action=self.onOK, **bkws)
        btn_all  = Button(panel, "Select All",    action=self.onAll, **bkws)
        btn_none = Button(panel, "Select None",   action=self.onNone,  **bkws)

        brow = wx.BoxSizer(wx.HORIZONTAL)
        brow.Add(btn_all ,  0, ALL_EXP|wx.ALIGN_LEFT, 1)
        brow.Add(btn_none,  0, ALL_EXP|wx.ALIGN_LEFT, 1)
        brow.Add(btn_ok ,   0, ALL_EXP|wx.ALIGN_LEFT, 1)


        self.suffix =  wx.TextCtrl(panel, value="", size=(150, -1))
        self.xoff = FloatCtrl(panel, value=0, precision=3, size=(75, -1))
        self.yoff = FloatCtrl(panel, value=0, precision=3, size=(75, -1))
        self.zoff = FloatCtrl(panel, value=0, precision=3, size=(75, -1))

        irow = 0
        sizer.Add(brow,   (irow, 0), (1, 4),  LEFT_CEN, 2)

        irow += 1
        sizer.Add(SimpleText(panel, ' Add Suffix:'), (irow, 0), (1, 1),  LEFT_CEN, 2)
        sizer.Add(self.suffix, (irow, 1), (1, 3), LEFT_CEN, 2)

        irow += 1
        sizer.Add(SimpleText(panel, 'Offsets X, Y, Z:'), (irow, 0), (1, 1),  LEFT_CEN, 2)
        sizer.Add(self.xoff, (irow, 1), (1, 1),  LEFT_CEN, 2)
        sizer.Add(self.yoff, (irow, 2), (1, 1),  LEFT_CEN, 2)
        sizer.Add(self.zoff, (irow, 3), (1, 1),  LEFT_CEN, 2)

        irow += 1
        sizer.Add(SimpleText(panel, ' Position Name'), (irow, 0), (1, 1),  LEFT_CEN, 2)
        sizer.Add(SimpleText(panel, 'Copy?'),          (irow, 1), (1, 1),  LEFT_CEN, 2)
        sizer.Add(SimpleText(panel, ' Position Name'), (irow, 2), (1, 1),  LEFT_CEN, 2)
        sizer.Add(SimpleText(panel, 'Copy?'),          (irow, 3), (1, 1),  LEFT_CEN, 2)

        irow += 1
        sizer.Add(wx.StaticLine(panel, size=(500, 2)), (irow, 0), (1, 4),  LEFT_CEN, 2)

        for ip, pname in enumerate(positions):
            cbox = self.checkboxes[pname] = wx.CheckBox(panel, -1, "")
            cbox.SetValue(True)

            if ip % 2 == 0:
                irow += 1
                icol = 0
            else:
                icol = 2
            sizer.Add(SimpleText(panel, "  %s  "%pname), (irow, icol),   (1, 1),  LEFT_CEN, 2)
            sizer.Add(cbox,                              (irow, icol+1), (1, 1),  LEFT_CEN, 2)
        irow += 1
        sizer.Add(wx.StaticLine(panel, size=(500, 2)), (irow, 0), (1, 4),  LEFT_CEN, 2)

        pack(panel, sizer)
        panel.SetMinSize((700, 550))

        panel.SetupScrolling()

        mainsizer = wx.BoxSizer(wx.VERTICAL)
        mainsizer.Add(panel, 1,  ALL_EXP|wx.GROW|wx.ALIGN_LEFT, 1)
        pack(self, mainsizer)

        self.SetMinSize((700, 550))
        self.Raise()
        self.Show()

    def onAll(self, event=None):
        for cbox in self.checkboxes.values():
            cbox.SetValue(True)

    def onNone(self, event=None):
        for cbox in self.checkboxes.values():
            cbox.SetValue(False)

    def onOK(self, event=None):
        if self.instname is not None and self.instdb is not None:
            suff = self.suffix.GetValue()

            idb = self.instdb
            uscope = idb.get_instrument(self.offline)
            sample = idb.get_instrument(self.instname)
            print("sample   ", uscope, sample)
            uname = uscope.name.replace(' ', '_')
            sname = sample.name.replace(' ', '_')
            conf_name = "CoordTrans:%s:%s" % (uname, sname)

            conf = json.loads(idb.get_config(conf_name).notes)
            print("Transfering positions from ", uscope, ' to ', sample)
            source_pvs = conf['source']
            dest_pvs = conf['dest']
            rotmat = np.array(conf['rotmat'])
            upos = {}
            for pname, cbox in self.checkboxes.items():
                if cbox.IsChecked():
                    v =  idb.get_position_values(pname, self.offline)
                    upos[pname]  = [v[pvn] for pvn in source_pvs]

            newnames = upos.keys()

            vals = np.ones((4, len(upos)))
            for i, pname in enumerate(newnames):
                vals[0, i] = upos[pname][0]
                vals[1, i] = upos[pname][1]
                vals[2, i] = upos[pname][2]

            # ignore potential problems with multiple OpenMP libraries -
            # apparently some cameras have a static link to this?
            os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'
            pred = np.dot(rotmat, vals)
            os.environ['KMP_DUPLICATE_LIB_OK'] = 'FALSE'

            poslist = idb.get_positions(self.instname, reverse=True)
            saved_temp = None

            if len(poslist) < 1 and self.parent is not None:
                saved_temp = '__tmp__'
                if saved_temp in newnames:
                    saved_temp = '__tmp_a0012AZqspkwx9827nf917+o,ppa+'
                self.parent.onSave(saved_temp)
                time.sleep(3.0)
                poslist = idb.get_positions(self.instname, reverse=True)

            pos0 = idb.get_position_values(poslist[0], self.instname)
            spos = {}
            for pvname in sorted(pos0.keys()):
                spos[pvname] = 0.000

            xoffset = self.xoff.GetValue()
            yoffset = self.yoff.GetValue()
            zoffset = self.zoff.GetValue()
            xpv, ypv, zpv = dest_pvs
            for i, pname in enumerate(newnames):
                spos[xpv] = pred[0, i] + xoffset
                spos[ypv] = pred[1, i] + yoffset
                spos[zpv] = pred[2, i] + zoffset
                nlabel = '%s%s' % (pname, suff)
                idb.save_position(self.instname, nlabel, spos)

            if saved_temp is not None:
                self.parent.onErase(posname=saved_temp, query=False)

        self.Destroy()

    def onCancel(self, event=None):
        self.Destroy()

class PositionPanel(wx.Panel):
    """panel of position lists, with buttons"""

    def __init__(self, parent, viewer, instrument='SampleStage',
                 xyzmotors=None, offline_instrument=None,
                 offline_xyzmotors=None, safe_move=None, **kws):
        wx.Panel.__init__(self, parent, -1, size=(300, 500))
        self.size = (300, 600)
        self.parent = parent
        self.viewer = viewer
        self.instrument = instrument
        self.xyzmotors = xyzmotors
        self.offline_instrument = offline_instrument
        self.offline_xyzmotors = offline_xyzmotors
        self.safe_move = safe_move
        self.image_display = None

        self.pos_name =  wx.TextCtrl(self, value="", size=(300, 25),
                                     style= wx.TE_PROCESS_ENTER)
        self.pos_name.Bind(wx.EVT_TEXT_ENTER, self.onSave)

        tlabel = wx.StaticText(self, label="Save Position: ")

        bkws = dict(size=(55, -1))
        btn_goto  = Button(self, "Go To", action=self.onGo,    **bkws)
        btn_erase = Button(self, "Erase", action=self.onErase, **bkws)
        btn_show  = Button(self, "Show",  action=self.onShow,  **bkws)
        brow = wx.BoxSizer(wx.HORIZONTAL)
        brow.Add(btn_goto,  0, ALL_EXP|wx.ALIGN_LEFT, 1)
        brow.Add(btn_erase, 0, ALL_EXP|wx.ALIGN_LEFT, 1)
        brow.Add(btn_show,  0, ALL_EXP|wx.ALIGN_LEFT, 1)
        # brow.Add(btn_many,  0, ALL_EXP|wx.ALIGN_LEFT, 1)

        self.pos_list  = wx.ListBox(self)
        self.pos_list.SetMinSize((275, 1200))
        self.pos_list.SetBackgroundColour(wx.Colour(253, 253, 250))
        self.pos_list.Bind(wx.EVT_LISTBOX, self.onSelect)
        self.pos_list.Bind(wx.EVT_RIGHT_DOWN, self.onRightClick)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(tlabel,         0, wx.ALIGN_LEFT|wx.ALL)
        sizer.Add(self.pos_name,  0, wx.ALIGN_LEFT|wx.ALL)
        sizer.Add(brow,           0, wx.ALIGN_LEFT|wx.ALL)
        sizer.Add(self.pos_list,  1, wx.ALIGN_CENTER, 3)

        self.pos_list.SetSize((275, 1200))
        pack(self, sizer)
        self.SetSize((275, 1300))

        self.instdb = InstrumentDB()

        self.last_refresh = 0
        self.get_positions_from_db()
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.onTimer, self.timer)
        self.timer.Start(2500)

    def onSave(self, event=None, name=None):
        if name is None:
            name = event.GetString().strip()
        if len(name) < 1:
            return

        if name in self.positions and self.viewer.v_replace:
            ret = Popup(self, "Overwrite Position %s?" % name,
                        "Veriry Overwrite Position",
                        style=wx.YES_NO|wx.NO_DEFAULT|wx.ICON_QUESTION)
            if ret != wx.ID_YES:
                return

        imgfile = '%s.jpg' % time.strftime('%b%d_%H%M%S')
        imgfile = os.path.join(self.viewer.imgdir, imgfile)
        tmp_pos = self.viewer.ctrlpanel.read_position()
        print("Read position ", tmp_pos)
        imgdata, count = None, 0
        if not os.path.exists(self.viewer.imgdir):
            os.makedirs(self.viewer.imgdir)
        while imgdata is None and count <100:
            imgdata = self.viewer.save_image(imgfile)
            if imgdata is None:
                time.sleep(0.05)
            count = count + 1

        imgdata['source'] = 'SampleStage'
        imgdata['data_format'] = 'file'
        imgdata.pop('data')
        notes = json.dumps(imgdata)
        fullpath = os.path.join(os.getcwd(), imgfile)

        im2_fullpath = self.viewer.save_videocam()
        thispos = self.positions[name] = {'image': fullpath,
                                          'image2': im2_fullpath,
                                          'timestamp': time.strftime('%b %d %H:%M:%S'),
                                          'position': tmp_pos,
                                          'notes':  notes}

        print("Save Position ", self.instrument, name, tmp_pos)
        self.instdb.save_position(name, self.instrument, tmp_pos,
                                  notes=notes, image=fullpath)
        self.get_positions_from_db()
        # self.pos_list.SetStringSelection(name)

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
        wx.CallAfter(partial(self.viewer.write_htmllog, name=name, thispos=thispos))
        wx.CallAfter(partial(self.onSelect, event=None, name=name))

    def onShow(self, event):
        posname = self.pos_list.GetStringSelection()
        ipos  =  self.pos_list.GetSelection()
        if posname is None or len(posname) < 1:
            return

        thispos = self.positions[posname]
        try:
            notes = json.loads(thispos['notes'])
        except:
            notes = {'data_format': ''}
        if isinstance(notes, str):
            notes = json.loads(notes)

        if 'data_format' not in notes:
            print('Cannot show image for %s' % posname)
            try:
                self.image_display.Destroy()
                self.image_display = None
            except:
                pass
            return

        label = []
        stages  = self.viewer.stages
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

        if self.image_display is None:
            self.image_display = ImageDisplayFrame()
            self.image_display.Raise()

        try:
            self.image_display.Show()
            self.image_display.Raise()
        except:
            self.image_display =  None

        if str(notes['data_format']) == 'file':
            self.image_display.showfile(data, title=posname,
                                        label=label)
        elif str(notes['data_format']) == 'base64':
            size = notes.get('image_size', (800, 600))
            self.image_display.showb64img(data, size=size,
                                          title=posname, label=label)


    @EpicsFunction
    def onGo(self, event):
        posname = self.pos_list.GetStringSelection()
        if posname is None or len(posname) < 1:
            return

        instname = self.instrument

        # pre-load to make sure the PVs are connected
        posvals = {}
        for name, val in self.instdb.get_position_values(posname, instname).items():
            pvname = normalize_pvname(name)
            get_pv(pvname)
            get_pvdesc(pvname)
            posvals[pvname] =  val


        orig, safe = {}, {}
        if self.safe_move is not None:
            for spv in self.safe_move:
                pvname = spv.get('pv', None)
                step = spv.get('step', None)
                sval = spv.get('value', None)
                if pvname is not None:
                    cur_val = get_pv(pvname).get()
                    orig[pvname] = cur_val
                    if step is not None:
                        safe[pvname] = cur_val + step
                    elif sval is not None:
                        safe[pvname] = sval

        time.sleep(0.005)

        def DoMove(pv_data):
            # do move, maybe moving to "Safe Positions" for some PVs
            # while move is in progress.
            if len(safe) > 0:
                for pvname, sval in safe.items():
                    get_pv(pvname).put(sval, wait=True)

            # start move of sample stage
            for pvname, sval in pv_data.items():
                get_pv(pvname).put(sval)

            if len(orig) > 0:
                # finish move of sample stage before restoring Safe Positions
                for pvname, sval in pv_data.items():
                    get_pv(pvname).put(sval, wait=True)

                # then restore safe positions, in order
                for pvname, sval in orig.items():
                    get_pv(pvname).put(sval, wait=True)

        pvdata = {}
        for pvname, value in posvals.items():
            save_val = str(value)
            curr_val = get_pv(pvname).get(as_string=True)
            desc = get_pvdesc(pvname)
            pvdata[pvname] = (desc, save_val, curr_val)

        if self.viewer.v_move:
            md = MoveToDialog(self, pvdata, instname, posname, callback=DoMove)
            spos = self.viewer.imgpanel.GetScreenPosition()
            md.SetPosition((int(spos[0]+200), int(spos[1]+50)))
            md.Raise()
        else:
            pv_data = {}
            for pvname, data in pvdata.items():
                pv_data[pvname] = data[1]
            DoMove(pv_data)

        self.viewer.write_message('moved to %s' % posname)

    def onErase(self, event=None, posname=None, query=True):
        if posname is None:
            posname = self.pos_list.GetStringSelection()
        if posname is None or len(posname) < 1:
            return
        if self.viewer.v_erase and query:
            if wx.ID_YES != Popup(self, "Erase  %s?" % (posname),
                                  'Verify Erase',
                                  style=wx.YES_NO|wx.ICON_QUESTION):
                return

        pos_names = self.pos_list.GetItems()
        ipos = pos_names.index(posname)
        self.instdb.remove_position(posname, self.instrument)
        self.positions.pop(posname)
        self.pos_list.Delete(ipos)
        self.pos_name.Clear()
        self.viewer.write_message('Erased Position %s' % posname)

    def onEraseMany(self, event=None):
        EraseManyPositionsFrame(self.instdb, self.instrument)

    def onMicroscopeTransfer(self, event=None):
        offline =  self.offline_instrument
        if len(offline) > 0 and self.instdb is not None:
            TransferPositionsDialog(offline, instname=self.instrument,
                                    instdb=self.instdb, parent=self)

    def onMicroscopeCalibrate(self, event=None, **kws):
        online = self.instrument
        offline = self.offline_instrument
        if len(online) > 0 and len(offline) > 0 and self.instdb is not None:
            # offline_xyz = self.offline_xyzmotors
            offline_xyz = [s.strip() for s in self.offline_xyzmotors]
            online_xyz  = [s.strip() for s in self.xyzmotors]
            if len(offline_xyz) == 3 and len(online_xyz) == 3:
                print("calibrate %s to %s " % (offline, online))
                # print(offline_xyz, online_xyz)

                make_uscope_rotation(self.instdb,
                                     offline_inst=offline,
                                     offline_xyz=offline_xyz,
                                     online_inst=online,
                                     online_xyz=online_xyz)


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

    def set_positions(self, positions):
        "set the list of position on the left-side panel"
        cur_sel = self.pos_list.GetStringSelection()
        self.pos_list.Clear()
        self.positions = positions
        for name, val in self.positions.items():
            self.pos_list.Append(name)
        if cur_sel in self.positions:
            self.pos_list.SetStringSelection(cur_sel)
        self.last_refresh = 0

    def onTimer(self, evt=None):
        inst = self.instdb.get_instrument(self.instrument)
        poslist = self.instdb.get_rows('position', where={'instrument_id':inst.id})
        npos = len(poslist)
        now = time.time()
        if (npos != len(self.posnames) or (now - self.last_refresh) > 900.0):
            self.get_positions_from_db()
            self.last_refresh = now

    def get_positions_from_db(self):
        if self.instdb is None:
            return
        positions = {}
        iname = self.instrument
        posnames =  [row.name for row in self.instdb.get_positions(iname)]
        self.posnames = posnames
        # self.instdb.make_pvmap()
        for pname in posnames:
            print("POS ", pname)
            thispos = self.instdb.get_position(pname, iname)
            print("Position : ", pname, thispos)
            image = ''
            notes = {}
            if thispos.modify_time is None:
                thispos.modify_time = datatime.isoformat(datetime.now(), sep=' ')

            if thispos.image is not None:
                image = thispos.image
            if thispos.notes is not None:
                notes = thispos.notes
            pdat = {}
            for name, val in self.instdb.get_position_values(pname, iname).items():
                pdat[name] =  val
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
            print( 'IO Error')
            return -1
        header = text[0].replace('\n', '').replace('\r', '')
        if header != POS_HEADER:
            print( 'Bad Header', header)
            return -2
        for line in text[1:]:
            name, pos, notes, img, ts = json.loads(line)
            tmp_pos = dict(pos)

            try:
                self.positions[name] = {'image': img, 'timestamp': ts,
                                        'position': tmp_pos, 'notes': notes}
            except:
                print( 'Cannot set', name, tmp_pos, notes, img)
            try:
                self.instdb.save_position(self.instrument, name, tmp_pos,
                                          notes=json.dumps(notes), image=img)
            except:
                print( 'Could save ', name, tmp_pos, notes, img)
            #print(" Import Pos ", name, img, notes)

        self.set_positions(self.positions)

        return 0
