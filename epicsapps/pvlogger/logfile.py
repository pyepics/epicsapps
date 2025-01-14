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

class PVLogFile:
    """PV LogFile"""
    def __init__(self, pvname, logfile=None, description=None, monitor_delta=None,
                 mod_time=None, text=None, data=None):
        self.pvname = pvname
        self.logfile = logfile
        self.description = description
        self.monitor_delta = monitor_delta
        self.mod_time = mod_time
        self.text = text
        self.data = data

    def read_log_text(self, parse=False):
        """read text of logfile"""
        self.text = read_textfile(self.logfile).split('\n')
        self.mod_time = os.stat(self.logfile).st_mtime
        self.data = None
        if parse:
            self.data = parse_logfile(self.text, self.logfile)

    def parse(self):
        """parse text to data"""
        if len(self.text) > 5:
            self.data = parse_logfile(self.text, self.logfile)

    def get_datetimes(self):
        """set datetimes to list of datetimes"""
        self.data.datetimes = [datetime.fromtimestamp(ts) for ts in self.timestamp]

    def get_mpldates(self):
        """set matplotlib/numpy dates"""
        self.data.mpldates = unixts_to_mpldates(np.array(self.timestamp))


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
    datetimes = None # [datetime.fromtimestamp(ts) for ts in times]
    mpldates =  None # unixts_to_mpldates(np.array(times))
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
        self.pvs = {}
        self.motors = []
        self.instruments = []
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
                logfiles[words[0]] = Path(self.folder, words[1])

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
            logfile = logfiles[pvname]
            mod_time = os.stat(logfile).st_mtime
            self.pvs[pvname] = PVLogFile(pvname, logfile=logfile,
                                         mod_time=mod_time,
                                         description=words[1],
                                         monitor_delta=words[2])


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
        lfiles = [pv.logfile for pv in self.pvs.values()]
        sizes = [os.stat(name).st_size for name in lfiles]
        order = np.array(sizes).argsort()
        if reverse:
            order = order[::-1]
        return [pvlist[i] for i in order]

    def read_all_logs_text(self, verbose=False):
        """read text of all PV logfiles"""
        t0 = time.time()
        for pvname, pv in self.pvs.items():
            pv.text = read_textfile(pv.logfile).split('\n')
            pv.mod_time = os.stat(pv.logfile).st_mtime
            if verbose:
                print(f'{pvname} : {len(pv.text)}')
        if verbose:
            dt = time.time()-t0
            print(f"# read text for {len(self.pvs)} PVs, {dt:.2f} secs")


    def parse_logfiles(self, nproc=4, nmax=None, verbose=False):
        """parse all unparsed PV logfiles, using multiprocessing"""
        if verbose:
            print(f"parse log files with {nproc} processes")
        t0 = time.time()

        # files largest to smallest
        pdata = {}
        pvlist = []
        maxsize = 0
        for pvname in self.pvs:
            if self.pvs[pvname].data is None:
                pdata[pvname] = {'status': 'pending',
                                 'queue': None, 'proc': None}
                pvlist.append(pvname)

        random.shuffle(pvlist)
        if nmax is not None:
            pvlist = pvlist[:nmax]

        # now run up to nproc processes to parse the text files
        def start_next_process(pvlist):
            for pvname in pvlist:
                pdat = pdata[pvname]
                if pdat['status'] == 'pending':
                    q = pdat['queue'] = Queue()
                    args = (self.pvs[pvname].text, self.pvs[pvname].logfile, q)
                    proc = Process(target=q_parse_logfile, args=args)
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
            for pvn in pvlist:
                pdat = pdata[pvn]
                if (pdat['status'] == 'started' and
                    pdat['queue'] is not None):
                    xsize = len(self.pvs[pvn].text)
                    work.append(pvn)
                    if xsize < _size:
                        _size = xsize
                        nextpv = pvn
            if nextpv is None or iloop % 2 == 1:
                nextpv = random.choice(work)
            pvname = nextpv
            pdat = pdata[pvname]
            ret = None
            # print(f"# {len(pvlist)} PVs/{(time.time()-t0):.1f} sec, check on {pvname}" )
            try:
                ret = pdat['queue'].get(timeout=0.5)
            except:
                ret = None
            if ret is not None:
                self.pvs[pvname].data = ret

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
        if verbose:
            dt = time.time()-t0
            print(f"# parsed files for {len(pvlist)} PVs, {dt:.2f} secs")

    def reset_new_logfiles(self, parse_data=False):
        """find 'new' logfiles,  read the text, and set the
        data to None.

        if parse_data is True, the data will be parsed
        """
        for pvname, pv in self.pvs[pvname].items():
            mtime = os.stat(pv.logfile).st_mtime
            if mtime > pv.mod_time:
                pv.text = read_textfile(pv.logfile).split('\n')
                pv.mod_time = mtime
                pv.data = None
                if parse_data:
                    pv.data = parse_logfile(pv.text, pv.logfile)
        return new


    def read_logfile(self, pvname):
        """read logfile, save file timestamp"""
        pv = self.pvs.get(pvname, None)
        if pv is None:
            raise ValueError(f"Unknown PV name: '{pvname}'")
        pv.read_logfile()
        pv.data = read_logfile(pv.logfile)
        pv.mod_time = os.stat(pv.logfile).st_mtime
