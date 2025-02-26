import os
import sys
import numpy
import time

from argparse import ArgumentParser, RawDescriptionHelpFormatter

from pyshortcuts import make_shortcut, platform
from pyshortcuts.utils import get_homedir

from .utils import get_configfolder, HAS_WXPYTHON

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

APPS = (EpicsApp('Instruments', 'instruments', icon='instrument'),
        EpicsApp('Sample Microscope', 'microscope', icon='microscope'),
        EpicsApp('areaDetector Viewer', 'adviewer', icon='areadetector'),
        EpicsApp('StripChart',       'stripchart', icon='stripchart'),
        EpicsApp('PVLogger',         'pvlogviewer', icon='logging'),
        )

# EpicsApp('Ion Chamber', 'epicsapp ionchamber', icon='ionchamber'))

def run_instruments(configfile=None, prompt=True):
    """Epics Instruments"""
    from .instruments import EpicsInstrumentApp
    EpicsInstrumentApp(configfile=configfile, prompt=prompt).MainLoop()

def run_samplemicroscope(configfile=None, prompt=True):
    """Sample Microscope"""
    from .microscope import MicroscopeApp
    MicroscopeApp(configfile=configfile, prompt=prompt).MainLoop()

def run_adviewer(configfile=None, prompt=True):
    """AD Viewer"""
    from .areadetector import areaDetectorApp
    areaDetectorApp(configfile=configfile, prompt=prompt).MainLoop()

def run_stripchart(configfile=None, prompt=False):
    """StripChart"""
    from .stripchart import StripChartApp
    StripChartApp(configfile=configfile, prompt=prompt).MainLoop()

def run_pvlogger(configfile=None, prompt=False, **kws):
    """PV Logger Command Line App"""
    from .pvlogger import PVLogger
    if configfile is not None:
        PVLogger(configfile=configfile, prompt=prompt).run()
    else:
        run_pvlogviewer(prompt=prompt)

def run_pvlogviewer(prompt=False):
    """PV Logger"""
    from .pvlogger import PVLoggerApp
    PVLoggerApp(prompt=prompt).MainLoop()


## main wrapper program
def run_epicsapps():
    """
    run PyEpics Applications
    """
    desc = 'run pyepics applications'
    epilog ='''applications:
  adviewer     [filename] Area Detector Viewer
  instruments  [filename] Epics Instruments GUI
  microscope   [filename] Sample Microscope Viewer
  pvlogviewer             Epics PV Logger Viewer GUI
  stripchart              Epics PV Stripchart GUI
  pvlogger     [filenmae] Epics PV Logger data collection CLI

notes:
  applications with the optional filename will look for a yaml-formatted
  configuration file in the folder
      {:s}
  or will prompt for configuration file if one is not found.
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
    parser.add_argument('-c', '--cli', dest='use_cli',
                        action='store_true', default=False,
                        help='use Command-line interface, no GUI (pvlogger only)')
    parser.add_argument('appname', nargs='?', help='application name')
    parser.add_argument('filename', nargs='?', help='configuration file name')

    args = parser.parse_args()
    runner = None
    needs_help = False
    kwargs = {'configfile': args.filename}
    if args.appname is None and args.makeicons is False:
        needs_help = True
    elif args.makeicons:
        for app in APPS:
            app.create_shortcut()
    else:
        if args.filename is None and args.prompt is None:
            args.prompt = not args.no_prompt
        use_mpl_wxagg()
        isapp = args.appname.lower().startswith
        kwargs['prompt'] = args.prompt
        if isapp('inst'):
            runner = run_instruments
        elif isapp('micro'):
            runner = run_samplemicroscope
        elif isapp('strip'):
            runner = run_stripchart
        elif isapp('pvlogv'):
            runner= run_pvlogviewer
            kwargs = {}
        elif isapp('pvlog'):
            runner= run_pvlogger
            kwargs['use_cli'] = args.use_cli
        elif isapp('ad'):
            runner = run_adviewer
        else:
            needs_help = True
    if needs_help:
        parser.print_usage()
    elif runner is not None:
        runner(**kwargs)
