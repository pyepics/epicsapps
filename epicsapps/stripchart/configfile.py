#!/usr/bin/python

from ..utils import ConfigFile, load_yaml, get_default_configfile

_configtext = """
workdir: "/home/user"
pvs:
   - ['S:SRcurrentAI.VAL', 'Storage Ring Current']
"""

CONFFILE = 'stripchart.yaml'

class StripChartConfig(ConfigFile):
    def __init__(self, fname='stripchart.yaml', default_config=None):
        if default_config is None:
            default_config = load_yaml(_configtext)
        ConfigFile.__init__(self, fname, default_config=default_config)
