#!/usr/bin/env python

from setuptools import setup, Extension

import os

deps = ('wx', 'epics', 'sqlalchemy', 'numpy', 'Image')

setup(name = 'epics_sampleviewer',
      version = '0.1',
      author = 'Matthew Newville',
      author_email = 'newville@cars.uchicago.edu',
      license = 'BSD',
      description = 'Epics Microscope/SampleStage Control',
      package_dir = {'epics_sampleviewer': 'lib'},
      packages = ['epics_sampleviewer']
      )
