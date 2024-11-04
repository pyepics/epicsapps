from .pvlogger import PVLogger
from ..utils import HAS_WXPYTHON

PVLoggerApp = None
if HAS_WXPYTHON:
    x = 1
    #from .pvlogger_app import PVLoggerApp
