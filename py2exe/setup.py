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

def gen_style(title):
    if title.endswith('.py'):
        title = title[:-3]
    style = """
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">
  <assemblyIdentity  version="5.0.0.0"  processorArchitecture="x86"
    name="%s"  type="win32"  />
  <description>%s</description>
  <trustInfo xmlns="urn:schemas-microsoft-com:asm.v3">
    <security> <requestedPrivileges>
        <requestedExecutionLevel level="asInvoker"
            uiAccess="false"> </requestedExecutionLevel>
      </requestedPrivileges>
    </security>
  </trustInfo>
  <dependency> <dependentAssembly> <assemblyIdentity
     type="win32" name="Microsoft.VC90.CRT"
     version="9.0.21022.8" processorArchitecture="x86"
     publicKeyToken="1fc8b3b9a1e18e3b">
    </assemblyIdentity> </dependentAssembly>
  </dependency>
  <dependency> <dependentAssembly> <assemblyIdentity
    type="win32" name="Microsoft.Windows.Common-Controls"
    version="6.0.0.0" processorArchitecture="X86"
    publicKeyToken="6595b64144ccf1df" language="*"  />
    </dependentAssembly> </dependency> </assembly>
""" % (title, title)
    return style


apps = []
for script, iconfile in (('EpicsAreaDetectorViewer.py', 'camera.ico'),
                         ('EpicsStripchart.py',  'stripchart.ico'),
                         ('EpicsInstruments.py', 'instrument.ico'),
                         ('EpicsMotorSetup_SQLITE.py', 'motorapp.ico'),
                         ('EpicsMotorSetup_GSE.py', 'motorapp.ico'),
                         ):
    apps.append({'script': script,
                 'icon_resources': [(0, iconfile)],
                 'other_resources': [(24, 1, gen_style(script))]})
    extra_files.append(iconfile)

xsort = numpy.sort

include_mods = ['ConfigParser', 'Image', 'ctypes', 'epics',
                'epics.devices', 'fpformat', 'h5py', 'h5py._objects',
                'h5py._proxy', 'h5py.defs', 'h5py.utils', 'matplotlib',
                'numpy', 'scipy', 'scipy.constants', 'scipy.fftpack',
                'scipy.io.matlab.mio5_utils', 'scipy.io.matlab.streams',
                'scipy.io.netcdf', 'scipy.optimize', 'scipy.signal',
                'scipy.stats', 'skimage', 'skimage.exposure', 'sqlalchemy',
                'sqlalchemy.dialects.sqlite', 'sqlalchemy.orm',
                'sqlalchemy.pool', 'sqlite3', 'wx', 'wx._core', 'wx.lib',
                'wx.lib.*', 'wx.lib.agw', 'wx.lib.agw.flatnotebook',
                'wx.lib.agw.pycollapsiblepane', 'wx.lib.colourselect',
                'wx.lib.masked', 'wx.lib.mixins',
                'wx.lib.mixins.inspection', 'wx.lib.newevent', 'wx.py',
                'wxmplot', 'wxutils', 'wxversion', 'xdrlib', 'xml.etree',
                'xml.etree.cElementTree',]


py2exe_opts = {'optimize':1,
               'bundle_files':1,
               'includes': include_mods,
               'packages': ['h5py', 'scipy.optimize', 'scipy.signal', 'scipy.io',
                            'numpy.random', 'numpy.fft',
                            'xml.etree', 'xml.etree.cElementTree'], 
               'excludes': ['Tkinter', '_tkinter', 'Tkconstants', 'tcl',
                            '_imagingtk', 'PIL._imagingtk', 'ImageTk',
                            'PIL.ImageTk', 'FixTk''_gtkagg', '_tkagg',
                            'matplotlib.tests', 'qt', 'PyQt4Gui', 'IPython'],
               'dll_excludes': ['w9xpopen.exe',
                                'libgdk-win32-2.0-0.dll',
                                'libgobject-2.0-0.dll', 'libzmq.dll']
               }

# include matplotlib datafiles

setup(name = "Epics Applications",
      windows = apps,
      options = {'py2exe': py2exe_opts},
      data_files = mpl_data_files)
 
for fname in extra_files:
    shutil.copy(fname, os.path.join('dist', fname))
