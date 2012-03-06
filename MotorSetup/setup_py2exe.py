from distutils.core import setup
import py2exe
import epics
import sqlalchemy

setup(name="Epics MotorSetup",
      windows=[{'script': 'pyepics_motorsetup.py',
                "icon_resources": [(0, "motorapp.ico")]}],
      options = dict(py2exe=dict(optimize=1, bundle_files=1, 
                                 includes=['epics', 'ctypes', 'wx', 'MySQLdb', 'sqlalchemy'],
                                 excludes=['Tkinter', '_tkinter', 'Tkconstants', 'tcl',
                                           '_imagingtk', 'PIL._imagingtk', 'ImageTk',
                                           'PIL.ImageTk', 'FixTk'],
                                 )
                     )
      )

