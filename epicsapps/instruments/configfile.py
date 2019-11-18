import os
from ..utils import ConfigFile, get_default_configfile, get_configfolder
CONFFILE = 'instruments.yaml'

class InstrumentConfig(ConfigFile):
    def __init__(self, fname='instruments.yaml', default_config=None):
        if default_config is None:
            default_config = dict(server='sqlite', dbname=None, host=None,
                                  port='5432', user=None, password=None,
                                  recent_dbs=[])
        if fname is None:
            fname = os.path.join(get_configfolder(), CONFFILE)
       
        ConfigFile.__init__(self, fname, default_config=default_config)
