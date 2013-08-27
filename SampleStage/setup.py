#!/usr/bin/env python

from distutils.core import setup

deps = ('wx', 'epics', 'sqlalchemy', 'numpy', 'Image')
setup(name = 'epicsapp.samplestage',
      version = '0.2',
      author = 'Matthew Newville',
      author_email = 'newville@cars.uchicago.edu',
      license = 'BSD',
      description = 'Epics SampleStage Control', 
      package_dir = {'epicsapps.samplestage': 'lib', 'epicsapps': 'base'},
      packages = ['epicsapps', 'epicsapps.samplestage'],
      data_files  = [('bin', ['pyepics_samplestage.py'])])


errmsg = 'WARNING: pyepics_samplestage requires Python module "%s"'

for mod in deps:
    try:
        a = __import__(mod)
    except ImportError:
        print errmsg % mod

