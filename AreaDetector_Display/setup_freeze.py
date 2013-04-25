"""
setup.py script for cx_Freeze

Usage:
    python setup_freeze.py bdist_mac --bundle-iconfile=cameras.icns
    cp cameras.icns build/GSE.../Contents/Resources/.
    cp dlls/*.dylib builf/GSE.../Contents/MacOS/.
"""

from cx_Freeze import setup, Executable

import wx
import matplotlib
matplotlib.use('WXAgg')
import Image
import numpy
import wxmplot
from wxmplot.plotframe import PlotFrame
import epics
import Carbon

libca = epics.ca.initialize_libca()

DATA_FILES = []
exe_opts = {'includes': ['epics', 'wx', 'matplotlib', 
                         'Image', 'ctypes', 'numpy', 'Carbon.Appearance'],
           'excludes': ['Tkinter', '_tkinter', 'Tkconstants', 'tcl',
           '_imagingtk', 'PIL._imagingtk', 'ImageTk',
        'PIL.ImageTk', 'FixTk''_gtkagg', '_tkagg',
        'qt', 'PyQt4Gui', 'email'],
        }

setup(name='GSE Microscope',
      version =1.0,
      description = "GSECARS XRM Microscope Control", 
      options = {'build_exe': exe_opts},
      executables = [Executable('MicroscopeDisplay.py', base=None)])

