#!/usr/bin/env python
"""
  read log file column file
"""
import os
import io
import sys
import random
import time
import tomli
import yaml
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime
from multiprocessing import Process, Queue, Pool

from charset_normalizer import from_bytes
import numpy as np
from pyshortcuts import debugtimer


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
    mpldates: []
    value: []
    char_value: []
    events: []

    def __repr__(self):
        return f"PVLogData(pv='{self.pvname}', file='{self.filename}', npts={len(self.timestamp)})"




def unixts_to_mpldates(ts):
    "convert array of unix timestamps to MPL dates"
    ts = ts.astype('datetime64')
    dsecs = ts.astype('datetime64[s]')
    frac = (ts - dsecs).astype('timedelta64[ns]')
    out = (dsecs - np.datetime64(0, 's')).astype(np.float64)
    out += 1.e-9*frac.astype(np.float64)
    return out / 86400.0


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
    return parse_logfile(text, filename)

def parse_logfile(textlines, filename):
    dt = debugtimer()
    section = 'HEADER'
    times = []
    vals = []
    cvals = []
    headers = []
    events = []
    index = -1
    dt.add('x start')
    for line in textlines:
        line = line.strip()
        if len(line) < 1:
            continue
        if line.startswith('#'):
            headers.append(line)
        else:
            words = line.split(maxsplit=2)
            if len(words) == 1:
                continue
            if len(words) == 2:
                words.append(words[1])
            index += 1
            ts, val, cval = float(words[0]), words[1], words[2]
            times.append(ts)
            if val in ('<index>', '<event>'):
                vals.append(index)
                if val == '<event>':
                    events.append((ts, cval))
            else:
                try:
                    val = float(val)
                except ValueError:
                    pass
                vals.append(val)
            cvals.append(cval)
    dt.add(f'read 0 {filename}')
    datetimes = [datetime.fromtimestamp(ts) for ts in times]
    dt.add('datetime')
    mpldates =  unixts_to_mpldates(np.array(times))
    dt.add('mpl')
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
    dt.add('headers')
    pvname = attrs.pop('pvname')
    # dt.show()
    return PVLogData(pvname=pvname,
                     filename=fpath.name,
                     path=fpath.as_posix(),
                     header=headers,
                     attrs=attrs,
                     timestamp=times,
                     mpldates=mpldates,
                     datetime=datetimes,
                     value=vals,
                     char_value=cvals,
                     events=events)

def q_parse_logfile(text, filename, queue):
    queue.put(parse_logfile(text, filename))


def read_logfolder(folder):
    """read information for PVLOG folder
    this folder must have the following files
        _PVLOG.yaml (or _PVLOG.toml):
             main configuration, as used for collection
        _PVLOG_filelist.txt
             mapping PV names to logfile names

    returns
    --------
    PVLogFolder
    """
    return PVLogFolder(folder)


class PVLogFolder:
    """
    data and methods for a PVlogger Folder
    """
    def __init__(self, folder, workdir='', update_seconds=5):
        self.folder = Path(folder).resolve()
        self.fullpath = self.folder.as_posix()
        self.workdir = workdir
        self.update_seconds = update_seconds
        self.pvs = []
        self.motors = []
        self.instruments = []
        self.timestamps = {}
        self.data = {}
        if self.folder.exists():
            self.read_folder()

    def __repr__(self):
        return f"PVLogFolder('{self.fullpath}')"

    def read_folder(self):
        """read PVlogger information for PVLOG folder
        this folder must have the following files
            _PVLOG.yaml:  main configuration, as used for collection
            _PVLOG_filelist.txt:  mapping PV names to logfile names
        """
        if not self.folder.exists():
            raise ValueError(f"'{self.folder}' - does not exist")
        # list of logfiles
        filelist = Path(self.folder, '_PVLOG_filelist.txt')
        if not filelist.exists():
            raise ValueError(f"'{self.folder}' is not a valid PVlog folder: no file list")

        logfiles = {}
        for line in read_textfile(filelist).split('\n'):
            if line.startswith('#'):
                continue
            words = [a.strip() for a in line.split('|', maxsplit=1)]
            if len(words) > 1:
                logfiles[words[0]] = words[1]

        # main config
        form = 'yaml'
        cfile = Path(self.folder, '_PVLOG.yaml')
        if not cfile.exists():
            form = 'toml'
            cfile = Path(self.folder, '_PVLOG.toml')
            if not cfile.exists():
                raise ValueError(f"'{self.folder}' is not a valid PVlog folder: no config file")
        ctext = open(cfile, 'r').read()
        if form == 'yaml':
            conf = yaml.load(ctext, Loader=yaml.Loader)
        else:
            conf = tomli.loads(ctext)

        self.pvs = {}
        for pline in conf['pvs']:
            words = [a.strip() for a in pline.split('|', maxsplit=2)]
            if len(words) < 2:
               words.extend(['<auto>', '<auto>'])
            pvname = words[0]
            self.pvs[pvname] = (logfiles[pvname], words[1], words[2])

        self.folder = conf['folder']
        self.workdir = conf['workdir']
        self.update_seconds = float(conf['update_seconds'])
        self.motors = conf['motors']
        self.instruments = conf['instruments']

    def _logfiles_sizeorder(self, reverse=False):
        """return list of PVs ordered by increasing size of logfiles
        use 'reverse=False' to PVs ordered by decreasing size of logfiles.
        """
        pvlist = list(self.pvs)
        lfiles = [Path(self.folder, pvinfo[0]) for pvinfo in self.pvs.values()]
        sizes = [os.stat(name).st_size for name in lfiles]
        order = np.array(sizes).argsort()
        if reverse:
            order = order[::-1]
        return [pvlist[i] for i in order]

    def read_all_logfiles(self, nproc=4, verbose=False, writer=None):
        """read all PV logfiles, using multiprocessingx"""
        if verbose:
            print(f"Read log files with {nproc} processes")
        t0 = time.time()


        # this mixes small and large files
        alist = self._logfiles_sizeorder(reverse=True)
        print(len(alist))
        blist = self._logfiles_sizeorder(reverse=False)
        pvlist = []
        for a, b in  zip(alist, blist):
            if a not in pvlist:  pvlist.append(a)
            if b not in pvlist:  pvlist.append(b)

        print('# PVS: ', len(pvlist), pvlist[:5])
        procs = {}
        pdata = {}
        fsizes = {}
        maxsize = 0
        # first, read text from disk with 1 process
        # (avoid multiprocessed reading in parallel)
        # and set up processes to parse the text, which takes longes
        for i, pvname in enumerate(pvlist):
            pvinfo = self.pvs[pvname]
            logfile = Path('pvlog', pvinfo[0])
            text = read_textfile(logfile).split('\n')
            fsizes[pvname] = len(text)
            if len(text) > maxsize:
                maxsize = len(text)
            pdata[pvname] = {'data': None,
                              'text': text,
                              'logfile': logfile,
                              'status': 'pending',
                              'queue': None,
                              'proc': None,
                              'tstamp': os.stat(logfile).st_mtime}

        if verbose:
            npvs = len(pvlist)
            dt = time.time()-t0
            print(f"Read files for {npvs} PVs, {dt:.2f} secs, parsing...")

        # now run up to nproc processes to parse the text files
        def start_next_process(pvlist):
            for pvname in pvlist:
                pdat = pdata[pvname]
                if pdat['status'] == 'pending':
                    q = pdat['queue'] = Queue()
                    proc = Process(target=q_parse_logfile,
                                   args=(pdat['text'], pdat['logfile'], q))
                    pdat['proc'] = proc
                    proc.start()
                    pdat['status'] = 'started'
                    break

        for i in range(nproc):
            start_next_process(pvlist)

        iloop = 0
        while len(pvlist) > 0:
            iloop += 1
            nextpv = None
            _size = maxsize + 1
            work = []
            for pvname in pvlist:
                pdat = pdata[pvname]
                if pdat['status'] == 'started' and pdat['queue'] is not None:
                    xsize = fsizes[pvname]
                    work.append(pvname)
                    if xsize < _size:
                        _size = xsize
                        nextpv = pvname
            if nextpv is None or iloop % 2 == 0:
                nextpv = random.choice(work)

            pvname = nextpv
            pdat = pdata[pvname]
            self.data[pvname] = pdat['queue'].get()
            self.timestamps[pvname] = pdat['tstamp']
            pdat['proc'].join()
            pdat['queue'].close()
            del pdat['queue'], pdat['proc']
            pvlist.remove(pvname)
            pdat['status'] = 'complete'
            start_next_process(pvlist)

            if verbose and len(pvlist) > 0:
                npend, nstart = 0, 0
                for pvname in pvlist:
                    stat = pdata[pvname]['status']
                    if stat.startswith('pend'):
                        npend +=1
                    elif stat.startswith('start'):
                        nstart +=1
                print(f"{len(pvlist)} PVs remaining, {nstart} in progress")
        dt = time.time()-t0
        print(f"Parsed files for {npvs} PVs, {dt:.2f} secs")

    def find_newer_logfiles(self):
        """return a list of PVs with newer or uread logfiles"""
        new = []
        for pvname, pvinfo in self.pvs[pvname].items():
            logfile = Path('pvlog', pvinfo[0])
            tstamp = os.stat(logfile).st_mtime
            if tstamp > self.timestamps.get(pvname, -1):
                new.append(pvname)
        return new


    def read_logfile(self, pvname):
        """read logfile, save file timestamp"""
        if pvname not in self.pvs:
            raise ValueError(f"Unknown PV name: '{pvname}'")

        pvinfo = self.pvs[pvname]
        logfile = Path('pvlog', pvinfo[0])
        self.data[pvname] = read_logfile(logfile)
        self.timestamps[pvname] = os.stat(logfile).st_mtime
