import os
import sys
import numpy
import time

from argparse import ArgumentParser, RawDescriptionHelpFormatter

from pyshortcuts import make_shortcut, platform
from pyshortcuts.utils import get_homedir

from .utils import get_configfolder

from .stripchart import StripChartApp
from .instruments import EpicsInstrumentApp
from .microscope import MicroscopeApp
from .areadetector import areaDetectorApp

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
        self.script = "epicsapps {}".format(script)
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
        script  = os.path.join(self.bindir, self.script)
        make_shortcut(script, name=self.name,
                      icon=os.path.join(icondir, self.icon),
                      terminal=self.terminal,
                      folder=self.folder)

        if platform == 'darwin' and HAS_CONDA:
            try:
                fix_darwin_shebang(script)
            except:
                print("Warning: could not fix Mac exe for ", script)

APPS = (EpicsApp('Instruments', 'instruments', icon='instrument'),
        EpicsApp('Sample Microscope', 'microscope', icon='microscope'),
        EpicsApp('areaDetector Viewer', 'adviewer', icon='camera'),
        EpicsApp('StripChart',       'stripchart', icon='stripchart'),
        )
# EpicsApp('Ion Chamber', 'epicsapp ionchamber', icon='ionchamber'))


def run_instruments(configfile=None, prompt=True):
    """Epics Instruments"""
    EpicsInstrumentApp(configfile=configfile, prompt=prompt).MainLoop()

def run_samplemicroscope(configfile=None, prompt=True):
    """Sample Microscope"""
    MicroscopeApp(configfile=configfile, prompt=prompt).MainLoop()

def run_adviewer(configfile=None, prompt=False):
    """AD Viewer"""
    areaDetectorApp(configfile=configfile, prompt=prompt).MainLoop()

def run_stripchart(configfile=None, prompt=False):
    """StripChart"""
    StripChartApp(configfile=configfile, prompt=prompt).MainLoop()

## main wrapper program
def run_epicsapps():
    """
    run PyEpics Applications
    """
    desc = 'run pyepics applications'
    epilog ='''applications:
  adviewer     [filename] Area Detector Viewer
  instruments  [filename] Epics Instruments
  microscope   [filename] Sample Microscope Viewer
  stripchart              Epics PV Stripchart

notes:
  applications with the optional filename will look for a yaml-formatted
  configuration file in the folder
      {:s}
  or will prompt for configuration if this file is not found.
'''.format(get_configfolder())
    parser = ArgumentParser(description=desc,
                            epilog=epilog,
                            formatter_class=RawDescriptionHelpFormatter)
    parser.add_argument('-m', '--makeicons', dest='makeicons',
                        action='store_true', default=False,
                        help='create desktop and start menu icons')
    parser.add_argument('-p', '--prompt', dest='prompt',
                        action='store_true', default=None,
                        help='prompt for configuration on startup')
    parser.add_argument('-n', '--no-prompt', dest='no_prompt',
                        action='store_true', default=False,
                        help='suppress prompt, use default configuration')


    parser.add_argument('appname', nargs='?', help='application name')
    parser.add_argument('filename', nargs='?', help='configuration file name')

    args = parser.parse_args()
    if args.appname is None and args.makeicons is False:
        parser.print_usage()
    elif args.makeicons:
        for app in APPS:
            app.create_shortcut()
    else:
        if args.filename is None and args.prompt is None:
            args.prompt = not args.no_prompt
        use_mpl_wxagg()
        isapp = args.appname.lower().startswith
        fapp = None
        if isapp('inst'):
            fapp = run_instruments
        if isapp('micro'):
            fapp = run_samplemicroscope
        elif isapp('strip'):
            fapp = run_stripchart
        elif isapp('adview'):
            fapp = run_adviewer
        if fapp is not None:
            fapp(configfile=args.filename, prompt=args.prompt)
