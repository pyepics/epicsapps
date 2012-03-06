from distutils.core import setup
import py2exe
import epics
a = epics.PV('13IDA:m1.VAL')

setup(name="Epics Instruments",
      windows=[{'script': 'EpicsInstruments.py',
                "icon_resources": [(0, "instrument.ico")]}],
      options = dict(py2exe=dict(optimize=1, bundle_files=2, 
                                 includes=['epics', 'ctypes', 'wx', 'sqlalchemy'],
                                 excludes=['Tkinter', '_tkinter', 'Tkconstants', 'tcl',
                                           '_imagingtk', 'PIL._imagingtk', 'ImageTk',
                                           'PIL.ImageTk', 'FixTk'],
                                 )
                     )
      )

