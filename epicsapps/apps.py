import os
import sys
import numpy
import time

from argparse import ArgumentParser, RawDescriptionHelpFormatter

from pyshortcuts import make_shortcut, platform
from pyshortcuts.utils import get_homedir
from pyshortcuts.shortcut import Shortcut

from .instruments import EpicsInstrumentApp
from .sampleviewer import ViewerApp as SampleViewerApp

HAS_CONDA = os.path.exists(os.path.join(sys.prefix, 'conda-meta'))

HAS_WXPYTHON = False
try:
    import wx
    HAS_WXPYTHON = True
except ImportError:
    pass

def use_mpl_wxagg():
    """import matplotlib, set backend to WXAgg"""
    if HAS_WXPYTHON:
        try:
            import matplotlib
            matplotlib.use('WXAgg', force=True)
            return True
        except ImportError:
            pass
    return False

here, _ = os.path.split(__file__)
icondir = os.path.join(here, 'icons')


def fix_darwin_shebang(script):
    """
    fix anaconda python apps on MacOs to launch with pythonw
    """
    pyapp = os.path.join(sys.prefix, 'python.app', 'Contents', 'MacOS', 'python')
    # strip off any arguments:
    script = script.split(' ', 1)[0]
    if not os.path.exists(script):
        script = os.path.join(sys.exec_prefix, 'bin', script)

    if platform == 'darwin' and os.path.exists(pyapp) and os.path.exists(script):
        with open(script, 'r') as fh:
            try:
                lines = fh.readlines()
            except IOError:
                lines = ['-']

        if len(lines) > 1:
            text = ["#!%s\n" % pyapp]
            text.extend(lines[1:])
            time.sleep(.05)
            with open(script, 'w') as fh:
                fh.write("".join(text))

class EpicsApp:
    """
    wrapper for Epics Application
    """
    def __init__(self, name, script, icon='epics', folder='Epics Apps', terminal=False):
        self.name = name
        self.script = script
        self.folder = folder
        icon_ext = 'ico'
        if platform == 'darwin':
            icon_ext = 'icns'
        self.icon = "%s.%s" % (icon, icon_ext)
        self.terminal = terminal
        bindir = 'bin'
        if platform == 'win':
            bindir = 'Scripts'

        self.bindir = os.path.join(sys.prefix, bindir)

    def create_shortcut(self):
        script =os.path.join(self.bindir, self.script)
        scut = make_shortcut(script, name=self.name,
                             icon=os.path.join(icondir, self.icon),
                             terminal=self.terminal,
                             folder=self.folder)

        if platform == 'linux':
            os.chmod(scut.target, 493)

        if platform == 'darwin' and HAS_CONDA:
            try:
                fix_darwin_shebang(script)
            except:
                print("Warning: could not fix Mac exe for ", script)

APPS = (EpicsApp('Instruments', 'epicsapp instruments', icon='instruments'),
        EpicsApp('Sample Viewer', 'epicsapp sampleviewer', icon='microscope'),
        EpicsApp('areaDetector Viewer', 'epicsapp adviewer', icon='camera'),
        EpicsApp('StripChart', 'epicsapp stripchart', icon='stripchart'))
# EpicsApp('Ion Chamber', 'epicsapp ionchamber', icon='ionchamber'))


# entry points:
def run_instruments(**kws):
    """Epics Instruments"""

    EpicsInstrumentApp(**kws).MainLoop()

def run_sampleviewer(inifile=None):
    """Sample Viewer"""
    ViewerApp(inifile=inifile).MainLoop()

## main cli wrapper
def run_epicsapps():
    """
    run PyEpics Applications
    """
    desc = 'run pyepics applications'
    epilog ='''applications:
  adviewer     [filename] Area Detector Viewer
  instruments  [filename] Epics Instruments
  sampleviewer [filename] Sample Microscope Viewer
  stripchart              Epics PV Stripchart

notes:
  applications with the optional filename will look for a yaml-formatted
  configuration file in the folder
      {:s}/.config/epicsapps
  or will prompt for configuration if this file is not found.
'''.format(get_homedir())
    parser = ArgumentParser(description=desc,
                            epilog=epilog,
                            formatter_class=RawDescriptionHelpFormatter)
    parser.add_argument('-m', '--makeicons',
                        dest='makeicons',
                        action='store_true',
                        default=False,
                        help='create desktop and start menu icons and quit')

    parser.add_argument('appname', nargs='?', help='application name')
    parser.add_argument('filename', nargs='?',
                        help='configuration filename')

    args = parser.parse_args()
    print(args)

    if args.appname is None and args.makeicons is False:
        parser.print_usage()

    # create desktop icons
    if args.makeicons:
        for app in APPS:
            app.create_shortcut()
        return
    use_mpl_wxagg()
    isapp = args.appname.lower().startswith
    if isapp('inst'):
        EpicsInstrumentApp().MainLoop()
    elif isapp('strip'):
        print("run Stripchart ")
    elif isapp('sample'):
        print("run Sample Viewer ", args.filename)
    elif isapp('ad'):
        print("run AD Viewer ", args.filename)
