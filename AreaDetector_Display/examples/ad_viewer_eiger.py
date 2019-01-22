#!/usr/bin/env python

from epicsad_display import areaDetectorApp

config_file = 'gse_eiger500.yaml'

areaDetectorApp(config_file).MainLoop()
