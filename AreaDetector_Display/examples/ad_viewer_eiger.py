#!/usr/bin/env python

from epicsad_display import areaDetectorApp

config_file = 'ad_eiger.yaml'

areaDetectorApp(config_file).MainLoop()
