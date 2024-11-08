#!/usr/bin/env python
"""
  read log file column file
"""
import os
import io
import sys
import time
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime

from charset_normalizer import from_bytes

import numpy as np


TINY = 1.e-7
MAX_FILESIZE = 400*1024*1024  # 400 Mb limit
COMMENTCHARS = '#;%*!$'

@dataclass
class PVLogData:
    pvname: str
    filename: str
    path: str
    header: []
    attrs: []
    timestamp: []
    datetime: []
    value: []
    char_value: []

    def __repr__(self):
        return f"PVLogData(pv='{self.pvname}', file='{self.filename}', npts={len(self.timestamp)})"

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
            text = decode(text)
    else:
        with open(filename, 'rb') as fh:
            text = decode(fh.read(size))
    return text.replace('\r\n', '\n').replace('\r', '\n')


def getfloats(txt):
    """convert a line of numbers into a list of floats,
    as for reading a file with columnar numerical data.

    Arguments
    ---------
      txt   (str) : line of text to parse

    Returns
    -------
      number of floats found, list with each entry as a float if possible

    """
    words = []
    nfloats = 0
    for word in txt.split():
        word = word.strip()
        try:
            word = float(word)
            nfloats += 1
        except ValueError:
            pass
        words.append(word)
    return nfloats, words

def read_logfile(filename):
    """read a PVlogger log file

    Arguments:
      filename (str):        name of file to read

    Returns:
      PVLogData dataclass instance

    """
    if not Path(filename).is_file():
        raise OSError("File not found: '%s'" % filename)
    if os.stat(filename).st_size > MAX_FILESIZE:
        raise OSError("File '%s' too big for read_ascii()" % filename)

    text = read_textfile(filename)
    lines = text.split('\n')

    ncol = None

    lines.reverse()
    section = 'DATA'
    times = []
    vals = []
    cvals = []
    headers = []

    for line in lines:
        line = line.strip()
        if len(line) < 1:
            continue
        # look for section transitions (going from bottom to top)
        nfloats, words = getfloats(line)
        if nfloats == 0:
            section = 'HEADER'

        if section == 'HEADER':
            headers.append(line)
        else:
            if len(words) > 3:
                words[2] = ' '.join(words[2:])
            times.append(words[0])
            vals.append(words[1])
            cvals.append(words[2])

    # reverse header, footer, data, convert to arrays
    for x in (headers, times, vals, cvals):
        x.reverse()

    datetimes = [datetime.fromtimestamp(ts) for ts in times]

    # try to parse attributes from header text
    fpath = Path(filename).absolute()
    attrs = {'filename': fpath.name, 'pvname': 'unknown'}

    for hline in headers:
        hline = hline.strip().replace('\t', ' ')
        if len(hline) < 1:
            continue
        if hline[0] in COMMENTCHARS:
            hline = hline[1:].strip()
        if '=' in hline:
            words = hline.split('=', 1)
            attrs[words[0].strip()] = words[1].strip()


    pvname = attrs.pop('pvname')

    return PVLogData(pvname=pvname,
                     filename=fpath.name,
                     path=fpath.as_posix(),
                     header=headers,
                     attrs=attrs,
                     timestamp=times,
                     datetime=datetimes,
                     value=vals,
                     char_value=cvals)
