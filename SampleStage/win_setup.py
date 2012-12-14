from distutils.core import setup
import py2exe
import epics
ca = epics.ca.initialize_libca()

setup(name="XRM Sample Stage", 
      windows=[{'script': "run_stage.py", 'icon_resources': [(0, 'micro.ico')]}],
      options = dict(py2exe=dict(optimize=1,
                                 includes=['epics', 'ctypes', 'wx', 'Image'],
                                 excludes=['tcl', 'Tkinter', 'Tkconstants'])
                     ))

