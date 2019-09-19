import os
import yaml

from pyshortcuts.utils import get_homedir

def get_configfile(name='epicsapps.yaml', dirname=None):
    """
    get an epics app config file

    Arguments:
        name (str):  name of config file ['epicsapps.yaml']
        dirname (str or None): name of config folder [None]

    Returns:
        full path name of config file

    Notes:
        by default (with `dirname=None`), the config file will
        be assumeed to be in the folder
             $HOME/.config/epicsapps
    """
    condfir = dirname
    if confdir is None:
        confdir = os.path.join(get_homedir(), '.config', 'epicsasps')

    if not os.path.exists(confdir):
        try:
            os.makedirs(confdir)
        except FileExistsError:
            pass
    return os.path.join(confdir, name)
