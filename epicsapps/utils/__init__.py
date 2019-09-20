import os
import yaml

import wx

from pyshortcuts.utils import get_homedir

def get_configfile(name='epicsapps.yaml', dirname=None):
    """
    get an epics app config file

    Arguments:
        name (str):  name of config file ['epicsapps.yaml']
        dirname (str or None): name of config folder [None, see Note 2]

    Returns:
        full path name of config file

    Notes:
        1. if the config file is found either in the current folder,
           or if the full path is given, that will be returned.
        2. if dirname=None, it will be assumed to be
             $HOME/.config/epicsapps
    """
    confdir = dirname
    if confdir is None:
        confdir = os.path.join(get_homedir(), '.config', 'epicsasps')

    if not os.path.exists(confdir):
        try:
            os.makedirs(confdir)
        except FileExistsError:
            pass
    if not os.path.exists(name):
        name = os.path.join(confdir, name)
    print("configfile: ",os.path.abspath(name))
    return os.path.abspath(name)

def normalize_pvname(pvname):
    pvname = str(pvname)
    if '.' not in pvname:
        pvname = '%s.VAL' % pvname
    return pvname

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
