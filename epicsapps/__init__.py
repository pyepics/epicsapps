#!/usr/bin/env python
from .apps import run_epicsapps

from ._version import get_versions
__version__ = get_versions()['version']
del get_versions

