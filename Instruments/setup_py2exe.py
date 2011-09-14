from distutils.core import setup
import py2exe

setup(name="Python Instruments",
      windows=[{'script': 'pyepics_instruments.py', 'icon_resources': [(0, 'instrument.ico')]}],
      options = dict(py2exe=dict(optimize=0,
                                 includes=['epics', 'ctypes', 'wx', 'sqlalchemy'],
                                 )
                     )
      )

