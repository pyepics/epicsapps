import os
import sys
import time
sys.path += ['.']

import epics
# from epicsapps.samplestage import SampleStage, StageConfig
from lib import SampleStage, StageConfig

epics.ca.DEFAULT_CONNECTION_TIMEOUT = 2.0
epics.ca.initialize_libca()

## read default config file to pre-connect epics motors
## before the GUI is really going.
## this speeds up loading and can avoid unconnected PVs
# print SampleStage.CONFIG_DIR
configfile = os.path.join(SampleStage.CONFIG_DIR,
                          'SampleStage.ini')
# configfile = 'SampleStage.ini'
cnf = StageConfig(configfile)

stages = []
#print 'Connecting'
for pvname in cnf.config['stages']:
    stages.append(epics.Motor(name=pvname))


## fetch motor fields for the side-effect of actually
## making the network connection
[(s.DESC, s.VAL) for s in stages]

app = SampleStage.StageApp()
app.MainLoop()





