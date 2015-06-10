#!/usr/bin/env python

from setuptools import setup, Extension

import os

deps = ('wx', 'epics', 'sqlalchemy', 'numpy', 'Image')

setup(name = 'epicsapp.sampleviewer',
      version = '0.1',
      author = 'Matthew Newville',
      author_email = 'newville@cars.uchicago.edu',
      license = 'BSD',
      description = 'Epics Microscope/SampleStage Control',
      package_dir = {'epicsapps.sampleviewer': 'lib'},
      packages = ['epicsapps', 'epicsapps.sampleviewer']



      )
