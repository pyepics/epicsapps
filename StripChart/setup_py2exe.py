from distutils.core import setup
import py2exe
import epics
import matplotlib
matplotlib.use('WXAgg')

setup(name="Epics PV StripChart",
      data_files=matplotlib.get_py2exe_datafiles(),
      windows=[{'script': "EpicsStripchart.py",
                'icon_resources': [(0, 'stripchart.ico')]}],
      options = dict(py2exe=dict(optimize=1, bundle_files=1, 
                                 includes=['epics', 'ctypes', 'wx', 'numpy', 'matplotlib'],
                                 excludes=['Tkinter', '_tkinter', 'Tkconstants', 'tcl',
                                           '_imagingtk', 'PIL._imagingtk', 'ImageTk',
                                           'PIL.ImageTk', 'FixTk', '_gtkagg', '_tkagg'],
                                 dll_excludes=['libgdk-win32-2.0-0.dll',
                                               'libgobject-2.0-0.dll']),
                     )
      )
