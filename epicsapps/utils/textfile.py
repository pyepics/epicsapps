"""
text file utilities
"""
import io
from pathlib import Path
from charset_normalizer import from_bytes

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


def read_textfile(filename, size=None):
    """read text from a file as string

    Argument
    --------
    filename  (str or file): name of file to read or file-like object
    size  (int or None): number of bytes to read

    Returns
    -------
    text of file as string.

    Notes
    ------
    1. the encoding is detected with charset_normalizer.from_bytes
       which is then used to decode bytes read from file.
    2. line endings are normalized to be '\n', so that
       splitting on '\n' will give a list of lines.
    3. if filename is given, it can be a gzip-compressed file
    """
    text = ''
    if isinstance(filename, bytes):
        filename = str(from_bytes(filename).best())
    if isinstance(filename, str):
        filename = Path(filename).absolute()
    if isinstance(filename, Path):
        filename = filename.as_posix()


    def decode(bytedata):
        return str(from_bytes(bytedata).best())

    if isinstance(filename, io.IOBase):
        text = filename.read(size)
        if filename.mode == 'rb':
            text = deco<de(text)
    else:
        with open(filename, 'rb') as fh:
            text = decode(fh.read(size))
    return text.replace('\r\n', '\n').replace('\r', '\n')
