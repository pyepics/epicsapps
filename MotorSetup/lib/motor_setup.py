#!/usr/bin/python
#
# Motor Setup GUI

import os
import sys
import time
import shutil

import wx
import wx.lib.agw.flatnotebook as flat_nb
import wx.lib.mixins.inspection

import epics
from epics.wx import finalize_epics, EpicsFunction
from epics.wx.utils import  (empty_bitmap, add_button, add_menu, pack, popup,
                    Closure, NumericCombo, FileSave, FileOpen, SelectWorkdir)
from epics.wx import MotorDetailPanel

from motordb import isMotorDB, MotorDB

from configfile import MotorsConfig
from utils import GUIColors, ConnectDialog, set_font_with_children, MDB_WILDCARD
 
from motorapp_utils import SaveMotorDialog, MotorChoiceDialog, MotorUpdateDialog


FNB_STYLE = flat_nb.FNB_NO_X_BUTTON|flat_nb.FNB_X_ON_TAB|flat_nb.FNB_SMART_TABS
FNB_STYLE |= flat_nb.FNB_NO_NAV_BUTTONS|flat_nb.FNB_FF2

ICON_FILE = 'motorapp.ico'

TEMPLATE_TOP = '''file "$(CARS)/CARSApp/Db/motor.db"
{
pattern
{P,  M,  DTYP,  C,  S,  DESC,  EGU,  DIR,  VELO, VBAS, ACCL, BDST, BVEL, BACC, SREV, UREV, PREC, DHLM, DLLM}'''


FILE_IN_USE_MSG = """The motor database file  %s
may be in use:
    Machine = %s
    Process = %s

Using two applications with a single file can cause data corruption!

Would you like this application to use this motor database file?
"""



class MotorSetupFrame(wx.Frame):
    def __init__(self, parent=None, server='sqlite', dbname=None, conf=None, **kwds):

        self.config = MotorsConfig(name=None)
        self.db, self.dbname = self.connect_db(server=server, dbname=dbname)
        if self.db is None:
            return
        wx.Frame.__init__(self, parent=parent, title='Epics Motor Setup',
                          size=(630, 700), **kwds)

        self.colors = GUIColors()
        self.SetBackgroundColour(self.colors.bg)

        wx.EVT_CLOSE(self, self.onClose)
        self.create_Statusbar()
        self.create_Menus()
        self.create_Frame()

    def connect_db(self, server, dbname=None, new=False):
        """connects to a db, possibly creating a new one"""

        if server == 'mysql':
            db = MotorDB(server=server)
            return db, dbname
        if dbname is None:
            filelist = self.config.get_dblist()
            if new:
                filelist = None
            dlg = ConnectDialog(filelist=filelist)
            dlg.Raise()
            if dlg.ShowModal() == wx.ID_OK:
                dbname = dlg.filebrowser.GetValue()
                if not dbname.endswith('.mdb'):
                    dbname = "%s.mdb" % dbname
            else:
                return None, dbname
            dlg.Destroy()

        db = MotorDB()
        if isMotorDB(dbname):
            db.connect(dbname)
            set_hostpid = True
            if not db.check_hostpid():
                hostname = db.get_info('host_name')
                pid     =  db.get_info('process_id')
                ret = popup(None, FILE_IN_USE_MSG % (os.path.abspath(dbname),
                                                     hostname, pid),
                            'Database in use',
                            style=wx.YES_NO|wx.ICON_EXCLAMATION)
                set_hostpid = (ret != wx.ID_YES)
            if set_hostpid:
                db.set_hostpid()

        else:
            db.create_newdb(dbname, connect=True)
        self.config.set_current_db(dbname)
        return db, dbname

    def create_Frame(self):
        self.nb = flat_nb.FlatNotebook(self, wx.ID_ANY, agwStyle=FNB_STYLE)

        colors = self.colors
        self.nb.SetActiveTabColour(colors.nb_active)
        self.nb.SetTabAreaColour(colors.nb_area)
        self.nb.SetNonActiveTabTextColour(colors.nb_text)
        self.nb.SetActiveTabTextColour(colors.nb_activetext)
        self.nb.SetBackgroundColour(colors.bg)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.nb, 1, wx.EXPAND)

        self.create_nbpages()
        self.SetMinSize((525, 625))

        pack(self, sizer)
        try:
            self.SetIcon(wx.Icon(ICON_FILE, wx.BITMAP_TYPE_ICO))
        except:
            pass
        self.Refresh()

    def create_nbpages(self):
        self.Freeze()
        if self.nb.GetPageCount() > 0:
            self.nb.DeleteAllPages()
        self.Thaw()


    def create_Menus(self):
        """create menus"""
        mbar = wx.MenuBar()
        file_menu = wx.Menu()

        add_menu(self, file_menu,
                 "Connect to a Motor\tCtrl+N", 
                 "Connect to a  Motor",
                 action=self.onNewMotor)
        add_menu(self, file_menu,
                 "&Save Motor Settings\tCtrl+S", 
                 "Save Motor Settings to Database",
                 action=self.onSaveMotor)
        add_menu(self, file_menu,
                 "&Read Motor Settings\tCtrl+R", 
                 "Read Motor Settings from Database",
                 action=self.onReadMotor)
        file_menu.AppendSeparator()
        add_menu(self, file_menu,
                 "&Copy All Motor Template for all motors\tCtrl+T" ,
                 "Copy Template Paragraph to Clipboard",
                 action=Closure(self.onCopyTemplate, all=True))
        add_menu(self, file_menu,
                 "&Write Motor Template to File for all motors\tCtrl+W", 
                 "Write Paragraph a Template File",
                 action=Closure(self.onWriteTemplate, all=True))
        add_menu(self, file_menu,
                 "&Copy Motor Template for this motor" ,
                 "Copy Template Paragraph to Clipboard",
                 action=Closure(self.onCopyTemplate, all=False))
        add_menu(self, file_menu,
                 "&Write Motor Template to File for this motor", 
                 "Write Paragraph a Template File",
                 action=Closure(self.onWriteTemplate, all=False))

        file_menu.AppendSeparator()
        add_menu(self, file_menu,
                 "E&xit\tCtrl+X", "Terminate the program",
                 action=self.onClose)

        mbar.Append(file_menu, "&File")
        self.SetMenuBar(mbar)

    def create_Statusbar(self):
        "create status bar"
        self.statusbar = self.CreateStatusBar(2, wx.CAPTION|wx.THICK_FRAME)
        self.statusbar.SetStatusWidths([-4,-1])
        for index, name  in enumerate(("Messages", "Status")):
            self.statusbar.SetStatusText('', index)

    def write_message(self,text,status='normal'):
        self.SetStatusText(text)

    def onNewMotor(self, event=None):
        dlg = wx.TextEntryDialog(self, 'Enter Motor Prefix',
                                       'Enter Motor Prefix', '')
        dlg.Raise()
        if dlg.ShowModal() == wx.ID_OK:
            prefix = dlg.GetValue()
            wx.CallAfter(self.addMotorPage, prefix)
        dlg.Destroy()

    def _MakeTemplate(self, all=False):
        if self.nb.GetPageCount() < 1:
            return

        buff = [TEMPLATE_TOP]
        motors = [self.nb.GetCurrentPage().motor]
        if all:
            motors = [self.nb.GetPage(i).motor for i in range(self.nb.GetPageCount())]

        # print "MOTORS : ", all, motors
        # for i in range(self.nb.GetPageCount()):
        #     print i, self.nb.GetPage(i)
        #     print i, self.nb.GetPage(i).motor
        # print self.nb.GetCurrentPage()
        # print self.nb.GetCurrentPage().motor
        
        for motor in motors:
            #  {P,  M,  DTYP,  C,  S,  DESC,  EGU,  DIR,  VELO, VBAS, ACCL, BDST, BVEL, BACC, SREV, UREV, PREC, DHLM, DLLM}
            pref = motor._prefix
            if pref.endswith('.'):
                pref = pref[:-1]
            pref, mname = pref.split(':')
            dtype = motor.get('DTYP', as_string=True)
            direc = motor.get('DIR', as_string=True)

            fmt = '{%s:, %s, "%s", %i, %i, "%s", %s, %s, %f, %f, %f, %f, %f, %f, %i, %f, %i, %f, %f}' 
            buff.append('# VAL=%f, OFF=%f, NTM=%i' % (motor.VAL, motor.OFF, motor.NTM))
            buff.append(fmt % (pref, mname, dtype, motor.CARD, -1, motor.DESC, motor.EGU,
                               direc, motor.VELO, motor.VBAS, motor.ACCL, motor.BDST, motor.BVEL, 
                               motor.BACC, motor.SREV, motor.UREV, motor.PREC, motor.DHLM, motor.DLLM))

        buff.append('}')
        return '\n'.join(buff)

    def onWriteTemplate(self, event=None, all=False):
        motor = self.nb.GetCurrentPage().motor
        name = motor._prefix.replace(':', '_').replace('.', '_')
        fname = FileSave(self, 'Save Template File',
                         wildcard='Template Files(*.template)|*.template|All files (*.*)|*.*',
                         default_file='Motor_%s.template' % name)
        if fname is not None:
            fout = open(fname, 'w+')
            fout.write("%s\n" % self._MakeTemplate(all=all))
            fout.close()
        self.write_message('Wrote Template to %s' % fname)

    def onCopyTemplate(self, event=None, all=False):
        dat = wx.TextDataObject()
        dat.SetText(self._MakeTemplate(all=all))
        wx.TheClipboard.Open()
        wx.TheClipboard.SetData(dat)
        wx.TheClipboard.Close()
        self.write_message('Copied Template to Clipboard')
        
    def onSaveMotor(self, event=None):
        try:
            motor = self.nb.GetCurrentPage().motor
        except AttributeError:
            pass
        
        dlg = SaveMotorDialog(self, motor)
        dlg.Raise()
        if dlg.ShowModal() == wx.ID_OK:
            name = dlg.GetName()
            desc = dlg.GetDesc()
            wx.CallAfter(self.saveMotorSettingsDb, motor, name, desc)
        dlg.Destroy()

    def onReadMotor(self, event=None, motorname=None):
        if motorname is None:
            dlg = MotorChoiceDialog(self, self.db.get_all_motors())
            dlg.Raise()
            if dlg.ShowModal() == wx.ID_OK:
                motorname = dlg.getMotorName()
            dlg.Destroy()
        if motorname is None:
            return
        db_motor = self.db.get_motor(motorname)
        if db_motor is None:
            return
        try:
            curmotor = self.nb.GetCurrentPage().motor
        except AttributeError:
            return
            
        dlg = MotorUpdateDialog(self, curmotor, db_motor)
        t0 = time.time()
        while time.time()-t0 < 10.0:
            if dlg.ready:
                break
        if dlg.ShowModal() == wx.ID_OK:
            out = {}
            for key, val in dlg.checkboxes.items():
                if val[0].IsChecked():
                    out[key] = val[1]
            self.update_motor(out)
        dlg.Destroy()

    @EpicsFunction
    def update_motor(self, newvals):
        try:
            motor = self.nb.GetCurrentPage().motor
        except AttributeError:
            return
        for key, val in newvals.items():
            motor.put(key.upper(), val)
        
        
    @EpicsFunction
    def addMotorPage(self, prefix=None, event=None):
        "add motor page"
        motor = epics.Motor(prefix)
        panel = MotorDetailPanel(parent=self, motor=motor)
        self.nb.AddPage(panel, prefix, True)

    @EpicsFunction
    def saveMotorSettingsDb(self, motor, name, desc):
        name = name.replace('\n', ' ').strip()
        if self.db.get_motor(name) is not None:
            msg = """Overwrite Motor settings?
      %s
This will overwrite the old settings
and cannot be undone.""" % name
            dlg = wx.MessageDialog(self, msg, 'Overwrite %s?' % name,
                               wx.NO_DEFAULT|wx.YES_NO|wx.ICON_EXCLAMATION)
            if dlg.ShowModal() != wx.ID_YES:
                return
            dlg.Destroy()
        self.db.add_motor(name, notes=desc, motor=motor)

    def onAbout(self, event=None):
        # First we create and fill the info object
        info = wx.AboutDialogInfo()
        info.Name = "Motor Setup"
        info.Version = "0.1"
        info.Copyright = "2012, Matt Newville, University of Chicago"
        info.Description = """
        Motor Setup is an application to manage Epics Motors, 
        and assist in writing motor template files.
        """

        wx.AboutBox(info)


    def onSelectFont(self, evt=None):
        fontdata = wx.FontData()
        fontdata.SetInitialFont(self.GetFont())
        dlg = wx.FontDialog(self, fontdata)

        if dlg.ShowModal() == wx.ID_OK:
            font = dlg.GetFontData().GetChosenFont()
            set_font_with_children(self, font)
            self.Refresh()
            self.Layout()
        dlg.Destroy()

    @EpicsFunction
    def onClose(self, event):
        self.db.set_hostpid(clear=True)
        self.db.commit()
        self.config.write()
        epics.poll()
        time.sleep(0.1)
        self.Destroy()


class EpicsMotorSetupApp(wx.App, wx.lib.mixins.inspection.InspectionMixin):
    def __init__(self, server='sqlite', dbname=None, **kws):
        self.dbname = dbname
        self.server = server
        wx.App.__init__(self)

    def OnInit(self):
        self.Init()
        frame = MotorSetupFrame(server=self.server, dbname=self.dbname)
        frame.Show()
        self.SetTopWindow(frame)
        return True

if __name__ == '__main__':
    dbname = 'GSECARS_Motors.mdb'
    server='mysql'
    inspect = True
    app = EpicsMotorSetupApp(dbname=dbname, server=server)

    app.MainLoop()
