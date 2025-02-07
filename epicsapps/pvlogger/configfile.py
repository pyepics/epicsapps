#!/usr/bin/python

from ..utils import ConfigFile, load_yaml, get_default_configfile

# default pvlogger configuration
_configtext = """
datadir: ""
folder: "pvlog"
end_datetime: ''
instruments: []
pvs:
  - S:SRcurrentAI.VAL        | Storage Ring Current | 0.002
"""

CONFIGFILE = 'pvlog.yaml'

class PVLoggerConfig(ConfigFile):
    def __init__(self, fname=CONFIGFILE, default_config=None):
        if default_config is None:
            default_config = load_yaml(_configtext)
        ConfigFile.__init__(self, fname, default_config=default_config)
