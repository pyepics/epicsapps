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

import larch
from  larch_plugins.epics import ScanDB, InstrumentDB

from epics import caput
from epics.wx import EpicsFunction

from epics.wx.utils import (add_menu, pack, Closure ,
                            NumericCombo, SimpleText, FileSave, FileOpen,
                            SelectWorkdir, LTEXT, CEN, LCEN, RCEN, RIGHT)

from .configfile import StageConfig
from .icons import icons
from .controlpanel import ControlPanel
from .positionpanel import PositionPanel

from .imagepanel_fly2 import ImagePanel_Fly2

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



class StageFrame(wx.Frame):
    htmllog  = 'SampleStage.html'
    html_header = """<html><head><title>Sample Stage Log</title></head>
<meta http-equiv='Pragma'  content='no-cache'>
<meta http-equiv='Refresh' content='300'>
<body>
    """

    def __init__(self, dbconn=None, station='Station_13IDE'):

        super(StageFrame, self).__init__(None, wx.ID_ANY, 'IDE Microscope',
                                    style=wx.DEFAULT_FRAME_STYLE , size=(1200, 750))

        self.SetFont(wx.Font(10, wx.SWISS, wx.NORMAL, wx.BOLD, False))

        self.motors = None
        self.dbconn = dbconn
        self.instdb = None
        self.initdb_thread = Thread(target=self.init_scandb)
        self.initdb_thread.start()

        self.SetTitle("XRM Sample Stage")
        self.read_config(configfile='SampleStage_autosave.ini', get_dir=True)

        self.create_frame(station=station)

        self.initdb_thread.join()
        if self.instdb is not None:
            self.pospanel.instdb = self.instdb
            self.pospanel.set_positions_instdb()
        else:
            self.pospanel.set_positions(self.config['positions'])

        # finally, start camera
        self.imgpanel.Start()

    def init_scandb(self):
        if self.dbconn is not None:
            scandb = ScanDB(**self.dbconn)
            self.instdb = InstrumentDB(scandb)

    def create_frame(self, station='13IDE_Station'):
        "build main frame"
        self.create_menus()
        self.statusbar = self.CreateStatusBar(2, wx.CAPTION|wx.THICK_FRAME)
        self.statusbar.SetStatusWidths([-3, -1])

        for index in range(2):
            self.statusbar.SetStatusText('', index)

        self.ctrlpanel = ControlPanel(self, station=station)
        self.imgpanel  = ImagePanel_Fly2(self, camera_id=self.cam_fly2id, 
                                         writer=self.write_framerate)

        self.pospanel  = PositionPanel(self)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.AddMany([(self.ctrlpanel, 0, ALL_EXP|LEFT_CEN, 1),
                       (self.imgpanel,  5, ALL_EXP|LEFT_CEN, 1),
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
                 action = self.onSaveConfig)
        add_menu(self, fmenu, label="&Read", text="Read Configuration",
                 action = self.onReadConfig)

        fmenu.AppendSeparator()
        add_menu(self, fmenu, label="E&xit",  text="Quit Program",
                 action = self.onClose)

        vmove  = wx.NewId()
        verase = wx.NewId()
        vreplace = wx.NewId()
        self.menu_opts = {vmove: 'v_move', verase: 'v_erase',
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
        mbar.Append(fmenu, '&File')
        mbar.Append(omenu, '&Options')
        self.SetMenuBar(mbar)


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

        cam = self.config['camera']
        self.imgdir     = cam.get('image_folder', 'Sample_Images')
        self.cam_type   = cam.get('type', 'fly2')
        self.cam_fly2id = cam.get('fly2_id', 0)

        self.cam_adpref = cam.get('ad_prefix', '')
        self.cam_adform = cam.get('ad_format', 'JPEG')

        self.cam_weburl = cam.get('web_url', 'http://164.54.160.115/jpg/2/image.jpg')


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

    def save_image(self, fname=None):
        "save image to file"
        imgdata = self.imgpanel.SaveImage(fname)
        if imgdata is None:
            self.write_message('could not save image to %s' % fname)
        else:
            self.write_message('saved image to %s' % fname)
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


    def onClose(self, event):
        self.imgpanel.Stop()
        self.imgpanel.Destroy()
        self.Destroy()

    def onSaveConfig(self, event=None):
        fname = FileSave(self, 'Save Configuration File',
                         wildcard='INI (*.ini)|*.ini|All files (*.*)|*.*',
                         default_file='SampleStage.ini')
        if fname is not None:
            self.cnf.Save(fname)
        self.write_message('Saved Configuration File %s' % fname)


    def onReadConfig(self, event=None):
        fname = FileOpen(self, 'Read Configuration File',
                         wildcard='INI (*.ini)|*.ini|All files (*.*)|*.*',
                         default_file='SampleStage.ini')
        if fname is not None:
            self.read_config(fname)
            self.connect_motors()
            self.pospanel.set_positions(self.config['positions'])
        self.write_message('Read Configuration File %s' % fname)

class ViewerApp(wx.App, wx.lib.mixins.inspection.InspectionMixin):
    def __init__(self, dbconn=None, debug=False, **kws):
        self.dbconn = dbconn
        self.debug = debug
        wx.App.__init__(self, **kws)

    def createApp(self):
        frame = StageFrame(dbconn=self.dbconn)
        frame.Show()
        self.SetTopWindow(frame)

    def OnInit(self):
        self.createApp()
        if self.debug:
            self.ShowInspectionTool()
        return True

if __name__ == '__main__':
    app = ViewerApp(debug=True)
    app.MainLoop()
