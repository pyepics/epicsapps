#!/usr/bin/env python

from setuptools import setup, Extension

from Cython.Distutils import build_ext
import os

deps = ('wx', 'epics', 'sqlalchemy', 'numpy', 'Image')


if os.path.exists('C:/Program Files (x86)/Point Grey Research/FlyCapture2'):
    fc2_sdk = 'C:/Program Files (x86)/Point Grey Research/FlyCapture2'
else:
    fc2_sdk = 'C:/Program Files/Point Grey Research/FlyCapture2'


if os.path.exists(os.path.join(fc2_sdk, 'lib/C')):
    fc2_lib = os.path.join(fc2_sdk, 'lib/C')
elif os.path.exists(os.path.join(fc2_sdk, 'lib64/C')):
    fc2_lib = os.path.join(fc2_sdk, 'lib64/C')

fc2_inc = os.path.join(fc2_sdk, 'include')

print fc2_sdk
print fc2_lib
print fc2_inc

setup(name = 'epicsapp.gsemicro',
      version = '0.1',
      author = 'Matthew Newville',
      author_email = 'newville@cars.uchicago.edu',
      license = 'BSD',
      description = 'Epics GSEXRM Microscope/SampleStage Control',

      cmdclass = {'build_ext': build_ext},

      ext_modules = [Extension('pyfly2',
                               sources = ['src/pyfly2.pyx'],
                               include_dirs = ['src', fc2_inc],
                               extra_compile_args = [],
                               extra_link_args = [],
                               libraries = ['FlyCapture2_Cd_v90'],
                               library_dirs = [fc2_lib])],

      data_files = ['FlyCapture2_Cd_v90.dll', 'FlyCapture2d_v90.dll',
                    'libiomp5md.dll'],
      package_dir = {'epicsapps.gsemicro': 'gsemicro',
                     'epicsapps': 'base'},
      packages = ['epicsapps', 'epicsapps.gsemicro']



      )
