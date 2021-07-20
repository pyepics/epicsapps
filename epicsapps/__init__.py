#!/usr/bin/env python

from .ionchamber import start_ionchamber
try:
    from . import instruments, microscope, areadetector, stripchart
    from .apps import run_epicsapps
except:
    pass

from ._version import get_versions
__version__ = get_versions()['version']
del get_versions
