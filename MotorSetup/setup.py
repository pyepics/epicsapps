#!/usr/bin/env python

from distutils.core import setup, setup_keywords

deps = ('wx', 'epics', 'sqlalchemy')
setup(name = 'epicsapp_motorsetup',
      version = '0.2',
      author = 'Matthew Newville',
      author_email = 'newville@cars.uchicago.edu',
      license = 'BSD',
      description = 'Epics Motor Setup and management',
      package_dir = {'epicsapps.motorsetup': 'lib', 'epicsapps': 'base'},
      packages = ['epicsapps', 'epicsapps.motorsetup'],
      data_files  = [('bin', ['pyepics_motorsetup.py'])])


errmsg = 'WARNING: pyepics_motorsetup requires Python module "%s"'

for mod in deps:
    try:
        a = __import__(mod)
    except ImportError:
        print errmsg % mod

