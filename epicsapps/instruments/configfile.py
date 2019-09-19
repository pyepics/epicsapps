import os
import yaml

from ..utils import get_configfile

from yaml import load, dump
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper


_config = dict(server='sqlite', dbname=None, host=None, port='5432',
               user=None, password=None, recent_dbs=[])

class InstrumentConfig(object):
    def __init__(self, name='instruments.yaml'):
        self.config = _config
        self.read(name)

    def read(self, fname):
        self.config_file = get_configfile(fname)
        if os.path.exists(self.config_file):
            text = None
            with open(self.config_file, 'r') as fh:
                text = fh.read()
            try:
                self.config = yaml.load(text, Loader=Loader)
            except:
                pass

    def write(self, fname=None, config=None):
        if fname is None:
            fname = self.config_file
        if config is None:
            config = self.config
        with open(fname, 'w') as fh:
            fh.write(yaml.dump(config))
