import os
import shutil
import time
from collections import namedtuple
import wx
import wx.lib.filebrowsebutton as filebrowse

import epics

from ..utils import normalize_pvname, get_pvdesc

from wxutils import (GridPanel, BitmapButton, FloatCtrl, FloatSpin,
                     FloatSpinWithPin, get_icon, SimpleText, Choice, YesNo,
                     SetTip, Check, Button, HLine, OkCancel, LCEN, RCEN,
                     pack)

FileBrowser = filebrowse.FileBrowseButtonWithHistory

ALL_EXP  = wx.ALL|wx.EXPAND
EIN_WILDCARD = 'Epics Instrument Files (*.ein)|*.ein|All files (*.*)|*.*'


def get_pvtypes(pvobj, instrument=None):
    """create tuple of choices for PV Type for database,
    which sets how to display PV entry.

    if pvobj is an epics.PV, the epics record type and
    pv.type are used to select the choices.

    if pvobj is an instrument.PV (ie, a db entry), the
    pvobj.pvtype.name field is used.
    """
    inst_pv = None
    if instrument is not None:
        inst_pv = instrument.PV

    choices = ['numeric', 'string']
    if isinstance(pvobj, epics.PV):
        prefix = pvobj.pvname
        suffix = None
        typename = pvobj.type
        if '.' in prefix:
            prefix, suffix = prefix.split('.')
        rectype = epics.caget("%s.RTYP" % prefix)
        if rectype == 'motor' and suffix in (None, 'VAL'):
            typename = 'motor'
        if pvobj.type == 'char' and pvobj.count > 1:
            typename = 'string'

    elif inst_pv is  not None and isinstance(pvobj, inst_pv):
        typename = str(pvobj.pvtype.name)

    # now we have typename: use as default, add alternate choices
    if typename == 'motor':
        choices = ['motor', 'numeric', 'string']
    elif typename in ('enum', 'time_enum'):
        choices = ['enum', 'numeric', 'string']
    elif typename in ('string', 'time_string'):
        choices = ['string', 'numeric']

    return tuple(choices)

def dumpsql(dbname, fname=None):
    """ dump SQL statements for an sqlite db"""
    if fname is None:
        fname =  '%s_dump.sql' % dbname
    os.system('echo .dump | sqlite3 %s > %s' % (dbname, fname))

def backup_versions(fname, max=5):
    """keep backups of a file -- up to 'max', in order"""
    if not os.path.exists(fname):
        return
    base, ext = os.path.splitext(fname)
    for i in range(max-1, 0, -1):
        fb0 = "%s_%i%s" % (base, i, ext)
        fb1 = "%s_%i%s" % (base, i+1, ext)
        if os.path.exists(fb0):
            try:
                shutil.move(fb0, fb1)
            except:
                pass
    try:
        shutil.move(fname, "%s_1%s" % (base, ext))
    except:
        pass


def save_backup(fname, outfile=None):
    """make a copy of fname"""
    if not os.path.exists(fname):
        return
    if outfile is None:
        base, ext = os.path.splitext(fname)
        outfile = "%s_BAK%s" % (base, ext)
    return shutil.copy(fname, outfile)

def set_font_with_children(widget, font, dsize=None):
    cfont = widget.GetFont()
    font.SetWeight(cfont.GetWeight())
    if dsize == None:
        dsize = font.PointSize - cfont.PointSize
    else:
        font.PointSize = cfont.PointSize + dsize
    widget.SetFont(font)
    for child in widget.GetChildren():
        set_font_with_children(child, font, dsize=dsize)

class GUIColors(object):
    def __init__(self):
        self.bg = wx.Colour(240,240,230)
        self.nb_active = wx.Colour(254,254,195)
        self.nb_area   = wx.Colour(250,250,245)
        self.nb_text = wx.Colour(10,10,180)
        self.nb_activetext = wx.Colour(80,10,10)
        self.title  = wx.Colour(80,10,10)
        self.pvname = wx.Colour(10,10,80)

class ConnectDialog(wx.Dialog):
    """
    Connect to a recent or existing DB File, or create a new one
    """
    msg = """Select Instruments SQLite File or Connect to PostgresQL DB"""
    def __init__(self, parent=None, dbname=None, server='sqlite',
                 user=None, password=None, host=None, port=5432,
                 recent_dbs=None, title='Select Instruments Database'):

        wx.Dialog.__init__(self, parent, wx.ID_ANY, size=(750, 450),
                           title=title)

        serverdef = 0 if server.startswith('sqlit') else 1

        self.server = Choice(self, choices=('SQLite', 'Postgresql'),
                             default=serverdef, size=(200, -1),
                             action=self.onServer)

        flist = []
        if recent_dbs is not None:
            for fname in recent_dbs:
                if os.path.exists(fname):
                    flist.append(fname)
        self.filebrowser = FileBrowser(self, size=(650, -1))
        self.filebrowser.SetHistory(flist)
        self.filebrowser.SetLabel('File:')
        self.filebrowser.fileMask = EIN_WILDCARD

        if len(flist) > 0:
            self.filebrowser.SetValue(flist[0])

        panel = GridPanel(self, ncols=5, nrows=6, pad=3,
                          itemstyle=wx.ALIGN_LEFT)

        panel.Add(SimpleText(self, ' Database Type:'), dcol=1, newrow=True)
        panel.Add(self.server, dcol=3)

        panel.Add(HLine(self, size=(400, -1)), dcol=5, newrow=True)

        panel.Add(SimpleText(self, ' SQLite database file'), dcol=2, newrow=True)
        panel.Add(self.filebrowser, dcol=3, newrow=True)

        panel.Add(HLine(self, size=(400, -1)), dcol=5, newrow=True)
        panel.Add(SimpleText(self, ' PostgresQL database connection'),
                  dcol=3, newrow=True)

        if dbname is None: dbname = ''
        if host in (None, ''):
            host = 'localhost'
        if port in (None, ''):
            port = '5432'
        if user is None:
            user = ''
        if password is None:
            password = ''
        self.dbname = wx.TextCtrl(self, -1, dbname, size=(300, -1))
        self.host = wx.TextCtrl(self, -1, host, size=(300, -1))
        self.port = wx.TextCtrl(self, -1, str(port), size=(300, -1))
        self.user = wx.TextCtrl(self, -1, user, size=(300, -1))
        self.password = wx.TextCtrl(self, -1, password, size=(300, -1),
                                    style=wx.TE_PASSWORD)

        panel.Add(SimpleText(self, ' Database Name:'), newrow=True)
        panel.Add(self.dbname)
        panel.Add(SimpleText(self, ' Host:'), newrow=True)
        panel.Add(self.host)
        panel.Add(SimpleText(self, ' Port:'), newrow=True)
        panel.Add(self.port)
        panel.Add(SimpleText(self, ' User:'), newrow=True)
        panel.Add(self.user)
        panel.Add(SimpleText(self, ' Password:'), newrow=True)
        panel.Add(self.password)

        btnsizer = wx.StdDialogButtonSizer()
        btnsizer.AddButton(wx.Button(self, wx.ID_OK))
        btnsizer.AddButton(wx.Button(self, wx.ID_CANCEL))
        btnsizer.Realize()

        panel.Add(HLine(self, size=(400, -1)), dcol=5, newrow=True)
        panel.Add(btnsizer, dcol=3, newrow=True)
        panel.pack()
        self.onServer()


    def onServer(self, event=None, server=None, **kws):
        if server is None:
            server = self.server.GetStringSelection().lower()

        is_pg = server.startswith('postgres')
        self.filebrowser.Enable(not is_pg)
        self.dbname.Enable(is_pg)
        self.host.Enable(is_pg)
        self.port.Enable(is_pg)
        self.user.Enable(is_pg)
        self.password.Enable(is_pg)

    def GetResponse(self, newname=None):
        self.Raise()
        response = namedtuple('dbconnect', ('ok', 'server',
                                            'dbname', 'host', 'port',
                                            'user', 'password'))
        ok = False
        server, dbname, host, port, user, password = ['']*6
        if self.ShowModal() == wx.ID_OK:
            ok = True
            server = self.server.GetStringSelection().lower()
            dbname = self.dbname.GetValue()
            if server.startswith('sqlite'):
                dbname = self.filebrowser.GetValue()
            else:
                host = self.host.GetValue()
                port = self.port.GetValue()
                user = self.user.GetValue()
                password = self.password.GetValue()

        return response(ok, server, dbname,
                        host, port, user, password)
