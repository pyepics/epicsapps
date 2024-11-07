#!/usr/bin/python

from ..utils import ConfigFile, load_yaml, get_default_configfile

# default pvlogger configuration
_configtext = """
folder: "pvlog"
update_seconds: 5
workdir: ""
instruments:
- SampleStage
- Small KB Mirror Stripes
pvs:
- S:SRcurrentAI.VAL        | Storage Ring Current
- RF-ACIS:FePermit:Sect1To35IdM.VAL | Shutter Permit
- S13ID:DSID:GapM.VAL      | ID Gap, ID-C/D
- S13ID:DSID:TaperGapM.VAL | ID Gap Taper, ID-C/D
- S13ID:USID:GapM.VAL      | ID Gap, ID-E
- S13ID:USID:TaperGapM.VAL | ID Gap Taper, ID-E

"""

CONFIGFILE = 'pvlogger.yaml'

class PVLoggerConfig(ConfigFile):
    def __init__(self, fname='areadetector.yaml', default_config=None):
        if default_config is None:
            default_config = load_yaml(_configtext)

        ConfigFile.__init__(self, fname, default_config=default_config)
