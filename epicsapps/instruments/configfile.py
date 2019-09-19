import os
import yaml

from ..utils import get_configfile

from yaml import load, dump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper


_config = {'dbs': ['EpicsInstruments.ein']}

class InstrumentConfig(object):
    def __init__(self, name='instruments.yaml'):
        self.config = _config
        self.config_file = None
        self.read(name)

    def read(self):
        cfile = get_configfile(name)
        if os.path.exists(cfile):
            self.config_file = cfile
            text = None
            with open(cfile, 'r') as fh:
                text = fh.read()
            try:
                self.config = yaml.load(text, Loader=Loader)
            except:
                pass

    def write(self, fname=None):
        if fname is None:
            fname = self.config_file
        with open(fname, 'w') as fh:
            fh.write(yaml.dump(self.config))
