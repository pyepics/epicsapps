import os
from pyshortcuts.utils import get_homedir

import yaml
from yaml import Loader, Dumper

def load_yaml(text):
    """very simple yaml loader"""
    return yaml.load(text, Loader=Loader)

def get_configfolder():
    """
    get an epicsapps config folder

    Returns:
        path name of config folder, typically $HOME/.config/epicsapps

    """
    escancred = os.environ.get('ESCAN_CREDENTIALS', None)
    if escancred is not None:
        confdir, _ = os.path.split(escancred)
    else:
        confdir = os.path.join(get_homedir(), '.config', 'epicsapps')

        if not os.path.exists(confdir):
            try:
                os.makedirs(confdir)
            except FileExistsError:
                pass
    return confdir

def get_default_configfile(fname):
    """get the default configfile, if it exists or None if it does not"""
    out = os.path.join(get_configfolder(), fname)
    if os.path.exists(out):
        return out
    return None

def read_recents_file(fname='recent_ad_pvs.txt'):
    fname = os.path.join(get_configfolder(), fname)
    lines = ['#']
    out = []
    if os.path.exists(fname):
        with open(fname, 'r') as fh:
            lines = fh.readlines()
    for line in lines:
        if not line.startswith('#') and len(line) > 2:
            out.append(line[:-1])
    return out

def write_recents_file(fname='recent_ad_pvs.txt', nlist=None):
    if nlist is not None and len(nlist) > 0:
        fname = os.path.join(get_configfolder(), fname)
        with open(fname, 'w') as fh:
            fh.write('\n'.join(nlist))

class ConfigFile(object):
    """
    Configuration File, using YAML
    The ConfigFile will have attributes / methods:

    config:          dict of configuration data
    default_config:  factory default configuration data
    filename:         name of config file
    reset_default():  set config to factory default
    read(fname):     read config from file
    write(fname=None, config=None):  write config to file

    """
    def __init__(self, fname, default_config=None):
        self.filename = fname
        self.default_config = {}
        self.default_configfile = os.path.join(get_configfolder(), fname)
        if default_config is not None:
            self.default_config.update(default_config)

        self.config = {}
        self.config.update(self.default_config)
        if fname is not None:
            self.read(fname)

    def reset_default(self):
        """reset config to initial / factory default"""
        self.config = {}
        self.config.update(self.default_config)

    def read(self, fname):
        """read config file

        Arguments:
            fname (str):  name of configuration file

        Notes:
           1. if the file is found in the current working folder or because the
              full path is given, that file will be read.
           2. if the file is not found, but a file with that name is found in
              the default configuration folder ($HOME/.config/epicsapps), that
              file will be read.

        """
        if not os.path.exists(fname):
            tmp = os.path.join(get_configfolder(), fname)
            if os.path.exists(tmp):
                fname = tmp
            elif os.path.exists(self.default_configfile):
                fname = self.default_configfile
            else:
                print("No config file to read: ", fname)
                return

        self.filename = os.path.abspath(fname)

        text = None
        with open(self.filename, 'r') as fh:
            text = fh.read()
        self.config = yaml.load(text, Loader=Loader)


    def write(self, fname=None, config=None):
        if fname is None:
            fname = self.filename

        if config is None:
            config = self.config

        with open(fname, 'w') as fh:
            yaml.dump(config, fh, default_flow_style=None)
