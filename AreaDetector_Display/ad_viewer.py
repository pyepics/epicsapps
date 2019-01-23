#!/usr/bin/env python

import sys
from optparse import OptionParser
from epicsad_display import areaDetectorApp

usage = "usage: %prog [options] config_file"
parser = OptionParser(usage=usage, prog="ad_display", version="0.1")

(options, args) = parser.parse_args()

configfile = None
if len(args) > 0:
    configfile = args[0]

areaDetectorApp(configfile=configfile).MainLoop()
