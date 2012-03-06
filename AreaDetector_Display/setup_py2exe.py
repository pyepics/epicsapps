from distutils.core import setup
import py2exe
import epics
import matplotlib
matplotlib.use('WXAgg')

setup(name="Epics AreaDetector Display",
      data_files=matplotlib.get_py2exe_datafiles(),
      windows=[{'script': 'pyepics_ad_display.py',
                "icon_resources": [(0, "camera.ico")]}],
      options = dict(py2exe=dict(optimize=1, bundle_files=2, 
                                 includes=['epics', 'ctypes', 'wx', 'numpy', 'Image'],
                                 excludes=['Tkinter', '_tkinter', 'Tkconstants', 'tcl',
                                           '_imagingtk', 'PIL._imagingtk', 'ImageTk',
                                           'PIL.ImageTk', 'FixTk'],
                                 )
                     )
      )

