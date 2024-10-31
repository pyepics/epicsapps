#!/usr/bin/python
"""
Epics PV Logger Application, CLI no GUI
"""
import os
import time
from numpy import array, where
from functools import partial

from epics import get_pv
from epics.wx import EpicsFunction, DelayedEpicsCallback

from ..utils import (get_pvtypes, get_pvdesc, normalize_pvname, debugtimer)

from .configfile import (ConfigFile, get_configfolder,
                         get_default_configfile, load_yaml,
                         read_recents_file, write_recents_file)

SLEEPTME = 0.05
RUN_FOLDER = 'pvlog'

class PVLogger():
    about_msg =  """Epics PV Logger, CLI
 Matt Newville <newville@cars.uchicago.edu>
"""
    def __init__(self, configfile=None, prompt=None, wxparent=None):
        self.data = {}
        self.pvs = []
        self.wxparent = wxparent

        if configfile is not None:
            self.read_configfile(configfile, is_file=True)
        self.run()

    def read_configfile(self, configfile):
        print('read config file ', self.configfile)

    def connect_pvs(self):
        self.pvs

    def onChanges(self, pvname, value, char_value='', timestamp=0, **kws):
        self.data[pvname].append((value, char_value, timestamp))


    def run(self):
        self.connect_pvs()

        for pv in self.pvs:
            iv
