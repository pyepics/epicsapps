import sys
import os
from optparse import OptionParser

from pyshortcuts import make_shortcut, platform

from .eiger_display import EigerApp

__version__ = '1.0'

def run_adeiger():
    '''
    command-line interface to running Eiger Display Application
    '''
    usage = 'Usage: eiger_display [options] DET_PREFIX'
    vers = 'eiger_display %s' % (__version__)

    parser = OptionParser(usage=usage, prog='eiger_display', version=vers)

    parser.add_option("-m", "--makeicons", dest="makeicons", action="store_true",
                      default=False, help="create desktop icons")

    (options, args) = parser.parse_args()

    print("options, args: ", options, args)
    # create desktop icons
    if options.makeicons:
        name = 'Eiger Display'
        script = 'eiger_display'
        icon_ext = 'ico'
        if platform.startswith('darwin'):
            icon_ext = 'icns'
        icon = "%s.%s" % ('eiger500k', icon_ext)
        bindir = 'bin'
        if platform.startswith('win'):
            bindir = 'Scripts'

        script = os.path.join(sys.prefix, bindir, script)
        icondir = os.path.join(__file__, 'icons')

        make_shortcut(script, name=name,
                      icon=os.path.join(icondir, icon),
                      terminal=True)
        print("Make Shortcut: ", script, icondir)
        if platform.startswith('linux'):
            os.chmod(script, 493)

    else:
        EigerApp(prefix=args[0])
