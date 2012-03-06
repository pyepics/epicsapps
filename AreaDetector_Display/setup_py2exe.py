from distutils.core import setup
import py2exe
import epics

setup(name="Epics AD Display",
      windows=[{'script': 'EpicsAreaDetectorViewer.py',
                "icon_resources": [(0, "camera.ico")]}],
      options = dict(py2exe=dict(optimize=1, bundle_files=1, 
                                 includes=['epics', 'ctypes', 'wx', 'numpy', 'Image'],
                                 excludes=['Tkinter', '_tkinter', 'Tkconstants', 'tcl',
                                           '_imagingtk', 'PIL._imagingtk', 'ImageTk',
                                           'PIL.ImageTk', 'FixTk'],
                                 )
                     )
      )

