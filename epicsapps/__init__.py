#!/usr/bin/env python

from . import instruments, microscope, areadetector, stripchart
from .ionchamber import start_ionchamber
from .apps import run_epicsapps

from ._version import get_versions
__version__ = get_versions()['version']
del get_versions
