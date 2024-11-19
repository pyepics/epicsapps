from .pvlogger import PVLogger
from ..utils import HAS_WXPYTHON

PVLoggerApp = None
if HAS_WXPYTHON:
    from .pvlogger_app import PVLoggerApp
