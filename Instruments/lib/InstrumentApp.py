#!/usr/bin/python
#
#  Instruments GUI

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

from configfile import InstrumentConfig
from instrument import isInstrumentDB, InstrumentDB

from utils import GUIColors, ConnectDialog, set_font_with_children, EIN_WILDCARD
from instrumentpanel import InstrumentPanel

from settingsframe import SettingsFrame, InstSelectionFrame
from editframe import EditInstrumentFrame, NewPositionFrame
from epics_server import EpicsInstrumentServer

from pvconnector import EpicsPVList

FNB_STYLE = flat_nb.FNB_NO_X_BUTTON|flat_nb.FNB_X_ON_TAB|flat_nb.FNB_SMART_TABS
FNB_STYLE |= flat_nb.FNB_DROPDOWN_TABS_LIST|flat_nb.FNB_NO_NAV_BUTTONS

ICON_FILE = 'instrument.ico'

FILE_IN_USE_MSG = """The instrument file  %s
may be in use:
    Machine = %s
    Process = %s

Using two applications with a single file can cause data corruption!

Would you like this application to use this instrument file?
"""

class InstrumentFrame(wx.Frame):
    def __init__(self, parent=None, conf=None, dbname=None, **kwds):


        self.config = InstrumentConfig(name=conf)
        self.db, self.dbname = self.connect_db(dbname)
        if self.db is None:
            return

        self.connected = {}
        self.panels = {}
        self.epics_server = None

        self.server_timer = None
        wx.Frame.__init__(self, parent=parent, title='Epics Instruments',
                          size=(925, -1), **kwds)

        self.pvlist = EpicsPVList(self)
        for pv in self.db.get_allpvs():
            self.pvlist.init_connect(pv.name, is_motor=(4==pv.pvtype_id))

        time.sleep(0.025)
        self.pvlist.show_unconnected()

        self.colors = GUIColors()
        self.SetBackgroundColour(self.colors.bg)

        self.Bind(wx.EVT_CLOSE, self.onClose)
        self.create_Statusbar()
        self.create_Menus()
        self.create_Frame()
        self.enable_epics_server()

    def connect_db(self, dbname=None, new=False):
        """connects to a db, possibly creating a new one"""
        if dbname is None:
            filelist = self.config.get_dblist()
            if new:
                filelist = None
            dlg = ConnectDialog(filelist=filelist)
            dlg.Raise()
            if dlg.ShowModal() == wx.ID_OK:
                dbname = dlg.filebrowser.GetValue()
                if not dbname.endswith('.ein'):
                    dbname = "%s.ein" % dbname
            else:
                return None, dbname
            dlg.Destroy()

        db = InstrumentDB()
        if isInstrumentDB(dbname):
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
        self.nb = flat_nb.FlatNotebook(self, wx.ID_ANY,
                                       agwStyle=FNB_STYLE)

        self.server_timer = wx.Timer(self)
        self.server_timer.Bind(wx.EVT_TIMER, self.OnServerTimer)
        colors = self.colors
        self.nb.SetActiveTabColour(colors.nb_active)
        self.nb.SetTabAreaColour(colors.nb_area)
        self.nb.SetNonActiveTabTextColour(colors.nb_text)
        self.nb.SetActiveTabTextColour(colors.nb_activetext)
        self.nb.SetBackgroundColour(colors.bg)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.nb, 1, wx.EXPAND)

        self.create_nbpages()

        self.SetSize((876,    351))
        self.SetMinSize((875, 350))

        pack(self, sizer)
        try:
            self.SetIcon(wx.Icon(ICON_FILE, wx.BITMAP_TYPE_ICO))
        except:
            pass
        self.Refresh()

    def create_nbpages(self):
        if self.nb.GetPageCount() > 0:
            self.nb.DeleteAllPages()

        for inst in self.db.get_all_instruments():
            if inst.show is None:
                inst.show = 1
            if int(inst.show) == 1:
                self.add_instrument_page(inst)

    def add_instrument_page(self, inst):
        panel = InstrumentPanel(self, inst, db=self.db,
                                size=(925, -1),
                                pvlist = self.pvlist,
                                writer = self.write_message)
        for pv in inst.pvs:
            panel.add_pv(pv.name)

        self.panels[inst.name] = panel
        # self.connect_pvs(inst, wait_time=0.10)
        self.nb.AddPage(panel, inst.name, True)

    def connect_pvs(self, inst, wait_time=0.10):
        """connect to PVs for an instrument.."""
        panel = self.panels[inst.name]
        return

    def create_Menus(self):
        """create menus"""
        mbar = wx.MenuBar()
        file_menu = wx.Menu()
        opts_menu = wx.Menu()
        inst_menu = wx.Menu()
        help_menu = wx.Menu()

        add_menu(self, file_menu,
                 "&Open File", "Open or Create Instruments File",
                 action=self.onOpen)
        add_menu(self, file_menu,
                 "&Save As", "Save Instruments File",
                 action=self.onSave)
        file_menu.AppendSeparator()

        add_menu(self, file_menu,
                 "E&xit", "Terminate the program",
                 action=self.onClose)

        add_menu(self, inst_menu,
                 "&Create New Instrument",
                 "Add New Instrument",
                 action=self.onAddInstrument)

        add_menu(self, inst_menu,
                 "&Edit Current Instrument",
                 "Edit Current Instrument",
                 action=self.onEditInstrument)

        add_menu(self, inst_menu,
                 "Enter a Position for the Current Instrument",
                 "Enter a Position for the Current Instrument",
                 action=self.onEnterPosition)

        inst_menu.AppendSeparator()
        add_menu(self, inst_menu,
                 "&Remove Current Instrument",
                 "Permanently Remove Current Instrument",
                 action=self.onRemoveInstrument)

        add_menu(self, opts_menu, "&Select Instruments to Show",
                 "Change Which Instruments are Shown", 
                 action=self.onSelectInstruments)

        add_menu(self, opts_menu, "&General Settings",
                 "Change Settings for GUI behavior, Epics Connection",
                 action=self.onSettings)


        add_menu(self, opts_menu,
                 "Change &Font", "Select Font",
                 action=self.onSelectFont)

        add_menu(self, help_menu,
                 'About', "More information about this program",
                 action=self.onAbout)

        mbar.Append(file_menu, "&File")
        mbar.Append(opts_menu, "&Options")
        mbar.Append(inst_menu, "&Instruments")
        mbar.Append(help_menu, "&Help")

        self.SetMenuBar(mbar)

    def create_Statusbar(self):
        "create status bar"
        self.statusbar = self.CreateStatusBar(2, wx.CAPTION)
        self.statusbar.SetStatusWidths([-4,-1])
        for index, name  in enumerate(("Messages", "Status")):
            self.statusbar.SetStatusText('', index)

    def write_message(self,text,status='normal'):
        self.SetStatusText(text)

    def enable_epics_server(self):
        """connect to an epics db to act as a server for external access."""
        connect = False
        if (1 == int(self.db.get_info('epics_use', default=0))):
            epics_prefix = self.db.get_info('epics_prefix', default='')
            if len(epics_prefix) > 1:
                connect = True
        if not connect:
            return

        self.epics_server = EpicsInstrumentServer(epics_prefix, db=self.db)
        self.epics_server.Start('Initializing...')

        if self.epics_server is not None and self.server_timer is not None:
            self.epics_server.SetInfo(os.path.abspath(self.dbname))
            self.server_timer.Start(100)

    def OnServerTimer(self, evt=None):
        """Epics Server Events:
        responds to requests from EpicsInstrument Db

        This allows an outside client to make move requests to
        pre-defined instruments/positions in this database.
        """
        server = self.epics_server
        if not server._pvs['TSTAMP'].connected:
            return
        server.SetTimeStamp()
        req = server._request
        if server._inst is None and len(server.InstName)>1:
            server._inst = self.db.get_instrument(server.InstName)

        if server._moving and self.db.restore_complete():
            server.MoveDone()

        elif 'Move' in req:
            move = req.pop('Move')
            if move and server.PosOK==1 and server.InstOK==1:
                if 1 == int(self.db.get_info('epics_use', default=0)):
                    server._moving = 1
                    self.db.restore_position(server.PosName, server._inst)
                    server.Message = 'Moving to %s' % server.PosName
                else:
                    server.MoveDone()

        elif 'Pos' in req:
            posname = req.pop('Pos')
            pos = None
            if server._inst is not None:
                pos = self.db.get_position(posname, instrument=server._inst)
            server.PosOK = {True:1, False:0}[pos is not None]

        elif 'Inst' in req:
            instname = req.pop('Inst')
            inst = self.db.get_instrument(instname)
            if inst is not None:
                server._inst = inst
            server.InstOK = {True:1, False:0}[inst is not None]

            pos = self.db.get_position(server.PosName, instrument=server._inst)
            server.PosOK = {True:1, False:0}[pos is not None]



    def onAddInstrument(self, event=None):
        "add a new, empty instrument and start adding PVs"
        newname = basename = 'New Instrument'
        inst = self.db.get_instrument(newname)
        count = 1
        while inst is not None:
            count += 1
            newname = "%s(%i)" % (basename, count)
            inst = self.db.get_instrument(newname)

        inst = self.db.add_instrument(newname)

        panel = InstrumentPanel(self, inst, db=self.db,
                                pvlist=self.pvlist,
                                size=(925, -1),
                                writer = self.write_message)

        self.nb.AddPage(panel, inst.name, True)
        EditInstrumentFrame(parent=self, db=self.db, inst=inst)

    def onEditInstrument(self, event=None):
        "edit the current instrument"
        inst = self.nb.GetCurrentPage().inst
        EditInstrumentFrame(parent=self, db=self.db, inst=inst)

    def onEnterPosition(self, event=None):
        "enter a new position for the current instrument"
        page = self.nb.GetCurrentPage()
        inst = page.inst
        NewPositionFrame(parent=self, db=self.db, inst=inst,
                         page=page)


    def onRemoveInstrument(self, event=None):
        inst = self.nb.GetCurrentPage().inst
        iname = inst.name

        MSG = "Permanently Remove Instrument '%s'?\nThis cannot be undone!"

        ret = popup(self, MSG % iname,
                    'Remove Instrument',
                    style=wx.YES_NO|wx.ICON_QUESTION)
        if ret != wx.ID_YES:
            return
        self.db.remove_instrument(inst)
        self.db.commit()
        pages = {}
        for i in range(self.nb.GetPageCount()):
            pages[self.nb.GetPageText(i)] = i

        self.nb.DeletePage(pages[iname])

    def onSettings(self, event=None):
        try:
            self.settings_frame.Raise()
        except:
            self.settting_frame = SettingsFrame(parent=self, db=self.db)

    def onSelectInstruments(self, event=None):
        try:
            self.instsel_frame.Raise()
        except:
            self.instsel_frame = InstSelectionFrame(parent=self, db=self.db)

    def onAbout(self, event=None):
        # First we create and fill the info object
        info = wx.AboutDialogInfo()
        info.Name = "Epics Instruments"
        info.Version = "0.4"
        info.Copyright = "2013, Matt Newville, University of Chicago"
        info.Description = """
        Epics Instruments is an application to manage Epics PVs.
        An Instrument is defined as a collection of Epics PV.
        For each Instrument, any number of Positions can be
        saved and later restored simply by selecting that name.
        """

        wx.AboutBox(info)

    def onOpen(self, event=None):
        dbname = FileOpen(self, 'Open Instrument File',
                         wildcard=EIN_WILDCARD,
                         default_file=self.dbname)
        if dbname is not None:
            self.db.set_hostpid(clear=True)
            self.db.close()
            time.sleep(1)
            self.db, self.dbname = self.connect_db(dbname)            
            self.config.set_current_db(dbname)
            self.db.set_hostpid(clear=False)
            self.config.write()
            self.create_nbpages()

#     def onNew(self, event=None):
#         fname = FileOpen(self, 'New Instrument File',
#                          wildcard=EIN_WILDCARD,
#                          default_file=self.dbname)
# 
#         self.db.close()
#         time.sleep(1)
#         self.dbname = fname
# 
#         self.connect_db(dbname=fname, new=True)
#         self.config.set_current_db(fname)
#         self.config.write()
#         self.create_nbpages()
# 

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
            self.config.set_current_db(outfile)
            self.config.write()

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

    # @EpicsFunction
    def onClose(self, event):
        self.config.write()

        display_order = [self.nb.GetPage(i).inst.name for i in range(self.nb.GetPageCount())]
        for inst in self.db.get_all_instruments():
            inst.show = 0
            if inst.name in display_order:
                inst.show = 1
                inst.display_order = display_order.index(inst.name)
        self.db.set_hostpid(clear=True)
        self.db.commit()
        time.sleep(0.25)
        
        for name, pv in self.pvlist.pvs.items():
            pv.clear_callbacks()
            pv.disconnect()
            time.sleep(0.001)
            
        if self.epics_server is not None:
            self.epics_server.Shutdown()

        time.sleep(0.25)
        
        self.Destroy()


class EpicsInstrumentApp(wx.App, wx.lib.mixins.inspection.InspectionMixin):
    def __init__(self, conf=None, dbname=None, **kws):
        self.conf  = conf
        self.dbname  = dbname
        wx.App.__init__(self)

    def OnInit(self):
        self.Init()
        frame = InstrumentFrame(conf=self.conf, dbname=self.dbname)
        frame.Show()
        self.SetTopWindow(frame)
        return True

if __name__ == '__main__':
    conf = None
    dbname = None
    inspect = True
    if inspect:
        app = EpicsInstrumentApp(dbname=dbname, conf=conf)
    else:
        app = wx.App()
        InstrumentFrame(conf=conf, dbname=dbname).Show()

    app.MainLoop()
