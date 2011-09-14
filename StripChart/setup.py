#!/usr/bin/env python

from distutils.core import setup, setup_keywords

deps = ('wx', 'epics', 'numpy', 'matplotlib')

setup(name = 'epicsapp_stripchart',
      version = '0.2',
      author = 'Matthew Newville',
      author_email = 'newville@cars.uchicago.edu',
      license = 'BSD',
      description = 'Epics PV Stripchart',
      package_dir = {'epicsapps.stripchart': 'lib',
                     'epicsapps': 'base'},
      packages = ['epicsapps', 'epicsapps.stripchart',
                  'epicsapps.stripchart.mplot'],
      data_files  = [('bin', ['pyepics_stripchart.py'])])


errmsg = 'WARNING: pyepics_stripchart requires Python module "%s"'
for mod in deps:
    try:
        a = __import__(mod)
    except ImportError:
        print errmsg % mod
