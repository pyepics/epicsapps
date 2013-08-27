#!/usr/bin/env python

from distutils.core import setup

deps = ('wx', 'epics', 'sqlalchemy')
setup(name = 'epicsapp.instruments',
      version = '0.2',
      author = 'Matthew Newville',
      author_email = 'newville@cars.uchicago.edu',
      license = 'BSD',
      description = 'Epics Instruments configuration and management',
      package_dir = {'epicsapps.instruments': 'lib', 'epicsapps': 'base'},
      packages = ['epicsapps', 'epicsapps.instruments'],
      data_files  = [('bin', ['pyepics_instruments.py'])])


errmsg = 'WARNING: pyepics_instruments requires Python module "%s"'

for mod in deps:
    try:
        a = __import__(mod)
    except ImportError:
        print errmsg % mod

