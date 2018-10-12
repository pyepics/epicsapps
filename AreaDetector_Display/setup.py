#!/usr/bin/env python

from distutils.core import setup, setup_keywords

deps = ('wx', 'epics', 'numpy', 'Image')
setup(name = 'epicsapp_ad_display',
      version = '0.2',
      author = 'Matthew Newville',
      author_email = 'newville@cars.uchicago.edu',
      license = 'BSD',
      description = 'Epics AreaDetector Viewer',
      package_dir = {'epicsapps.ad_display': 'lib', 'epicsapps': 'base'},
      packages = ['epicsapps', 'epicsapps.ad_display'],
      data_files  = [('bin', ['pyepics_ad_display.py'])])


errmsg = 'WARNING: pyepics_ad_display requires Python module "%s"'

for mod in deps:
    try:
        a = __import__(mod)
    except ImportError:
        print(errmsg % mod)
