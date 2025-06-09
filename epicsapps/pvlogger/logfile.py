#!/usr/bin/env python
"""
  read log file column file
"""
import os
import sys
import random
import time
import tomli
import yaml
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime, timezone
from dateutil import parser as dateparser
import pytz
from multiprocessing import Process, Queue, Pool
from matplotlib.dates import date2num
import numpy as np
from pyshortcuts import debugtimer

from ..utils.textfile import read_textfile
from .pvlogger import TIMESTAMP_FILE, motor_fields

TINY = 1.e-7
MAX_FILESIZE = 400*1024*1024  # 400 Mb limit
COMMENTCHARS = '#;%*!$'


TZONE = str(datetime.now(timezone.utc).astimezone().tzinfo)
if os.environ.get('TZ', None) is not None:
    TZONE = pytz.timezone(os.environ.get('TZ', TZONE))

# The EPICS EPOCH starts at 1990, and may sometimes
# send 0 or EPIC2UNIX_EPOCH=631152000.0
MIN_TIMESTAMP = 1.0e9

def is_int(s):
    try:
        _ = int(s)
        return True
    except:
        return False

@dataclass
class PVLogData:
    pvname: str
    filename: str
    path: str
    is_numeric: bool
    headers: []
    attrs: []
    timestamps: []
    datetimes: []
    mpldates: []
    values: []
    char_values: []
    events: []

    def __repr__(self):
        return f"PVLogData(pv='{self.pvname}', file='{self.filename}', npts={len(self.timestamps)})"

    def get_datetimes(self):
        """set datetimes to list of datetimes"""
        if (self.datetimes is None or
            len(self.datetimes) < len(self.timestamps)):
            self.datetimes = [datetime.fromtimestamp(ts, tz=TZONE) for ts in self.timestamps]
        return self.datetimes

    def get_mpldates(self):
        """set matplotlib/numpy dates"""
        if (self.mpldates is None or
                len(self.mpldates) < len(self.timestamps)):
            self.mpldates = np.array(self.timestamps)/86400.0
        return self.mpldates

class PVLogFile:
    """PV LogFile"""
    def __init__(self, pvname, logfile=None, description=None, monitor_delta=None,
                 mod_time=None, text=None, data=None):
        self.pvname = pvname
        self.logfile = logfile
        self.description = description
        self.monitor_delta = monitor_delta
        self.mod_time = mod_time
        self.has_motor_events = False
        self.text = text
        self.data = data

    def read_log_text(self, parse=False):
        """read text of logfile"""
        self.text = read_textfile(self.logfile).split('\n')
        self.mod_time = os.stat(self.logfile).st_mtime
        self.data = None
        if parse and len(self.text) > 3:
            self.parse()

    def parse(self):
        """parse text to data"""
        self.data = parse_logfile(self.text, self.logfile)
        self.has_motor_events = False

    def get_datetimes(self):
        """set datetimes to list of datetimes"""
        return self.data.get_datetimes()

    def get_mpldates(self):
        """set matplotlib/numpy dates"""
        return self.data.get_mpldates()

    def set_end_time(self, tstamp):
        last_time = self.data.timestamps[-1]
        if tstamp > (last_time + 0.001):
            self.data.values.append(self.data.values[-1])
            self.data.char_values.append(self.data.char_values[-1])
            self.data.timestamps.append(tstamp)
            self.get_mpldates()

def read_logfile(filename):
    """read a PVlogger log file

    Arguments:
      filename (str):  name of file to read

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
    return parse_logfile(lines, filename)

def parse_logfile(textlines, filename):
    dt = debugtimer()
    section = 'HEADER'
    times = []
    vals = []
    cvals = []
    headers = []
    events = []
    index = -1
    val_index = 0
    start_tstamp = MIN_TIMESTAMP
    for line in textlines:
        line = line.strip()
        if len(line) < 1:
            continue
        if line.startswith('#'):
            headers.append(line)
            if 'start_time' in line:
                words = [a.strip() for a in line[1:].split('=')]
                start_tstamp = dateparser.parse(words[1]).timestamp()
        else:
            words = line.split(maxsplit=2)
            if len(words) == 1:
                continue
            if len(words) == 2:
                words.append(words[1])
            index += 1
            ts, val, cval = float(words[0]), words[1], words[2]
            if ts < MIN_TIMESTAMP:
                if len(times) < 1:
                    ts = start_tstamp
                else:
                    ts = times[-1]
            if val == '<event>':
                events.append([ts, cval])
            else:
                if val in ('<index>', '<non_numeric>'):
                    val_index  += 1
                    vals.append(index)
                    cvals.append(cval)
                    times.append(ts)
                else:
                    try:
                        val = float(val)
                        vals.append(val)
                        cvals.append(cval)
                        times.append(ts)
                    except ValueError:
                        events.append((ts, cval))

    dt.add(f'read 0 {filename}')
    datetimes = None #
    mpldates =  None #
    # try to parse attributes from header text
    fpath = Path(filename).absolute()
    attrs = {'filename': fpath.name, 'pvname': 'unknown', 'type': 'time_double'}
    enum_strs = {}
    enum_mode = False
    for hline in headers:
        hline = hline.strip().replace('\t', ' ')
        if len(hline) < 1:
            continue
        if hline[0] in COMMENTCHARS:
            hline = hline[1:].strip()
        if '-----' in hline:
            break
        if '=' in hline:
            words = hline.split('=', 1)
            if enum_mode:
                enum_strs[int(words[0].strip())] = words[1].strip()
            else:
                attrs[words[0].strip()] = words[1].strip()
        if 'enum strings' in hline:
            enum_mode = True
    if 'enum' in attrs['type'] and len(enum_strs) > 0:
        attrs['enum_strs'] = enum_strs

    pvname = attrs.pop('pvname')
    npts = (len(vals) + len(events))
    is_numeric = (val_index < 0.8*npts)
    return PVLogData(pvname=pvname,
                     filename=fpath.name,
                     is_numeric=is_numeric,
                     path=fpath.as_posix(),
                     headers=headers,
                     attrs=attrs,
                     timestamps=times,
                     mpldates=mpldates,
                     datetimes=datetimes,
                     values=vals,
                     char_values=cvals,
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
    def __init__(self, folder, datadir='', **kws):
        self.folder = Path(folder).resolve()
        self.fullpath = self.folder.as_posix()
        self.datadir = Path(datadir)

        self.time_start = None
        self.time_stop = None
        self.kws = kws
        self.pvs = {}
        self.motors = []
        self.instruments = []
        self.on_read = None
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
        filelist = Path(self.folder, '_PVLOG_filelist.txt').absolute()
        if not filelist.exists():
            raise ValueError(f"'{self.folder}' is not a valid PVlog folder: no file list")

        logfiles = {}
        for line in read_textfile(filelist).split('\n'):
            if line.startswith('#'):
                continue
            words = [a.strip() for a in line.split('|', maxsplit=1)]
            if len(words) > 1:
                logfiles[words[0]] = Path(self.folder, words[1])
        self.logfiles = logfiles

        # main config
        form = 'yaml'
        cfile = Path(self.folder, '_PVLOG.yaml')
        if not cfile.exists():
            form = 'toml'
            cfile = Path(self.folder, '_PVLOG.toml')
            if not cfile.exists():
                raise ValueError(f"'{self.folder}' is not a valid PVlog folder: no config file")
        ctext = open(cfile, 'r', encoding='utf-8').read()
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

        self.motors = conf['motors']
        # look for extra instrumens, as added during/after collection
        conf['extra_instruments'] = {}
        xin_file = Path(self.folder, '_PVLOG_instruments.txt')
        if xin_file.exists():
            with open(xin_file, 'r', encoding='utf-8') as fh:
                xtext = fh.read()
            xconf = yaml.load(xtext, Loader=yaml.Loader)
            conf['instruments'].update(xconf)
        self.instruments = conf['instruments']

        # determine start and stop time
        start_time, stop_time = 0, 0
        tstamp_file = Path(self.folder, TIMESTAMP_FILE)
        if tstamp_file.exists():
            with open(tstamp_file, 'r', encoding='utf-8') as fh:
                line = fh.readline()
                words = line.split()
                stop_time = float(words[0])
        self.time_stop = stop_time

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
            ts = None
            try:
                last_line = pv.text[-1]
                if not last_line.startswith('#'):
                    words = last_line[-1].split()
                    if len(words) > 0:
                        ts = float(words[0])
            except:
                pass
            if ts is not None:
                self.time_stop = ts
            if verbose:
                print(f'{pvname} : {len(pv.text)}')
        if verbose:
            dt = time.time()-t0
            print(f"#read {len(self.pvs)} log files, {dt:.2f} secs")


    def parse_logfiles(self, nproc=4, nmax=None, verbose=False):
        """parse all unparsed PV logfiles, using multiprocessing"""
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

        npvs = len(pvlist)
        if self.on_read is not None:
            self.on_read(pvname='Reading PVs', npvs=npvs, nproc=nproc)

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
        data_start_time = None
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
            try:
                ret = pdat['queue'].get(timeout=0.5)
            except:
                ret = None
            if ret is not None:
                self.pvs[pvname].data = ret
                pdat['proc'].join()
                pdat['queue'].close()
                del pdat['queue'], pdat['proc']
                stime = ret.attrs.get('start_time',  None)
                if stime is not None:
                    start_tstamp = dateparser.parse(stime).timestamp()
                    if data_start_time is None:
                        data_start_time = start_tstamp
                    else:
                        data_start_time = min(data_start_time, start_tstamp)
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
                if data_start_time != self.time_start:
                    self.time_start = data_start_time
                if self.on_read is not None:
                    self.on_read(npvs=len(pvlist), nstart=nstart, pvname=pvname,
                                  nproc=nproc, tstart=self.time_start)
        if verbose:
            dt = time.time()-t0
            print(f"# parsed {npvs} Log files: {dt:.2f} secs")

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
        pv.read_log_text(parse=True)
        pv.mod_time = os.stat(pv.logfile).st_mtime
        if pvname in self.motors:
            self.read_motor_events(pvname)

    def read_motor_events(self, motorname):
        """read Motor Events for motor PVs
        This will convert the data for the logged "Motor Fields" for a Motor PV
        ('.OFF', '.FOFF', '.SET', '.HLS', '.LLS', '.DIR', '_able.VAL', '.SPMG')
        into entries in the "events" list for the Motor data.

       Event data is a list of (timestamp, string) values, and so look like:
           [(1734109257.422, 'FOFF = Frozen'),
            (1734109257.422, 'SET = Use'), ...]
        """
        if motorname in self.motors:
            pv = self.pvs[motorname]
            if pv.data is None:
                pv.read_log_text(parse=True)
            root = motorname[:-4]
            # print('read motor init events ',pv.data.events)
            if pv.has_motor_events and len(pv.data.events) > 7:
                return

            for suff in motor_fields:
                pvname = f'{root}{suff}'
                label = suff[1:]
                if pvname in self.logfiles:
                    pvdat = read_logfile(self.logfiles[pvname])
                    dtype = pvdat.attrs['type']
                    enumstrs = pvdat.attrs.get('enum_strs', None)
                    for ts, val, cval in zip(pvdat.timestamps, pvdat.values,
                                            pvdat.char_values):
                        if 'enum' in dtype and enumstrs is not None:
                            cval = enumstrs.get(val, cval)
                        pv.data.events.append((ts, f'{label} = {cval}'))
            pv.data.events = sorted(pv.data.events, key=lambda x: x[0])
            pv.has_motor_events = True
