#!/usr/bin/env python

from distutils.core import setup, setup_keywords

deps = ('wx', 'epics', 'numpy', 'matplotlib')

setup(name = 'epicsapp_mcadisplay',
      version = '0.2',
      author = 'Matthew Newville',
      author_email = 'newville@cars.uchicago.edu',
      license = 'BSD',
      description = 'Epics MCA Display',
      package_dir = {'epicsapps.mcadisplay': 'lib',
                     'epicsapps': 'base'},
      packages = ['epicsapps', 'epicsapps.mcadisplay'],
      data_files  = [('bin', ['pyepics_mcadisplay.py'])])


errmsg = 'WARNING: pyepics_mcadisplay requires Python module "%s"'
for mod in deps:
    try:
        a = __import__(mod)
    except ImportError:
        print errmsg % mod
