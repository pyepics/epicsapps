#!/usr/bin/env python

from setuptools import setup

deps = ('wx', 'epics', 'numpy')
setup(name = 'epicsad_display',
      version = '0.2',
      author = 'Matthew Newville',
      author_email = 'newville@cars.uchicago.edu',
      license = 'BSD',
      description = 'Epics AreaDetector Viewer',
      packages = ['epicsad_display', 'epicsad_display.icons'],
      package_data={'epicsad_display': ['icons/*']},
      )
