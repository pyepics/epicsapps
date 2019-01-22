#!/usr/bin/env python

import sys
from optparse import OptionParser
from epicsad_display import areaDetectorApp

usage = "usage: %prog [options] config_file"
parser = OptionParser(usage=usage, prog="ad_display", version="0.1")

(options, args) = parser.parse_args()

if len(args) < 1:
    print(usage)
    sys.exit()

config_file = args[0]

areaDetectorApp(config_file).MainLoop()
