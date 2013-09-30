##
"""
Important note:
seeing errors in build with python setup.py py2exe?

move whole directory to a non-networked drive!


"""
##
from distutils.core import setup
# from setuptools import setup
import py2exe
import sys
import os
import shutil
import numpy
import scipy
import matplotlib
import h5py
import Image
import sqlalchemy
import wx
import ctypes
import ctypes.util

import scipy.io.netcdf
from scipy.io.netcdf import netcdf_file
import scipy.constants

loadlib =  ctypes.windll.LoadLibrary

# larch library bits...
from larch.larchlib import get_dll
cllib = get_dll('cldata')

# matplotlib, wxmplot
matplotlib.use('WXAgg')
mpl_data_files = matplotlib.get_py2exe_datafiles()
import wxmplot

# epics
import epics
ca = epics.ca.initialize_libca()

extra_files = ['inno_setup.iss', 'license.txt', 'readme.txt']

apps = []
for script, iconfile in (('EpicsAreaDetectorViewer.py', 'camera.ico'),
                         ('EpicsStripchart.py',  'stripchart.ico'),
                         ('EpicsInstruments.py', 'instrument.ico'),
                         ('EpicsMotorSetup_SQLITE.py', 'motorapp.ico'),
                         ('EpicsMotorSetup_GSE.py', 'motorapp.ico'),
                         ):
    apps.append({'script': script, 'icon_resources': [(0, iconfile)]})
    extra_files.append(iconfile)

xsort = numpy.sort

# pu2exe.org for options
xpy2exe_opts = {'optimize':1,
               'bundle_files':2,
               'includes': ['epics', 'ctypes', 'wx', 'ConfigParser',
                            'Image', 'MySQLdb', 'sqlite3', 'sqlalchemy'],
               'packages': ['MySQLdb', 'sqlite3', 'sqlalchemy.dialects.mysql',
                            'sqlalchemy.dialects.sqlite', 'epics.ca'], 
               'excludes': ['Tkinter', '_tkinter', 'Tkconstants', 'tcl',
                            '_imagingtk', 'PIL._imagingtk', 'ImageTk',
                            'PIL.ImageTk', 'FixTk''_gtkagg', '_tkagg',
                            'qt', 'PyQt4Gui', 'Carbon', 'email'],
               'dll_excludes': ['libgdk-win32-2.0-0.dll',
                                'libgobject-2.0-0.dll']
               }

py2exe_opts = {'optimize':1,
               'bundle_files':1,
               'includes': ['Image', 'ctypes', 'numpy', 'scipy',
                            'scipy.optimize', 'scipy.constants', 'scipy.stats',
                            'wx', 'wx._core', 'wx.py', 'wxversion',
                            'wx.lib', 'wx.lib.*', 'wx.lib.masked', 'wx.lib.mixins',
                            'wx.lib.colourselect', 'wx.lib.newevent',
                            'wx.lib.agw', 'wx.lib.agw.flatnotebook',
                            'h5py', 'h5py._objects', 'h5py.defs', 'h5py.utils', 'h5py._proxy',
                            'matplotlib', 'wxmplot',
                            'ConfigParser', 'fpformat',
                            'sqlalchemy', 'sqlalchemy.orm', 'sqlalchemy.pool',
                            'sqlite3', 'sqlalchemy.dialects.sqlite',
                            'xdrlib',  'epics', 'epics.devices'],
              
               'packages': ['h5py', 'scipy.optimize', 'scipy.signal', 'scipy.io',
                            'numpy.random', 'numpy.fft',
                            'xml.etree', 'xml.etree.cElementTree'], 
               'excludes': ['Tkinter', '_tkinter', 'Tkconstants', 'tcl',
                            '_imagingtk', 'PIL._imagingtk', 'ImageTk',
                            'PIL.ImageTk', 'FixTk''_gtkagg', '_tkagg',
                            'matplotlib.tests', 'qt', 'PyQt4Gui', 'IPython'],

               'dll_excludes': ['libgdk-win32-2.0-0.dll',
                                'libgobject-2.0-0.dll', 'libzmq.dll']
               }

# include matplotlib datafiles


setup(name = "Epics Applications",
      windows = apps,
      options = {'py2exe': py2exe_opts},
      data_files = mpl_data_files)
 
for fname in extra_files:
    shutil.copy(fname, os.path.join('dist', fname))
