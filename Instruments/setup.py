#!/usr/bin/env python

from distutils.core import setup, setup_keywords

setup(name = 'epicsapp_instruments',
      version = '0.2',
      author = 'Matthew Newville',
      author_email = 'newville@cars.uchicago.edu',
      license = 'BSD',
      description = 'Epics Instruments configuration and management',
      package_dir = {'epicsapps.instruments': 'lib', 'epicsapps': 'base'},
      packages = ['epicsapps', 'epicsapps.instruments'],
      data_files  = [('bin', ['pyepics_instruments'])])

try:
    import wx
except ImportError:
    print 'WARNING:  pyepics_instruments requires wxPython'

try:
    import epics
except ImportError:
    print 'WARNING:  pyepics_instruments requires pyepics'

try:
    import sqlalchemy
except ImportError:
    print 'WARNING:  pyepics_instruments requires sqlachemy'

