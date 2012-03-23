from distutils.core import setup
import py2exe
import os
import shutil
import epics
# import Image
# import sqlalchemy
import matplotlib
ca = epics.ca.initialize_libca()
matplotlib.use('WXAgg')

extra_files = ['inno_setup.iss', 'license.txt', 'readme.txt']

apps = []
for script, iconfile in (('EpicsAreaDetectorViewer.py', 'camera.ico'),
                         ('EpicsStripchart.py',  'stripchart.ico'),
                         ('EpicsInstruments.py', 'instrument.ico'),
                         ('EpicsMotorSetup_SQLITE.py', 'motorapp.ico'),
                         ('EpicsMotorSetup_GSE.py', 'motorapp.ico'),
                         ):
    apps.append({'script': script, 'icon_resources': [(0, iconfile)]})
    extra_files.append(iconfile)

# pu2exe.org for options
py2exe_opts = {'optimize':1,
               'bundle_files':2,
               'includes': ['epics', 'ctypes', 'wx', 'ConfigParser',
                            'numpy', 'numpy.fft', 'numpy.random',
                            'Image', 'MySQLdb', 'sqlite3', 'sqlalchemy'],
               'packages': ['MySQLdb', 'sqlite3', 'sqlalchemy.dialects.mysql',
                            'sqlalchemy.dialects.sqlite', 'epics.ca'], 
               'excludes': ['Tkinter', '_tkinter', 'Tkconstants', 'tcl',
                            '_imagingtk', 'PIL._imagingtk', 'ImageTk',
                            'PIL.ImageTk', 'FixTk''_gtkagg', '_tkagg',
                            'qt', 'PyQt4Gui', 'Carbon', 'email'],
               'dll_excludes': ['libgdk-win32-2.0-0.dll',
                                'libgobject-2.0-0.dll']
               }

# include matplotlib datafiles
setup(name = "Epics Applications",
      windows = apps,
      options = {'py2exe': py2exe_opts},
      data_files = matplotlib.get_py2exe_datafiles(),
      )

for fname in extra_files:
    shutil.copy(fname, os.path.join('dist', fname))
