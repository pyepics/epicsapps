
from ..utils import ConfigFile

class InstrumentConfig(object):
    def __init__(self, name='instruments.yaml', default_config=None):
        if default_config is None:
            default_config = dict(server='sqlite', dbname=None, host=None,
                                  port='5432', user=None, password=None,
                                  recent_dbs=[])

        ConfigFile.__init__(self, fname, default_config=default_config)
