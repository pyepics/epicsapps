import os
import yaml
import time
import wx

import epics

def get_icon(iconname):
    topdir, _s = os.path.split(__file__)
    topdir, _s = os.path.split(topdir)
    if not iconname.endswith('.ico'):
        iconname = "%s.ico" % iconname
    return os.path.abspath(os.path.join(topdir, 'icons', iconname))


def normalize_pvname(pvname):
    pvname = str(pvname)
    if '.' not in pvname:
        pvname = '%s.VAL' % pvname
    return pvname

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

def get_pvdesc(pvname):
    desc = pref = pvname
    if '.' in pvname:
        pref = pvname[:pvname.find('.')]
    t0 = time.time()
    descpv = epics.get_pv(pref + '.DESC', form='native')
    if descpv.connect():
        desc = descpv.get()
    return desc


def SelectWorkdir(parent,  message='Select Working Folder...'):
    "prompt for and change into a working directory "
    dlg = wx.DirDialog(parent, message,
                       style=wx.DD_DEFAULT_STYLE|wx.DD_CHANGE_DIR)

    path = os.path.abspath(os.curdir)
    dlg.SetPath(path)
    if  dlg.ShowModal() == wx.ID_CANCEL:
        return None
    path = os.path.abspath(dlg.GetPath())
    dlg.Destroy()
    os.chdir(path)
    return path

class GUIColors(object):
    def __init__(self):
        self.bg = wx.Colour(250,250,240)
        self.nb_active = wx.Colour(254,254,195)
        self.nb_area   = wx.Colour(250,250,245)
        self.nb_text = wx.Colour(10,10,180)
        self.nb_activetext = wx.Colour(80,10,10)
        self.title  = wx.Colour(80,10,10)
        self.pvname = wx.Colour(10,10,80)
