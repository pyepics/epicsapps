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

from utils import GUIColors, ConnectDialog, set_font_with_children, MDB_WILDCARD
 
#from settingsframe import SettingsFrame
#from editframe import EditInstrumentFrame

FNB_STYLE = flat_nb.FNB_NO_X_BUTTON|flat_nb.FNB_X_ON_TAB|flat_nb.FNB_SMART_TABS
FNB_STYLE |= flat_nb.FNB_NO_NAV_BUTTONS|flat_nb.FNB_FF2

ICON_FILE = 'motorapp.ico'

TEMPLATE_TOP = '''file "$(CARS)/CARSApp/Db/motor.db"
{
pattern
{P,  M,  DTYP,  C,  S,  DESC,  EGU,  DIR,  VELO, VBAS, ACCL, BDST, BVEL, BACC, SREV, UREV, PREC, DHLM, DLLM}
#'''



FILE_IN_USE_MSG = """The motor database file  %s
may be in use:
    Machine = %s
    Process = %s

Using two applications with a single file can cause data corruption!

Would you like this application to use this instrument file?
"""

class MotorSetupFrame(wx.Frame):
    def __init__(self, parent=None, dbname=None, **kwds):
        self.db, self.dbname = self.connect_db(dbname)
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

    def connect_db(self, dbname=None, new=False):
        """connects to a db, possibly creating a new one"""
        if dbname is None:
            dlg = ConnectDialog(filelist=None)
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
        self.SetMinSize((525, 500))

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

    @EpicsFunction
    def connect_pvs(self, inst, wait_time=2.0):
        """connect to PVs for an instrument.."""
        self.connected = False
        for pv in inst.pvs:
            self.epics_pvs[pv.name]  = epics.PV(pv.name)
            time.sleep(0.002)
        t0 = time.time()
        while (time.time() - t0) < wait_time:
            time.sleep(0.002)
            if all(x.connected for x in self.epics_pvs.values()):
                break
        return

    def create_Menus(self):
        """create menus"""
        mbar = wx.MenuBar()
        file_menu = wx.Menu()

        add_menu(self, file_menu,
                 "Connect to a &Motor", "Connect to a  Motor",
                 action=self.onNewMotor)
        add_menu(self, file_menu,
                 "&Save Motor Settings", "Save Motor Settings to Database",
                 action=self.onSaveMotor)
        add_menu(self, file_menu,
                 "&Read Motor Settings", "Read Motor Settings from Database",
                 action=self.onReadMotor)
        file_menu.AppendSeparator()
        add_menu(self, file_menu,
                 "&Copy Motor Template" , "Copy Template Paragraph to Clipboard",
                 action=self.onCopyTemplate)
        add_menu(self, file_menu,
                 "&Write Motor Template to File", "Write Paragraph a Template File",
                 action=self.onWriteTemplate)
        file_menu.AppendSeparator()
        add_menu(self, file_menu,
                 "E&xit", "Terminate the program",
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
        "add a new, empty instrument and start adding PVs"
        dlg = wx.TextEntryDialog(self, 'Enter Motor Prefix',
                                       'Enter Motor Prefix', '')
        dlg.Raise()
        if dlg.ShowModal() == wx.ID_OK:
            prefix = dlg.GetValue()
            wx.CallAfter(self.addMotorPage, prefix)
        dlg.Destroy()

    def onSaveMotor(self, event=None):
        "add a new, empty instrument and start adding PVs"
        print 'would save motor ', event
        page = self.nb.GetCurrentPage()

    def onReadMotor(self, event=None):
        "add a new, empty instrument and start adding PVs"
        print 'would read motor '

    def _MakeTemplate(self):
        motor = self.nb.GetCurrentPage().motor
        if motor is None: 
            return ''

        #  {P,  M,  DTYP,  C,  S,  DESC,  EGU,  DIR,  VELO, VBAS, ACCL, BDST, BVEL, BACC, SREV, UREV, PREC, DHLM, DLLM}
        pref = motor._prefix
        if pref.endswith('.'):
            pref = pref[:-1]
        pref, mname = pref.split(':')
        dtype = motor.get('DTYP', as_string=True)
        direc = motor.get('DIR', as_string=True)

        fmt = '{%s:, %s, "%s", %i, %i, "%s", %s, %s, %f, %f, %f, %f, %f, %f, %i, %f, %i, %f, %f}' 
        dline = fmt % (pref, mname, dtype, motor.CARD, -1, motor.DESC, motor.EGU,
                       direc, motor.VELO, motor.VBAS, motor.ACCL, motor.BDST, motor.BVEL, 
                       motor.BACC, motor.SREV, motor.UREV, motor.PREC, motor.DHLM, motor.DLLM)

        return '\n'.join([TEMPLATE_TOP, dline , '}'])
         
    def onWriteTemplate(self, event=None):
        "add a new, empty instrument and start adding PVs"
        motor = self.nb.GetCurrentPage().motor
        print 'would write template for motor  ', motor
        name = motor._prefix.replace(':', '_').replace('.', '_')
        fname = FileSave(self, 'Save Template File',
                         wildcard='Template Files(*.template)|*.template|All files (*.*)|*.*',
                         default_file='Motor_%s.template' % name)
        if fname is not None:
            fout = open(fname, 'w+')
            fout.write("%s\n" % self._MakeTemplate())
            fout.close()



    def onCopyTemplate(self, event=None):
        "add a new, empty instrument and start adding PVs"
        dat = wx.TextDataObject()
        dat.SetText(self._MakeTemplate())
        wx.TheClipboard.Open()
        wx.TheClipboard.SetData(dat)
        wx.TheClipboard.Close()


    @EpicsFunction
    def addMotorPage(self, prefix=None, event=None):
        "add motor page"
        print 'Add Motor Page ', prefix
        motor = epics.Motor(prefix)
        panel = MotorDetailPanel(parent=self, motor=motor)
        self.nb.AddPage(panel, prefix, True)

    def onAbout(self, event=None):
        # First we create and fill the info object
        info = wx.AboutDialogInfo()
        info.Name = "Motor Setup"
        info.Version = "0.31"
        info.Copyright = "2012, Matt Newville, University of Chicago"
        info.Description = """
        Motor Setup is an application to manage Epics Motors, 
        and assist in writing motor template files.
        """

        wx.AboutBox(info)

    def onSave(self, event=None):
        outfile = FileSave(self, 'Save Instrument File As',
                           wildcard=EIN_WILDCARD,
                           default_file=self.dbname)

        # save current tab/instrument mapping
        fulldbname = os.path.abspath(self.dbname)

        if outfile not in (None, self.dbname, fulldbname):
            self.db.close()
            try:
                shutil.copy(self.dbname, outfile)
            except shutil.Error:
                pass

            time.sleep(1.0)
            self.dbname = outfile

            self.db = InstrumentDB(outfile)

            # set current tabs to the new db

            insts = [(i, self.nb.GetPageText(i)) for i in range(self.nb.GetPageCount())]

            for nbpage, name in insts:
                self.nb.GetPage(nbpage).db = self.db
                self.nb.GetPage(nbpage).inst = self.db.get_instrument(name)

            self.write_message("Saved Instrument File: %s" % outfile)

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

        epics.poll()
        time.sleep(0.1)
        self.Destroy()


class EpicsMotorSetupApp(wx.App, wx.lib.mixins.inspection.InspectionMixin):
    def __init__(self, dbname=None, **kws):
        self.dbname = dbname
        wx.App.__init__(self)

    def OnInit(self):
        self.Init()
        frame = MotorSetupFrame(dbname=self.dbname)
        frame.Show()
        self.SetTopWindow(frame)
        return True

if __name__ == '__main__':
    dbname = 'GSECARS_Motors.mdb'
    inspect = True
    app = EpicsMotorSetupApp(dbname=dbname)


    #app = wx.PySimpleApp()
    #MotorSetupApp(conf=conf, dbname=dbname).Show()

    app.MainLoop()
