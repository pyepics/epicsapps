from distutils.core import setup
import py2exe

setup(name="XRM Sample Stage", 
      windows=[{'script': "run_stage.py", 'icon_resources': [(0, 'micro.ico')]}],
      options = dict(py2exe=dict(optimize=0,
                                 includes=['epics', 'ctypes', 'wx'],
                                 excludes=['tcl', 'Tkinter', 'Tkconstants'])
                     ))

