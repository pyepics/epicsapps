"""
text file utilities
"""
import io
from pathlib import Path
from pyshortcuts import read_textfile

def unixpath(d):
    if isinstance(d, bytes):
        d = str(from_bytes(d).best())
    if isinstance(d, str):
        d = Path(d).absolute()
    if isinstance(d, Path):
        return d.as_posix()
    raise ValueError(f"cannot get Path name from {d}")

def normalize_path(pstr, subs={'P:/': '/cars5/Users',
                               'T:/': '/cars6/Data'}):
    """normalize a string for a Path, including
    optional substitutions for mapped Windows drives
    """
    pstr = pstr.replace('\\', '/')
    for key, val in subs.items():
        if pstr.startswith(key):
            pstr = Path(val, pstr[len(key):]).as_posix()
    return unixpath(pstr)
