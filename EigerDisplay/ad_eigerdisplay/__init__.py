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

    # create desktop icons
    if options.makeicons:
        name = 'Eiger Display'
        script = 'eiger_display'
        icon_ext = 'ico'
        if platform.startswith('darwin'):
            icon_ext = 'icns'

        bindir = 'bin'
        if platform.startswith('win'):
            bindir = 'Scripts'

        script = os.path.join(sys.prefix, bindir, script)
        topdir, _s = os.path.split(__file__)
        icon = os.path.join(topdir, 'icons', "%s.%s" % ('eiger500k', icon_ext))

        make_shortcut(script, name=name, icon=icon, terminal=True)
        if platform.startswith('linux'):
            os.chmod(script, 493)

    else:
        EigerApp(prefix=args[0]).MainLoop()
