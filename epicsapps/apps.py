import os
import sys
import numpy
import time
from pyshortcuts import make_shortcut, platform
from pyshortcuts.utils import get_homedir
from pyshortcuts.shortcut import Shortcut


HAS_CONDA = os.path.exists(os.path.join(sys.prefix, 'conda-meta'))

HAS_WXPYTHON = False
try:
    import wx
    HAS_WXPYTHON = True
except ImportError:
    pass

here, _ = os.path.split(__file__)
icondir = os.path.join(here, 'icons')

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

APPS = (EpicsApp('Instruments', 'instruments', icon='instruments'),
        EpicsApp('Sample Viewer', 'sampleviewer', icon='microscope'))
        # EpicsApp('EpicsApps', 'epicsapps', terminal=True, icon='epics'))


def make_desktop_shortcuts():
    """make desktop shortcuts for Epics Apps"""
    for app in APPS:
        app.create_shortcut()

# entry points:
def run_instruments(**kws):
    """Epics Instruments"""
    use_mpl_wxagg()
    from .instruments import EpicsInstrumentApp
    EpicsInstrumentApp(**kws).MainLoop()

def run_sampleviewer(inifile=None):
    """Sample Viewer"""
    use_mpl_wxagg()
    from .sampleviewer import ViewerApp
    ViewerApp(inifile=inifile).MainLoop()

## main cli wrapper
def run_epicsapps():
    """
    main desktop shortcuts for EpicsApps
    """
    make_desktop_shortcuts()
