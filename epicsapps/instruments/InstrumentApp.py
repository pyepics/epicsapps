#!/usr/bin/python
#
#  Instruments GUI
import os
import time
import shutil

import wx
import wx.lib.agw.flatnotebook as flat_nb
import wx.lib.mixins.inspection
import wx.adv

from wxutils import FileSave, FileOpen, Popup, pack, MenuItem

from .configfile import InstrumentConfig, CONFFILE, get_default_configfile
from .instrument import isInstrumentDB, InstrumentDB
from .creator import make_newdb

from .utils import GUIColors, ConnectDialog, set_font_with_children, EIN_WILDCARD
from .instrumentpanel import InstrumentPanel

from .settingsframe import SettingsFrame, InstSelectionFrame
from .editframe import EditInstrumentFrame, NewPositionFrame, ErasePositionsFrame
from .epics_server import EpicsInstrumentServer

from .pvconnector import EpicsPVList

from ..utils import (get_icon, debugtimer, PasswordSetDialog, PasswordCheckDialog,
                     hash_password, test_password)


FNB_STYLE = flat_nb.FNB_NO_X_BUTTON|flat_nb.FNB_X_ON_TAB|flat_nb.FNB_SMART_TABS
FNB_STYLE |= flat_nb.FNB_DROPDOWN_TABS_LIST|flat_nb.FNB_NO_NAV_BUTTONS


FILE_IN_USE_MSG = """The instrument file  %s
may be in use:
    Machine = %s
    Process = %s

Using two applications with a single file can cause data corruption!

Would you like this application to use this instrument file?
"""

class InstrumentFrame(wx.Frame):
    def __init__(self, parent=None, configfile=None, prompt=False, **kws):

        if isInstrumentDB(configfile):
            dbname = configfile
            configfile = get_default_configfile(CONFFILE)

            self.configfile = InstrumentConfig(fname=configfile)
            self.config = self.configfile.config
            self.config['server'] = 'sqlite'
            self.config['dbname'] = dbname
        else:
            if configfile is None:
                configfile = get_default_configfile(CONFFILE)
            self.configfile = InstrumentConfig(fname=configfile)
            self.config = self.configfile.config

        dt = debugtimer()
        wx.Frame.__init__(self, parent=None, title='Epics Instruments',
                          size=(925, -1), **kws)
        dt.add(' make frame')
        self.pvlist = EpicsPVList(self)
        dt.add(' get pvlist')
        self.connected = {}
        self.panels = {}
        self.epics_server = None
        self.server_timer = None
        self.db, self.dbname = self.connect_db(prompt=prompt, **self.config)

        if self.db is None:
            return
        dt.add('db connected')

        self.admin_pass = self.db.get_info('admin_password', '')
        if len(self.admin_pass) < 32:
            self.admin_pass = ''
        self.admin_expires = 0.0
        self.admin_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.onAdminTimer, self.admin_timer)

        self.colors = GUIColors()
        self.create_Statusbar()
        self.create_Menus()
        dt.add('create menu')
        self.create_Frame()
        dt.add('create frame')
        self.Bind(wx.EVT_CLOSE, self.onClose)
        dt.add('before enable epics')
        self.enable_epics_server()
        dt.add('after enable epics')
        # dt.show()
        # print(time.ctime())

    def connect_db(self, dbname=None, server='sqlite',
                   user=None, password=None, host=None, port=None,
                   recent_dbs=None, new=False, prompt=False, **kws):
        """connects to a db, possibly creating a new one"""
        if prompt or dbname is None:
            dlg = ConnectDialog(parent=self, dbname=dbname, server=server,
                                user=user, password=password, host=host,
                                port=port, recent_dbs=recent_dbs)

            response = dlg.GetResponse()
            dlg.Destroy()
            if not response.ok:
                return None, response.dbname

            server = response.server
            host = response.host
            port = response.port
            user = response.user
            password = response.password
            dbname = response.dbname

            if (response.server.startswith('sqlite') and
                not dbname.endswith('.ein')):
                dbname = "%s.ein" % dbname

        if (server.startswith('sqlite') and not os.path.exists(dbname)):
            make_newdb(dbname)
            time.sleep(0.25)

        db = InstrumentDB(dbname=dbname, server=server, user=user,
                          password=password, host=host, port=port)

        if server.startswith('sqlite'):
            if isInstrumentDB(dbname):
                if getattr(db, 'engine', None) is None:
                    db.connect(dbname, server='sqlite')
                set_hostpid = True
                if not db.check_hostpid():
                    hostname = db.get_info('host_name')
                    pid = db.get_info('process_id')
                    ret = Popup(None, FILE_IN_USE_MSG % (os.path.abspath(dbname),
                                                         hostname, pid),
                                'Database in use',
                                style=wx.YES_NO|wx.ICON_EXCLAMATION)
                    set_hostpid = (ret != wx.ID_YES)
                if set_hostpid:
                    db.set_hostpid()
                db.check_version()
            else:
                db.create_newdb(dbname, connect=True)
        self.config['dbname'] = dbname
        self.config['server'] = server
        self.config['connstr'] = db.conndict
        if 'recent_dbs' not in self.config:
            self.config['recent_dbs'] = []

        if server.lower().startswith('sqlite'):
            if dbname in self.config['recent_dbs']:
                self.config['recent_dbs'].remove(dbname)
            self.config['recent_dbs'].insert(0, dbname)
        else:
            self.config['host'] = host
            self.config['port'] = port
            self.config['user'] = user
            self.config['password'] = password

        for pvid, pvname in db.get_allpvs().items():
            self.pvlist.init_connect(pvname)
        time.sleep(0.025)
        # self.pvlist.show_unconnected()
        return db, dbname

    def create_Frame(self):
        self.nb = flat_nb.FlatNotebook(self, wx.ID_ANY,
                                       agwStyle=FNB_STYLE)
        self.nb.Bind(flat_nb.EVT_FLATNOTEBOOK_PAGE_CHANGED, self.onNBChanged)
        self.nb.Bind(flat_nb.EVT_FLATNOTEBOOK_PAGE_CLOSING, self.onNBClosing)
        colors = self.colors
        self.nb.SetActiveTabColour(colors.nb_active)
        self.nb.SetTabAreaColour(colors.nb_area)
        self.nb.SetNonActiveTabTextColour(colors.nb_text)
        self.nb.SetActiveTabTextColour(colors.nb_activetext)

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.nb, 1, wx.EXPAND)

        self.create_nbpages()

        self.SetSize((876, 351))
        self.SetMinSize((875, 350))

        pack(self, sizer)
        iconfile = get_icon('instrument')
        try:
            self.SetIcon(wx.Icon(iconfile, wx.BITMAP_TYPE_ICO))
        except Exception:
            pass

    def validate_admin(self):
        """returns True if administrator password is not set or the
           administrator password has been entered recently ('admin_timeout'),
           prompting to check password if needed.
        """
        if len(self.admin_pass) < 32:
            return True

        if time.time() < self.admin_expires:
            return True

        dlg = PasswordCheckDialog(self, pwhash=self.admin_pass,
                                  msg='Enter Administrator Password')
        res = dlg.GetResponse()
        if res:
            self.admin_expires = time.time() + 60*float(self.db.get_info('admin_timeout', '15.0'))
            self.admin_timer.Start(1000)
        return res

    def leave_admin_mode(self):
        """leave adminstrator mode, removing instruments that are admin only"""
        self.admin_expires = time.time() - 60
        self.admin_timer.Stop()
        for i in range(self.nb.GetPageCount()):
            page = self.nb.GetPage(i)
            inst = self.db.get_instrument(page.instname)
            if inst.admin_only:
                self.nb.DeletePage(i)


    def create_nbpages(self):
        self.initializing = True
        if self.nb.GetPageCount() > 0:
            self.nb.DeleteAllPages()

        for row in self.db.get_all_instruments():
            if row.show is None:
                self.db.update('instrument',
                               where={'name': row.name}, show=1)
                show = 1
            else:
                show = int(row.show)
            if show:
                if row.admin_only:
                    show = self.validate_admin()
                if show:
                    self.add_instrument_page(row.name)
        self.initializing = False
        self.init_stime = time.time()
        self.init_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.onInitTimer, self.init_timer)
        self.init_timer.Start(2000)

    def onAdminTimer(self, evt=None):
        if time.time() > self.admin_expires:
            self.leave_admin_mode()

    def onInitTimer(self, evt=None):
        # print(f"init timer done {time.time()- self.init_stime:.3f}")
        if time.time() > 10 + self.init_stime:
            self.init_timer.Stop()
            current_page = self.nb.GetCurrentPage()
            callback = getattr(current_page, 'onPanelExposed', None)
            if callable(callback):
                wx.CallAfter(callback, {'updates': True})

    def add_instrument_page(self, instname):
        inst = self.db.get_instrument(instname)
        show = self.validate_admin() if inst.admin_only else True
        if show:
            panel = InstrumentPanel(self, instname, db=self.db,
                                    size=(925, -1),
                                    pvlist = self.pvlist,
                                    writer = self.write_message)
            self.panels[instname] = panel
            self.nb.AddPage(panel, instname, True)

    def onNBClosing(self, event=None):
        current_page = self.nb.GetCurrentPage()
        callback = getattr(current_page, 'onPanelExposed', None)
        if callable(callback):
            callback(updates=False)

    def onNBChanged(self, event=None):
        current_page = self.nb.GetCurrentPage()
        inst = self.db.get_instrument(current_page.instname)
        show = self.validate_admin() if inst.admin_only else True

        pages = {}
        for i in range(self.nb.GetPageCount()):
            pages[self.nb.GetPageText(i)] = i

        if show:
            for i in range(self.nb.GetPageCount()):
                page = self.nb.GetPage(i)
                callback = getattr(page, 'onPanelExposed', None)
                if callable(callback) and not self.initializing:
                    callback(updates=(page==current_page))
        else:
            wx.CallAfter(self.nb.DeletePage, pages[current_page.instname])

    def connect_pvs(self, instname, wait_time=0.10):
        """connect to PVs for an instrument.."""
        return

    def create_Menus(self):
        """create menus"""
        mbar = wx.MenuBar()
        file_menu = wx.Menu()
        opts_menu = wx.Menu()
        inst_menu = wx.Menu()
        help_menu = wx.Menu()

        MenuItem(self, file_menu,
                 "&Open Database", "Open or Create Instruments File/Connection",
                 action=self.onOpen)
        MenuItem(self, file_menu,
                 "&Save", "Save Instruments File",
                 action=self.onSave)
        file_menu.AppendSeparator()

        MenuItem(self, file_menu,
                 "E&xit", "Close the program",
                 action=self.onClose)

        MenuItem(self, inst_menu,
                 "&Create New Instrument",
                 "Add New Instrument",
                 action=self.onAddInstrument)

        inst_menu.AppendSeparator()


        MenuItem(self, inst_menu,
                 "Current Instrument: Enter a Position",
                 "Enter a Position for the Current Instrument",
                 action=self.onEnterPosition)

        MenuItem(self, inst_menu,
                 "Current Instrument: Erase Many Positions",
                 "Erase Positions for the Current Instrument",
                 action=self.onErasePositions)

        MenuItem(self, inst_menu,
                 "Current Instrument: Edit",
                 "Edit Current Instrument",
                 action=self.onEditInstrument)

        MenuItem(self, inst_menu,
                 "Current Instrument: Remove",
                 "Permanently Remove Current Instrument",
                 action=self.onRemoveInstrument)

        MenuItem(self, opts_menu, "&Select Instruments to Show",
                 "Change Which Instruments are Shown",
                 action=self.onSelectInstruments)

        MenuItem(self, opts_menu, "&General Settings",
                 "Change Settings for GUI behavior, Epics Connection",
                 action=self.onSettings)

        MenuItem(self, opts_menu, "Set Administrator Password",
                 "Set a Password to restrict access to selected Instruments",
                 action=self.onSetAdminPassword)

        MenuItem(self, help_menu,
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
        epics_prefix = ''

        if 1 == self.db.get_info('epics_use', as_int=True, default=0):
            epics_prefix = self.db.get_info('epics_prefix', default='')
            if len(epics_prefix) > 1:
                connect = True
        if not connect:
            return

        self.epics_server = EpicsInstrumentServer(epics_prefix, db=self.db)
        self.epics_server.Start('Initializing Epics Listener...')
        if self.epics_server is not None:
            self.epics_server.SetInfo(os.path.abspath(self.dbname))
            self.server_timer = wx.Timer(self)
            self.Bind(wx.EVT_TIMER, self.OnServerTimer, self.server_timer)
            self.server_timer.Start(250)

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
            server._inst = self.db.get_instrument(server.InstName).name
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
                inst = inst.name
            if inst is not None:
                server._inst = inst
            server.InstOK = {True:1, False:0}[inst is not None]

            pos = self.db.get_position(server.PosName, instrument=server._inst)
            server.PosOK = {True:1, False:0}[pos is not None]

    def onAddInstrument(self, event=None):
        "add a new, empty instrument and start adding PVs"
        if not self.validate_admin():
            return
        newname = basename = 'New Instrument'
        inst = self.db.get_instrument(newname)
        count = 1
        while inst is not None:
            count += 1
            newname = f"{basename}({count})"
            inst = self.db.get_instrument(newname)

        inst = self.db.add_instrument(newname)

        panel = InstrumentPanel(self, inst.name, db=self.db,
                                pvlist=self.pvlist,
                                size=(925, -1),
                                writer = self.write_message)

        self.nb.AddPage(panel, inst.name, True)
        EditInstrumentFrame(parent=self, db=self.db, instname=inst.name)

    def onEditInstrument(self, event=None):
        "edit the current instrument"
        if self.validate_admin():
            with_admin_only = len(self.admin_pass) > 32
            instname = self.nb.GetCurrentPage().instname
            EditInstrumentFrame(parent=self, db=self.db,
                                instname=instname, with_admin_only=with_admin_only)

    def onEnterPosition(self, event=None):
        "enter a new position for the current instrument"
        page = self.nb.GetCurrentPage()
        NewPositionFrame(parent=self, db=self.db, instname=page.instname,
                         page=page)

    def onErasePositions(self, event=None):
        ErasePositionsFrame(self, self.nb.GetCurrentPage())

    def onRemoveInstrument(self, event=None):
        current_page = self.nb.GetCurrentPage()
        instname = current_page.instname
        if not self.validate_admin():
            return

        msg = f"Permanently Remove Instrument '{instname}'?\nThis cannot be undone!"
        ret = Popup(self, msg, 'Remove Instrument',
                    style=wx.YES_NO|wx.ICON_QUESTION)
        if ret != wx.ID_YES:
            return
        current_page.pos_timer.Stop()
        current_page.put_timer.Stop()

        pages = {}
        for i in range(self.nb.GetPageCount()):
            pages[self.nb.GetPageText(i)] = i

        self.nb.DeletePage(pages[instname])
        self.db.remove_instrument(instname)

    def onSettings(self, event=None):
        try:
            self.settings_frame.Raise()
        except:
            if self.validate_admin():
                self.settting_frame = SettingsFrame(parent=self, db=self.db)

    def onSetAdminPassword(self, event=None):
        admin_pass = self.admin_pass
        if len(admin_pass) < 40:
            admin_pass = ''
        dlg = PasswordSetDialog(current_hash=admin_pass,
                        msg='Set Administrator Password',
                        rules={'minlen': 8, 'lowercase': 1, 'uppercase': 0,
                                'special': 1, 'digits': 1})

        result = dlg.GetResponse()
        if len(result) > 32:
            self.admin_pass = result
            self.db.set_info('admin_password', result)
            self.write_message('Admin Password set')
        else:
            self.write_message('Admin Password not set')

    def onSelectInstruments(self, event=None):
        try:
            self.instsel_frame.Raise()
        except:
            if self.validate_admin():
                self.instsel_frame = InstSelectionFrame(parent=self, db=self.db)

    def onAbout(self, event=None):
        # First we create and fill the info object
        info = wx.adv.AboutDialogInfo()
        info.Name = "Epics Instruments"
        info.Version = "0.5"
        info.Copyright = "2025, Matt Newville, University of Chicago"
        info.Description = """
        Epics Instruments is an application to manage Epics PVs.
        An Instrument is defined as a collection of Epics PV.
        For each Instrument, any number of Positions can be
        saved and later restored simply by selecting that name.
        """
        wx.adv.AboutBox(info)

    def onOpen(self, event=None):
        dbname = FileOpen(self, 'Open Instrument File',
                         wildcard=EIN_WILDCARD,
                         default_file=self.dbname)
        if dbname is not None:
            self.db.set_hostpid(clear=True)
            self.db.close()
            time.sleep(1)
            self.db, self.dbname = self.connect_db(dbname)
            self.db.set_hostpid(clear=False)
            try:
                self.configfile.write(config=self.config)
            except:
                pass
            self.create_nbpages()

    def onSave(self, event=None):
        outfile = FileSave(self, 'Save Instrument File As',
                           wildcard=EIN_WILDCARD,
                           default_file=self.dbname)

        # save current tab/instrument mapping
        curr_conn = self.db.conndict
        fulldbname = os.path.abspath(self.dbname)
        print("onSave ", fulldbname, self.dbname, outfile)
        if outfile not in (None, self.dbname, fulldbname):
            self.db.close()
            try:
                shutil.copy(self.dbname, outfile)
            except shutil.Error:
                pass

            time.sleep(1.0)
            self.dbname = outfile
            try:
                self.configfile.write(config=self.config)
            except:
                pass
            print(" WRITE OUT FILE ", type(outfile), outfile, curr_conn)
            curr_conn['dbname'] = outfile
            self.db = InstrumentDB(**curr_conn)

            # set current tabs to the new db

            insts = [(i, self.nb.GetPageText(i)) for i in range(self.nb.GetPageCount())]

            for nbpage, name in insts:
                # print(' Get Page ', nbpage, name)
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
        try:
            self.configfile.write(config=self.config)
        except:
            pass
        pages = [self.nb.GetPage(i).instname for i in range(self.nb.GetPageCount())]
        for inst in self.db.get_all_instruments():
            show = 0
            display_order = len(pages) + 1
            if inst.name in pages:
                show = 1
                display_order = pages.index(inst.name)
            self.db.update('instrument', where={'name':inst.name},
                           show=show, display_order=display_order)

        self.db.set_hostpid(clear=True)
        self.admin_timer.Stop()
        self.init_timer.Stop()

        time.sleep(0.1)
        for name, pv in self.pvlist.pvs.items():
            try:
                pv.clear_callbacks()
                # pv = None
            except:
                pass
        time.sleep(0.10)

        self.pvlist.etimer.Stop()
        if self.epics_server is not None:
            self.epics_server.Shutdown()
        time.sleep(0.10)
        self.Destroy()


DEBUG = False
class EpicsInstrumentApp(wx.App, wx.lib.mixins.inspection.InspectionMixin):
    def __init__(self, prompt=False, configfile=None):
        self.prompt = prompt
        self.configfile = configfile
        wx.App.__init__(self)

    def OnInit(self):

        frame = InstrumentFrame(configfile=self.configfile, prompt=self.prompt)
        frame.Show()
        self.SetTopWindow(frame)
        if DEBUG:
            self.ShowInspectionTool()
        return True
