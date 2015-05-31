import wx
import wx.lib.mixins.inspection

import sys
import time
import os
import shutil

from cStringIO import StringIO
from threading import Thread
from collections import OrderedDict
import base64

import pyfly2

import larch
from  larch_plugins.epics import ScanDB, InstrumentDB

import wx.lib.agw.pycollapsiblepane as CP
import wx.lib.mixins.inspection

from epics import Motor, caput
from epics.wx import MotorPanel, EpicsFunction

from epics.wx.utils import (add_button, add_menu, popup, pack, Closure ,
                            NumericCombo, SimpleText, FileSave, FileOpen,
                            SelectWorkdir, LTEXT, CEN, LCEN, RCEN, RIGHT)

from .configfile import StageConfig
from .icons import bitmaps
from .imageframe import ImageDisplayFrame

ALL_EXP  = wx.ALL|wx.EXPAND
CEN_ALL  = wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_CENTER_VERTICAL
LEFT_CEN = wx.ALIGN_LEFT|wx.ALIGN_CENTER_VERTICAL
LEFT_TOP = wx.ALIGN_LEFT|wx.ALIGN_TOP
LEFT_BOT = wx.ALIGN_LEFT|wx.ALIGN_BOTTOM
CEN_TOP  = wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_TOP
CEN_BOT  = wx.ALIGN_CENTER_HORIZONTAL|wx.ALIGN_BOTTOM


CONFIG_DIR  = '//cars5/Data/xas_user/config/SampleStage/'
WORKDIR_FILE = os.path.join(CONFIG_DIR, 'workdir.txt')
ICON_FILE = os.path.join(CONFIG_DIR, 'micro.ico')

AUTOSAVE_DIR = "//cars5/Data/xas_user"
AUTOSAVE_TMP = os.path.join(AUTOSAVE_DIR, '_tmp_.jpg')
AUTOSAVE_FILE = "%s/%s" % (AUTOSAVE_DIR, 'IDEuscope_Live.jpg')
INSTRUMENT_NAME = 'IDE_SampleStage'

IMG_W, IMG_H  = 1928, 1448

class ImagePanel(wx.Panel):
    def __init__(self, parent, camera, update_rate=1.0):
        super(ImagePanel, self).__init__(parent,  -1, size=(990, 745))
        self.camera = camera
        self.parent = parent
        self.info  = {}
        self.cam_name = '-'
        self.update_rate = update_rate
        self.count = 0
        self.fps = 0.0
        self.has_scalebar = False
        self.scale = 0.60
        self.SetBackgroundColour("#EEEEEE")
        self.starttime = time.clock()
        self.last_autosave = 0
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_SIZE, self.onSize)
        self.Bind(wx.EVT_PAINT, self.onPaint)
        self.Bind(wx.EVT_TIMER, self.onTimer, self.timer)
        self.timer.Start(50)

    def onSize(self, evt):
        frame_w, frame_h = evt.GetSize()
        self.scale = min(frame_w*1.01/IMG_W, frame_h*1.01/IMG_H)
        self.Refresh()
        evt.Skip()

    def onTimer(self, event=None):
        self.Refresh()

    def onPaint(self, event):
        self.count += 1
        now = time.clock()
        elapsed = now - self.starttime
        if elapsed >= self.update_rate:
            self.fps = self.count / elapsed
            self.parent.write_framerate(" %.2f fps\n" % (self.fps))
            self.starttime = now
            self.count = 0
        if self.scale < 0.2: self.scale=0.2
        self.image = self.camera.GrabWxImage(scale=self.scale, rgb=True)
        bitmap = wx.BitmapFromImage(self.image)

        img_w, img_h =  bitmap.GetSize()
        pan_w, pan_h =  self.GetSize()
        pad_w, pad_h = (pan_w-img_w)/2.0, (pan_h-img_h)/2.0

        dc = wx.AutoBufferedPaintDC(self)
        dc.Clear()
        dc.DrawBitmap(bitmap, pad_w, pad_h, useMask=True)
        dc.SetPen(wx.Pen('Red', 1.5, wx.SOLID))
        dc.BeginDrawing()
        if self.has_scalebar:
            dc.DrawLine(img_w-20, img_h-60, img_w-200, img_h-60)
        dc.EndDrawing()

        now = time.clock()
        if (now - self.last_autosave)  > 1.0:
            try:
                self.image.SaveFile(AUTOSAVE_TMP, wx.BITMAP_TYPE_JPEG)
                self.last_autosave = now
                shutil.copy(AUTOSAVE_TMP, AUTOSAVE_FILE)
            except:
                pass
            if self.cam_name == '-':
                self.cam_name = self.info.get('modelName', '-')


class ControlPanel(wx.Panel):
    motorgroups = {'fine': ('fineX', 'fineY'),
                   'coarse': ('X', 'Y'),
                   'focus': ('Z', None),
                   'theta': ('theta', None)}

    def __init__(self, parent):
        wx.Panel.__init__(self, parent, -1)

        self.parent = parent
        self.tweaks = {}
        self.tweaklist = {}
        self.motorwids = {}
        self.SetMinSize((280, 500))
        self.get_tweakvalues()

        fine_p = self.group_panel(label='Fine Stages', group='fine',
                                      precision=4,
                                      buttons=[('Zero Fine Motors',
                                                self.onZeroFineMotors)])

        coarse_p = self.group_panel(label='Coarse Stages', group='coarse')
        focus_p = self.group_panel(label='Focus', group='focus')
        theta_p = self.group_panel(label='Theta', group='theta')

        sizer = wx.BoxSizer(wx.VERTICAL)
        for panel in (fine_p, coarse_p, focus_p, theta_p):
            sizer.Add((3, 3))
            sizer.Add(panel,   0, ALL_EXP|LEFT_TOP)
            sizer.Add((3, 3))
            sizer.Add(wx.StaticLine(self, size=(290, 3)), 0, CEN_TOP)
        pack(self, sizer)

    @EpicsFunction
    def connect_motors(self):
        "connect to epics motors"
        self.motors = {}
        self.sign = {None: 1}
        for pvname, val in self.parent.config['stages'].items():
            pvname = pvname.strip()
            label = val['label']
            self.motors[label] = Motor(name=pvname)
            self.sign[label] = val['sign']

        for mname in self.motorwids:
            self.motorwids[mname].SelectMotor(self.motors[mname])

    def group_panel(self, label='Fine Stages', group='fine',
                    precision=3, buttons=None):
        """make motor group panel """
        motors = self.motorgroups[group]

        is_xy = motors[1] is not None
        panel  = wx.Panel(self)

        init_tweaks = dict(fine=6, coarse=6, focus=5, theta=8)

        self.tweaks[group] = NumericCombo(panel, self.tweaklist[group],
                                          precision=precision, init=init_tweaks[group])

        slabel = wx.BoxSizer(wx.HORIZONTAL)
        slabel.Add(wx.StaticText(panel, label=" %s: " % label, size=(120,-1)),
                   1,  wx.EXPAND|LEFT_BOT)
        slabel.Add(self.tweaks[group], 0,  ALL_EXP|LEFT_TOP)

        smotor = wx.BoxSizer(wx.VERTICAL)
        smotor.Add(slabel, 0, ALL_EXP)

        for mnam in motors:
            if mnam is None: continue
            self.motorwids[mnam] = MotorPanel(panel, label=mnam, psize='small')
            self.motorwids[mnam].desc.SetLabel(mnam)
            smotor.Add(self.motorwids[mnam], 0, ALL_EXP|LEFT_TOP)

        if buttons is not None:
            for label, action in buttons:
                smotor.Add(add_button(panel, label, action=action))

        btnbox = self.make_button_panel(panel, full=is_xy, group=group)
        btnbox_style = CEN_BOT
        if is_xy:
            btnbox_style = CEN_TOP

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(smotor, 0, ALL_EXP|LEFT_TOP)
        sizer.Add(btnbox, 0, btnbox_style, 1)

        pack(panel, sizer)
        return panel

    def make_button_panel(self, parent, group='', full=True):
        panel = wx.Panel(parent)
        if full:
            sizer = wx.GridSizer(3, 3, 1, 1)
        else:
            sizer = wx.GridSizer(1, 3)
        def _btn(name):
            btn = wx.BitmapButton(panel, -1, bitmaps[name],
                                  style = wx.NO_BORDER)
            btn.Bind(wx.EVT_BUTTON, Closure(self.onMove,
                                            group=group, name=name))
            return btn
        if full:
            sizer.Add(_btn('nw'),     0, wx.ALL|wx.EXPAND)
            sizer.Add(_btn('nn'),     0, wx.ALL|wx.EXPAND)
            sizer.Add(_btn('ne'),     0, wx.ALL|wx.EXPAND)
            sizer.Add(_btn('ww'),     0, wx.ALL|wx.EXPAND)
            sizer.Add((2, 2))
            sizer.Add(_btn('ee'),     0, wx.ALL|wx.EXPAND)
            sizer.Add(_btn('sw'),     0, wx.ALL|wx.EXPAND)
            sizer.Add(_btn('ss'),     0, wx.ALL|wx.EXPAND)
            sizer.Add(_btn('se'),     0, wx.ALL|wx.EXPAND)
        else:
            sizer.Add(_btn('ww'),     0, wx.ALL|wx.EXPAND)
            sizer.Add((2, 2))
            sizer.Add(_btn('ee'),     0, wx.ALL|wx.EXPAND)

        pack(panel, sizer)
        return panel

    def onZeroFineMotors(self, event=None):
        "event handler for Zero Fine Motors"
        mot = self.motors
        mot['X'].VAL +=  self.sign['fineX'] * mot['fineX'].VAL
        mot['Y'].VAL +=  self.sign['fineY'] * mot['fineY'].VAL
        time.sleep(0.1)
        mot['fineX'].VAL = 0
        mot['fineY'].VAL = 0

    def get_tweakvalues(self):
        "get settings for tweak values for combo boxes"
        def maketweak(prec=3, tmin=0, tmax=10,
                      decades=7, steps=(1,2,5)):
            steplist = []
            for i in range(decades):
                for step in (j* 10**(i - prec) for j in steps):
                    if (step <= tmax and step > 0.98*tmin):
                        steplist.append(step)
            return steplist

        self.tweaklist['fine']   = maketweak(prec=4, tmax=2.0)
        self.tweaklist['coarse'] = maketweak(tmax=70.0)
        self.tweaklist['focus']  = maketweak(tmax=70.0)
        self.tweaklist['theta']  = maketweak(tmax=9.0)
        self.tweaklist['theta'].extend([10, 20, 30, 45, 90, 180])


    def onMove(self, event, name=None, group=None):
        if name == 'camera':
            return self.save_image()

        twkval = float(self.tweaks[group].GetStringSelection())
        ysign = {'n':1, 's':-1}.get(name[0], 0)
        xsign = {'e':1, 'w':-1}.get(name[1], 0)

        x, y = self.motorgroups[group]
        # print ' MOVE   ', x, xsign, self.sign[x],  y, ysign, self.sign[y]

        xsign = xsign * self.sign[x]
        val = float(self.motorwids[x].drive.GetValue())
        self.motorwids[x].drive.SetValue("%f" % (val + xsign*twkval))
        if y is not None:
            val = float(self.motorwids[y].drive.GetValue())
            ysign = ysign * self.sign[y]
            self.motorwids[y].drive.SetValue("%f" % (val + ysign*twkval))
        try:
            self.motors[x].TWV = twkval
            if y is not None:
                self.motors[y].TWV = twkval
        except:
            pass


class PositionPanel(wx.Panel):
    """panel of position lists, with buttons"""
    def __init__(self, parent): # , size=(175, 200)):
        wx.Panel.__init__(self, parent, -1, size=(300, 500))

        self.SetSize((300, 500))
        self.parent = parent
        self.image_display = None

        self.pos_name =  wx.TextCtrl(self, value="", size=(285, 25),
                                     style= wx.TE_PROCESS_ENTER)
        self.pos_name.Bind(wx.EVT_TEXT_ENTER, self.onSavePosition)

        tlabel = wx.StaticText(self, label="Save Position: ")

        bsize = (60, -1)
        btn_save  = add_button(self, "Save",  size=bsize,
                               action=Closure(self.onSavePosition, from_wid=True))
        btn_goto  = add_button(self, "Go To", size=bsize, action=self.onGo)
        btn_erase = add_button(self, "Erase", size=bsize, action=self.onErasePosition)
        btn_show  = add_button(self, "Show",  size=bsize, action=self.onShowPosition)

        brow = wx.BoxSizer(wx.HORIZONTAL)
        brow.Add(btn_save,  0, ALL_EXP|wx.ALIGN_LEFT, 1)
        brow.Add(btn_goto,  0, ALL_EXP|wx.ALIGN_LEFT, 1)
        brow.Add(btn_erase, 0, ALL_EXP|wx.ALIGN_LEFT, 1)
        brow.Add(btn_show,  0, ALL_EXP|wx.ALIGN_LEFT, 1)

        self.pos_list  = wx.ListBox(self)
        self.pos_list.SetBackgroundColour(wx.Colour(253, 253, 250))
        self.pos_list.Bind(wx.EVT_LISTBOX, self.onSelectPosition)
        self.pos_list.Bind(wx.EVT_RIGHT_DOWN, self.onPosRightClick)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(tlabel,         0, wx.ALIGN_LEFT|wx.ALL)
        sizer.Add(self.pos_name,  0, wx.ALIGN_LEFT|wx.ALL)
        sizer.Add(brow,           0, wx.ALIGN_LEFT|wx.ALL)
        sizer.Add(self.pos_list,  1, ALL_EXP|wx.ALIGN_CENTER, 3)

        pack(self, sizer)
        self.SetMinSize((200, 300))

    def onSavePosition(self, event, from_wid=False):
        name = event.GetString().strip()
        if from_wid:
            name = self.pos_name.GetValue().strip()

        if len(name) < 1:
            return
        if self.parent.v_replace and name in self.positions:
            ret = popup(self, "Overwrite Position %s?" %name,
                        "Veriry Overwrite Position",
                    style=wx.YES_NO|wx.NO_DEFAULT|wx.ICON_QUESTION)

            if ret != wx.ID_YES:
                return
        imgfile = '%s.jpg' % time.strftime('%b%d_%H%M%S')
        fname =  "%s/%s" % (self.parent.imgdir, imgfile)

        imgdata = self.parent.save_image(fname=fname)

        tmp_pos = []
        motors = self.parent.ctrlpanel.motors
        for v in self.parent.config['stages'].values():
            tmp_pos.append(float(motors[v['label']].VAL))

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
        wx.CallAfter(Closure(self.onSelectPosition, event=None, name=name))


    def onShowPosition(self, event):
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
            self.image_displaysh.showb64img(thisimage['data'], title=posname)

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
        motorwids = self.parent.ctrlpanel.motorwids
        for name, val in zip(stage_names, pos_vals):
            motorwids[name['label']].drive.SetValue("%f" % val)
        self.parent.write_message('moved to %s' % posname)

    def onErasePosition(self, event):
        posname = self.pos_list.GetStringSelection()
        ipos  =  self.pos_list.GetSelection()
        if posname is None or len(posname) < 1:
            return
        if self.parent.v_erase:
            ret = popup(self, "Erase  %s?" % (posname),
                        'Verify Erase',
                        style=wx.YES_NO|wx.ICON_QUESTION)
            if ret != wx.ID_YES:
                return
        self.positions.pop(posname)
        self.pos_list.Delete(ipos)
        self.pos_name.Clear()
        self.parent.write_message('Erased Position %s' % posname)
        # self.display_imagefile(fname=None)

    def onSelectPosition(self, event=None, name=None):
        "Event handler for selecting a named position"
        if name is None:
            name = str(event.GetString().strip())
        if name is None or name not in self.positions:
            return
        self.pos_name.SetValue(name)
        thispos = self.positions[name]
        imgfile = "%s/%s" % (self.parent.imgdir, thispos['image'])
        tstamp =  thispos.get('timestamp', None)
        if tstamp is None:
            try:
                img_time = time.localtime(os.stat(imgfile).st_mtime)
                tstamp =  time.strftime('%b %d %H:%M:%S', img_time)
            except:
                tstamp = ''
        # self.parent.display_imagefile(fname=imgfile, name=name, tstamp=tstamp)

    def onPosRightClick(self, event=None):
        menu = wx.Menu()
        # make basic widgets for popup menu
        for item, name in (('popup_up1', 'Move up'),
                           ('popup_dn1', 'Move down'),
                           ('popup_upall', 'Move to top'),
                           ('popup_dnall', 'Move to bottom')):
            setattr(self, item,  wx.NewId())
            wid = getattr(self, item)
            self.Bind(wx.EVT_MENU, self.onPosRightEvent, wid)
            menu.Append(wid, name)
        self.PopupMenu(menu)
        menu.Destroy()

    def onPosRightEvent(self, event=None):
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


class StageFrame(wx.Frame):
    htmllog  = 'SampleStage.html'
    html_header = """<html><head><title>Sample Stage Log</title></head>
<meta http-equiv='Pragma'  content='no-cache'>
<meta http-equiv='Refresh' content='300'>
<body>
    """

    def __init__(self, camera, dbconn=None):

        super(StageFrame, self).__init__(None, wx.ID_ANY, 'IDE Microscope',
                                    style=wx.DEFAULT_FRAME_STYLE , size=(1200, 750))

        self.SetFont(wx.Font(10, wx.SWISS, wx.NORMAL, wx.BOLD, False))

        self.camera = camera
        self.motors = None
        self.dbconn = dbconn
        self.instdb = None
        self.initdb_thread = Thread(target=self.init_larchdb)
        self.initdb_thread.start()

        self.SetTitle("XRM Sample Stage")
        self.read_config(configfile='SampleStage_autosave.ini', get_dir=True)

        self.create_frame()
        self.ctrlpanel.connect_motors()

        # wait for all wx stuff to successfully init, then turn on the camera
        self.camera.Connect()
        self.imgpanel.info = self.camera.info
        self.camera.StartCapture()

        self.initdb_thread.join()
        if self.instdb is not None:
            self.pospanel.instdb = self.instdb
            self.pospanel.set_positions_instdb()
        else:
            self.pospanel.set_positions(self.config['positions'])

    def init_larchdb(self):
        if self.dbconn is not None:
            scandb = ScanDB(**self.dbconn)
            self.instdb = InstrumentDB(scandb)
            print self.instdb.get_instrument(INSTRUMENT_NAME)

    def create_frame(self):
        "build main frame"
        self.create_menus()
        self.statusbar = self.CreateStatusBar(2, wx.CAPTION|wx.THICK_FRAME)
        self.statusbar.SetStatusWidths([-3, -1])

        for index in range(2):
            self.statusbar.SetStatusText('', index)


        self.imgpanel  = ImagePanel(self, self.camera)
        self.ctrlpanel = ControlPanel(self)
        self.pospanel  = PositionPanel(self)

        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.AddMany([(self.ctrlpanel, 0, ALL_EXP|LEFT_CEN, 1),
                       (self.imgpanel,  2, ALL_EXP|LEFT_CEN, 1),
                       (self.pospanel,  1, ALL_EXP|LEFT_CEN, 1)])

        pack(self, sizer)
        icon = wx.Icon(ICON_FILE, wx.BITMAP_TYPE_ICO)
        self.SetIcon(icon)
        self.Bind(wx.EVT_CLOSE, self.onClose)


    def create_menus(self):
        "Create the menubar"
        mbar  = wx.MenuBar()
        fmenu = wx.Menu()
        omenu = wx.Menu()
        add_menu(self, fmenu, label="&Save", text="Save Configuration",
                 action = self.onSave)
        add_menu(self, fmenu, label="&Read", text="Read Configuration",
                 action = self.onRead)

        fmenu.AppendSeparator()
        add_menu(self, fmenu, label="E&xit",  text="Quit Program",
                 action = self.onClose)

        vmove  = wx.NewId()
        verase = wx.NewId()
        vreplace = wx.NewId()
        self.menu_opts = {vmove: 'v_move',
                          verase: 'v_erase',
                          vreplace: 'v_replace'}

        mitem = omenu.Append(vmove, "Verify Go To ",
                             "Prompt to Verify Moving with 'Go To'",
                             wx.ITEM_CHECK)
        mitem.Check()
        self.Bind(wx.EVT_MENU, self.onMenuOption, mitem)

        mitem = omenu.Append(verase, "Verify Erase",
                     "Prompt to Verify Erasing Positions", wx.ITEM_CHECK)
        mitem.Check()
        self.Bind(wx.EVT_MENU, self.onMenuOption, mitem)

        mitem = omenu.Append(vreplace, "Verify Overwrite",
                     "Prompt to Verify Overwriting Positions",  wx.ITEM_CHECK)
        mitem.Check()
        self.Bind(wx.EVT_MENU, self.onMenuOption, mitem)

        omenu.AppendSeparator()
        #add_menu(self, omenu, label="Camera Settings",  text="Edit Camera Settings",
        #         action = self.onSettings)

        mbar.Append(fmenu, '&File')
        mbar.Append(omenu, '&Options')
        self.SetMenuBar(mbar)

        self.popup_up1 = wx.NewId()
        self.popup_dn1 = wx.NewId()
        self.popup_upall = wx.NewId()
        self.popup_dnall = wx.NewId()

    def onMenuOption(self, evt=None):
        """events for options menu: move, erase, overwrite """
        setattr(self, self.menu_opts[evt.GetId()], evt.Checked())

    def read_config(self, configfile=None, get_dir=False):
        "open/read ini config file"
        if get_dir:
            try:
                workdir = open(WORKDIR_FILE, 'r').readline()[:-1]
                os.chdir(workdir)
            except:
                pass
            ret = SelectWorkdir(self)
            if ret is None:
                self.Destroy()
            os.chdir(ret)

        self.cnf = StageConfig(configfile)
        self.config = self.cnf.config
        self.stages    = self.config['stages']
        self.v_move    = self.config['setup']['verify_move']
        self.v_erase   = self.config['setup']['verify_erase']
        self.v_replace = self.config['setup']['verify_overwrite']
        self.finex_dir = self.config['setup']['finex_dir']
        self.finey_dir = self.config['setup']['finey_dir']

        self.imgdir     = 'Sample_Images'
        self.cam_type   = 'flycapture'
        self.cam_adpref = ''
        self.cam_adform = 'JPEG'
        self.cam_weburl = 'http://164.54.160.115/jpg/2/image.jpg'
        try:
            self.imgdir     = self.config['camera']['image_folder']
            # self.cam_type   = self.config['camera']['type']
            self.cam_adpref = self.config['camera']['ad_prefix']
            self.cam_adform = self.config['camera']['ad_format']
            self.cam_weburl = self.config['camera']['web_url']
        except:
            pass

        if not os.path.exists(self.imgdir):
            os.makedirs(self.imgdir)
        if not os.path.exists(self.htmllog):
            self.begin_htmllog()
        self.ConfigCamera()

    def begin_htmllog(self):
        "initialize log file"
        fout = open(self.htmllog, 'w')
        fout.write(self.html_header)
        fout.close()

    @EpicsFunction
    def save_image(self, fname=None):
        "save image to file"
        self.waiting_for_imagefile = True
        imagedata = None
        if self.cam_type.lower().startswith('fly'):
            self.imgpanel.image.SaveFile(fname, wx.BITMAP_TYPE_JPEG)
            imgdata = base64.b4encode(self.imgpanel.image.GetData())

        elif self.cam_type.lower().startswith('web'):
            try:
                imgdata = urlopen(self.cam_weburl).read()
            except:
                self.write_message('could not open camera: %s' % self.cam_weburl)
                return

            if fname is None:
                fname = FileSave(self, 'Save Image File',
                                 wildcard='JPEG (*.jpg)|*.jpg|All files (*.*)|*.*',
                                 default_file='sample.jpg')
            if img is not None and fname is not None:
                out = open(fname, "wb")
                out.write(imgdata)
                out.close()
                self.write_message('saved image to %s' % fname)
                imgdata = base64.b64encode(imgdata)
        else: # areaDetector
            cname = "%s%s1:"% (self.cam_adpref, self.cam_adform.upper())
            caput("%sFileName" % cname, fname, wait=True)
            time.sleep(0.03)
            caput("%sWriteFile" % cname, 1, wait=True)
            self.write_message('saved image to %s' % fname)
            time.sleep(0.05)
            img_ok = False
            t0 = time.time()
            while not img_ok:
                if time.time()-t0 > 15:
                    break
                try:
                    out = open(fname, "rb")
                    imgdata = base64.b64encode(out.read())
                    out.close()
                    img_ok = True
                except:
                    pass
                time.sleep(0.05)
        self.waiting_for_imagefile = False
        return imgdata

    def autosave(self):
        self.cnf.Save('SampleStage_autosave.ini')

    def write_htmllog(self, name):
        thispos = self.config['positions'].get(name, None)
        if thispos is None:
            return
        imgfile = thispos['image']
        tstamp  = thispos['timestamp']
        pos     = ', '.join([str(i) for i in thispos['position']])
        pvnames = ', '.join([i.strip() for i in self.stages.keys()])
        labels  = ', '.join([i['label'].strip() for i in self.stages.values()])

        fout = open(self.htmllog, 'a')
        fout.write("""<hr>
<table><tr><td><a href='Sample_Images/%s'>
    <img src='Sample_Images/%s' width=200></a></td>
    <td><table><tr><td>Position:</td><td>%s</td></tr>
    <tr><td>Saved:</td><td>%s</td></tr>
    <tr><td>Motor Names:</td><td>%s</td></tr>
    <tr><td>Motor PVs:</td><td>%s</td></tr>
    <tr><td>Motor Values:</td><td>%s</td></tr>
    </table></td></tr>
</table>""" % (imgfile, imgfile, name, tstamp, labels, pvnames, pos))
        fout.close()



    @EpicsFunction
    def ConfigCamera(self):
        if self.cam_type.lower().startswith('area'):
            if not self.cam_adpref.endswith(':'):
                self.cam_adpref = "%s:" % self.cam_adpref
            cname = "%s%s1:"% (self.cam_adpref, self.cam_adform.upper())
            caput("%sEnableCallbacks" % cname, 1)
            thisdir = os.path.abspath(os.getcwd())
            thisdir = thisdir.replace('\\', '/').replace('T:/', '/Volumes/Data/')

            caput("%sFilePath" % cname, thisdir)
            caput("%sAutoSave" % cname, 0)
            caput("%sAutoIncrement" % cname, 0)
            caput("%sFileTemplate" % cname, "%s%s")
            if self.cam_adform.upper() == 'JPEG':
                caput("%sJPEGQuality" % cname, 90)


    def write_message(self, msg='', index=0):
        "write to status bar"
        self.statusbar.SetStatusText(msg, index)

    def write_framerate(self, msg):
        "write to status bar"
        self.statusbar.SetStatusText(msg, 1)


    def set_image_size(self, size):
        if self.imgsize is None:
            self.imgsize = size

        if self.GetClientSize() != size:
            self.SetClientSize(size)
            self.Center()

    def onClose(self, event):
        self.camera.StopCapture()
        self.imgpanel.Destroy()
        self.Destroy()

    def onSave(self, event=None):
        fname = FileSave(self, 'Save Configuration File',
                         wildcard='INI (*.ini)|*.ini|All files (*.*)|*.*',
                         default_file='SampleStage.ini')
        if fname is not None:
            self.cnf.Save(fname)
        self.write_message('Saved Configuration File %s' % fname)

        #fname = 'save.jpg'

        #self.imgpanel.image.SaveFile(fname, wx.BITMAP_TYPE_JPEG)


    def onRead(self, event=None):
        fname = FileOpen(self, 'Read Configuration File',
                         wildcard='INI (*.ini)|*.ini|All files (*.*)|*.*',
                         default_file='SampleStage.ini')
        if fname is not None:
            self.read_config(fname)
            self.connect_motors()
            self.pospanel.set_positions(self.config['positions'])
        self.write_message('Read Configuration File %s' % fname)

class ViewerApp(wx.App, wx.lib.mixins.inspection.InspectionMixin):
    def __init__(self, camera_id=0, dbconn=None, debug=True, **kws):
        self.camera_id = camera_id
        self.debug = debug
        self.dbconn = dbconn
        wx.App.__init__(self, **kws)

    def run(self):
        self.MainLoop()

    def createApp(self):
        self.context = pyfly2.Context()
        self.camera = self.context.get_camera(self.camera_id)
        frame = StageFrame(self.camera, dbconn=self.dbconn)
        frame.Show()
        self.SetTopWindow(frame)

    def OnInit(self):
        self.createApp()
        if self.debug:
            self.ShowInspectionTool()
        return True

if __name__ == '__main__':
    ViewerApp().run()
