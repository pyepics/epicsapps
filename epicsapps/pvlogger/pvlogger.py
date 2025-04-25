#!/usr/bin/python
"""
Epics PV Logger Application, CLI no GUI
"""
import sys
import os
import atexit
import traceback
import uuid
import random
from time import time, sleep
from collections import deque
from pathlib import Path
from datetime import datetime, timedelta
from dateutil import parser as dateparser
import numpy as np
import yaml
from pyshortcuts import fix_filename, new_filename, isotime, gformat

from epics import get_pv, PV
from epics import ca
ca.WITH_CA_MESSAGES = True
ca.initialize_libca()

from ..instruments import InstrumentDB

from ..utils import normalize_pvname
from .configfile import PVLoggerConfig


STOP_FILE = '_PVLOG_stop.txt'
TIMESTAMP_FILE = '_PVLOG_timestamp.txt'
RUNLOG_FILE = '_PVLOG_runlog.txt'
ERROR_FILE = '_PVLOG_error.txt'
UPDATETIME = 15.0
LOGTIME = 300.0
SLEEPTIME = 0.5

RUN_FOLDER = 'pvlog'
motor_fields = ('.OFF', '.FOFF', '.SET', '.HLS', '.LLS',
                '.DIR', '_able.VAL', '.SPMG')

# The EPICS EPOCH starts at 1990, and may sometimes
# send 0 or EPIC2UNIX_EPOCH=631152000.0
MIN_TIMESTAMP = 1.0e9

def get_machineid_process():
    """return (matimhine_id, process_id)"""
    return hex(uuid.getnode())[2:], os.getpid()

def get_instruments(instrument_names=None):
    """look up Epics Instruments, return dict of name:pvlist"""
    escan_cred = os.environ.get('ESCAN_CREDENTIALS', '')
    insts = {}
    if len(escan_cred) > 0:
        inst_db = InstrumentDB()
        for row in inst_db.get_all_instruments():
            iname = row.name
            if (instrument_names is None or
                iname in instrument_names):
                insts[iname] = []
                for pvname in inst_db.get_instrument_pvs(iname):
                    insts[iname].append(pvname)
    return insts

def save_pvlog_timestamp():
    """
    save timestamp to _PVLOG_timestamp.txt to show when logger last ran
    """
    macid, pid = get_machineid_process()
    with open(TIMESTAMP_FILE, 'w', encoding='utf-8') as fh:
        fh.write(f'{int(time())} {macid} {pid} 0 0 0 \n\n')

def check_pvlog_timestamp():
    """
    read timestamp file, determine if this process is the one that
    wrote the file, and so the controlling process
    """
    mid, pid = get_machineid_process()
    _ts, _mid, _pid = 0, 'none', 0
    line, words = '', []
    if Path(TIMESTAMP_FILE).exists():
        line = ''
        with open(TIMESTAMP_FILE, 'r', encoding='utf-8') as fh:
            line = fh.readlines()[0]
    else:
        return True
    if len(line) > 2:
        words = [a.strip() for a in line.split()]
        if len(words) < 2:
            return True
        _ts = int(words[0])
        _mid = words[1]
        _pid = int(words[2])
    return (_mid == mid and _pid == pid and (time() - _ts) < (2*UPDATETIME))


class LoggedPV():
    """wraps a PV for logging
    """
    def __init__(self, pvname, desc=None, mdel=None,
                 descpv=None, mdelpv=None, connection_timeout=0.25):
        self.pvname = normalize_pvname(pvname)
        self.connection_timeout = connection_timeout
        logname = self.pvname.replace('.', '_') + '.log'
        self.fpath = Path(new_filename(fix_filename(logname)))
        self.filename = self.fpath.as_posix()
        self.timestamp = 0.0
        self.end_timestamp = -1
        self.value = None
        self.char_value = None
        self.data = deque()
        self.needs_header = False
        self.needs_flush = False
        self.connected = None
        self.next_flushtime = 0.0
        self.set_desc(desc, descpv)
        self.set_mdel(mdel, mdelpv)
        self.pv = get_pv(self.pvname, callback=self.onChanges,
                         connection_callback=self.onConnect)

    def write(self, txt, flush=False):
        with open(self.fpath, 'a', encoding='utf-8') as fh:
            fh.write(txt)
            if flush:
                fh.flush()
                self.next_flushtime = time() + 15.0
                self.needs_flush = False

    def flush(self):
        self.next_flushtime = time() + 15.0
        with open(self.fpath, 'a', encoding='utf-8') as fh:
            fh.flush()
            self.needs_flush = False

    def set_mdel(self, mdel, mdelpv):
        self.mdel = mdel
        if self.pvname.endswith('.VAL'):
            if isinstance(mdelpv, PV):
                if mdelpv.wait_for_connection(timeout=self.connection_timeout):
                    if (mdelpv.write_access and
                        self.mdel not in (None, 'None', '<auto>')):
                        mdelpv.put(self.mdel)
                        sleep(0.001)
                        self.mdel = mdelpv.get()
                    elif self.mdel in (None, 'None', '<auto>'):
                        self.mdel = mdelpv.get()

        try:
            self.mdel = float(self.mdel)
        except:
            self.mdel = None

    def set_desc(self, desc, descpv):
        "set description"
        self.desc = desc
        if self.desc in (None, 'None', '<auto>') and isinstance(descpv, PV):
            if not descpv.connected:
                descpv.wait_for_connection(timeout=self.connection_timeout)
            if descpv.connected:
                self.desc = descpv.get()


    def onConnect(self, pvname, conn, pv):
        ts = time()
        if conn:
            if self.connected is None: # initial connection
                self.connected = True
                self.needs_header = True
                msg = None
            else:
                msg = "<event> <CA_reconnected>"
        else:
            msg = "<event> <CA_disconnected>"
        if msg is not None:
            self.write(f"{ts:.3f}  {msg}\n", flush=True)

    def onChanges(self, pvname, value, char_value='', timestamp=None, **kws):
        skip = False
        if self.value is not None and self.mdel is not None:
            try:
                skip = (abs(value - self.value) < self.mdel)
            except:
                skip = False
        if isinstance(skip, np.ndarray):
            skip = any(skip)
        if not skip:
            self.value = value
            self.char_value = char_value
            if '\n' in char_value:
                self.char_value = char_value.replace('\n', '\\n')
            if '\r' in char_value:
                self.char_value = char_value.replace('\r', '\\r')
            if timestamp is None or timestamp < MIN_TIMESTAMP:
                timestamp = time()
            self.timestamp = timestamp
            self.data.append((timestamp, value, char_value))

    def save_current_value(self):
        """
        put the current value and current time into the data queue,
        to record 'what is the value now'?

        This may be useful to do periodically, or at
        the end of data collection.
        """
        self.data.append((time(), self.value, self.char_value))

    def write_data(self):
        if len(self.data) < 1:
            return
        buff = []
        if self.needs_header:
            if self.pv.connected:
                if self.value is None:
                    self.value = self.pv.get()
                if self.char_value is None:
                    self.char_value = self.pv.get(as_string=True)

            buff = ["# pvlog data file",
                    f"# pvname        = {self.pvname}",
                    f"# label         = {self.desc}",
                    f"# monitor_delta = {self.mdel}",
                    f"# start_time    = {isotime()}"]

            for attr in ('count', 'nelm', 'type', 'units',
                    'precision', 'host', 'access'):
                val = getattr(self.pv, attr, 'unknown')
                buff.append(f"# {attr:12s}  = {val}")
            enum_strs = getattr(self.pv, 'enum_strs', None)
            if enum_strs is not None:
                buff.append("# enum strings:")
                for index, nam in enumerate(enum_strs):
                    buff.append(f"#      {index} = {nam}")

            buff.extend(["#---------------------------------",
                         "# timestamp       value             char_value"])
            self.needs_flush = True

        n = len(self.data)
        if n > 0:
            for i in range(n):
                ts, val, cval = self.data.popleft()
                if i == 0 and self.needs_header:
                    # re-determine the char value for the first point
                    cur_val = self.pv.value
                    cval = self.pv._set_charval(val)
                    self.char_value = self.pv._set_charval(cur_val)
                xval = '<index>'
                if self.pv.nelm == 1 and 'double' in self.pv.type:
                    try:
                        xval = gformat(val, length=16)
                    except:
                        pass
                elif ('enum' in self.pv.type or
                      'int' in self.pv.type or
                      'long' in self.pv.type):
                    xval = f'{val:<16d}'

                buff.append(f"{ts:.3f}  {xval}   {cval}")
            buff.append('')
            self.needs_flush = True
            self.needs_header = False
        flush = self.needs_flush and (time() > self.next_flushtime)
        self.write('\n'.join(buff), flush=flush)


class PVLogger():
    about_msg =  """Epics PV Logger, CLI
 Matt Newville <newville@cars.uchicago.edu>
"""
    def __init__(self, configfile=None, prompt=None):
        self.pvs = {}
        self.end_date = None
        self.end_timestamp = None
        self.exc = None
        if configfile is not None:
            self.read_configfile(configfile)

    def read_configfile(self, configfile):
        self.cfile = PVLoggerConfig(configfile)
        self.config = self.cfile.config

        self.folder = Path(self.config.get('folder', 'pvlog'))
        self.datadir = self.config.get('datadir', '')
        if len(self.datadir) < 1 or self.datadir == '.':
            self.datadir = os.getcwd()
        self.datadir = Path(self.datadir)
        pvlog_folder = Path(self.datadir, self.folder).absolute()
        if pvlog_folder.exists():
            tfile = Path(pvlog_folder, TIMESTAMP_FILE)
            cfile = Path(pvlog_folder, '_PVLOG.yaml')
            lfile = Path(pvlog_folder, '_PVLOG_filelist.txt')
            if tfile.exists() and cfile.exists() and lfile.exists():
                raise ValueError(f"PVLOG folder '{pvlog_folder}' appears to be in use")

        pvlog_folder.mkdir(mode=0o755, parents=False, exist_ok=True)
        os.chdir(pvlog_folder)

        # defualt end time is 1 month from now
        month =  (datetime.now() + timedelta(days=30))
        end_date = month.isoformat(timespec='seconds', sep=' ')
        end_tstamp = month.timestamp()

        self.end_date = self.config.get('end_datetime', end_date)

        try:
            dt = dateparser.parse(self.end_date)
            end_tstamp = dt.timestamp()
        except:
            pass
        self.end_timestamp = end_tstamp

    def connect_pvs(self):
        """
        initial connection, or re-connection of PVs
        from configuration to PV objects, and saved metadata files
        """
        _pvnames, _pvdesc, _pvmdel = [], [], []
        for pvline in self.config.get('pvs', []):
            name = pvline.strip()
            desc = '<auto>'
            mdel = '<auto>'
            if '|' in pvline:
                words = [w.strip() for w in pvline.split('|')]
                name = words[0]
                if len(words) > 1:
                    desc = words[1]
                if len(words) > 2:
                    mdel = words[2]
            if name in _pvnames:
                idx = _pvnames.index(name)
                _pvdesc[idx] = desc
                _pvmdel[idx] = mdel
            else:
                _pvnames.append(name)
                _pvdesc.append(desc)
                _pvmdel.append(mdel)
        inst_names = self.config.get('instruments', [])
        escan_cred = os.environ.get('ESCAN_CREDENTIALS', '')
        inst_map = {}
        if len(inst_names) > 0 and len(escan_cred) > 0:
            inst_db = InstrumentDB()
            for inst in inst_names:
                inst_map[inst] = []
                try:
                    for pvname in  inst_db.get_instrument_pvs(inst):
                        _pvnames.append(pvname)
                        inst_map[inst].append(pvname)
                        _pvdesc.append('<auto>')
                        _pvmdel.append('<auto>')
                except AttributeError:
                    pass

        mdelpvs = {}
        descpvs = {}
        rtyppvs = {}
        for ipv, pvname in enumerate(_pvnames):
            if pvname.endswith('.VAL'):
                pref = pvname[:-4]
                rtyppvs[pvname] = get_pv(f"{pref}.RTYP")
                if _pvdesc[ipv] in (None, 'None', '<auto>'):
                    descpvs[pvname] = get_pv(f"{pref}.DESC")
                if _pvmdel[ipv] in (None, 'None', '<auto>'):
                    mdelpvs[pvname] = get_pv(f"{pref}.MDEL")

        sleep(0.05)
        out = {'datadir': self.datadir.as_posix(),
               'folder': self.folder.as_posix(),
               'end_datetime': self.end_date,
               'instruments': inst_map,
               'motors': [],
               'pvs': []}

        for ipv, pvname in enumerate(_pvnames):
            desc = _pvdesc[ipv]
            mdel = _pvmdel[ipv]
            descpv = mdelpv = None
            if desc in (None, 'None', '<auto>') and pvname in descpvs:
                descpv = descpvs[pvname]
            if mdel in (None, 'None', '<auto>')  and pvname in mdelpvs:
                mdelpv = mdelpvs[pvname]
            lpv = self.add_pv(pvname, desc=desc, mdel=mdel,
                              descpv=descpv, mdelpv=mdelpv)

            out['pvs'].append(' | '.join([lpv.pvname, lpv.desc, str(lpv.mdel)]))

            rtype_pv = rtyppvs.get(pvname, None)
            if rtype_pv is not None and 'motor' == rtype_pv.get():
                desc = lpv.desc
                out['motors'].append(pvname)
                prefix = pvname[:-4]
                for mfield in motor_fields:
                    self.add_pv(f"{prefix}{mfield}",
                                desc=f"{lpv.desc} {mfield}",  mdel=None)

        with open('_PVLOG.yaml', 'w', encoding='utf-8') as fh:
            yaml.safe_dump(out, fh, default_flow_style=False, sort_keys=False)

        pfiles = ["# PV Name                                |    Log File "]
        for lpv in self.pvs.values():
            pfiles.append(f"{lpv.pvname:40s} | {lpv.filename:40s}")
        pfiles.append("")
        with open('_PVLOG_filelist.txt', 'w', encoding='utf-8') as fh:
            fh.write('\n'.join(pfiles))
        # count connected PVs
        sleep(0.1)
        ntotal = len(self.pvs)
        nconn = 0
        for loggedpv in self.pvs.values():
            if loggedpv.pv.connected:
                nconn += 1
        with open(RUNLOG_FILE, 'a', encoding='utf-8') as fh:
            fh.write(f'{isotime()}: Connected to {nconn} of {ntotal} Logged PVs\n')


    def add_pv(self, pvname, desc=None, mdel=None, descpv=None, mdelpv=None):
        if pvname not in self.pvs:
            self.pvs[pvname] = LoggedPV(pvname, desc=desc, mdel=mdel,
                                        descpv=descpv, mdelpv=mdelpv)
        else:
            this_pv = self.pvs[pvname]
            if desc in (None, 'None', '<auto'):
                desc = this_pv.desc
            this_pv.set_desc(desc, descpv)
            if mdel in (None, 'None', '<auto'):
                mdel = this_pv.mdel
            this_pv.set_mdel(mdel, mdelpv)

        return self.pvs[pvname]

    def look_for_new_pvs(self):
        """
        look for a file named _PVLOG_requests.yaml and add PVs
        listed there to monitoring process
        """
        reqfile = Path("_PVLOG_requests.yaml")
        if reqfile.exists():
            with open(RUNLOG_FILE, 'a', encoding='utf-8') as fh:
                fh.write(f'{isotime()}: read _PVLOG_requests.yaml\n')

            rconfig = PVLoggerConfig(reqfile.as_posix())
            for section in ('pvs', 'instruments'):
                newdat = rconfig.config.get(section, [])
                if len(newdat) > 0:
                    self.config[section].extend(newdat)

            end_date = rconfig.config.get('end_datetime', None)
            if end_date is not None:
                try:
                    dt = dateparser.parse(end_date)
                    end_tstamp = dt.timestamp()
                    self.end_date = dt.isoformt(timespec='sec', sep=' ')
                    self.end_timestamp = end_tstamp
                except:
                    pass

            self.connect_pvs()

            try:
                reqfile.unlink(missing_ok=True)
            except:
                pass

    def look_for_exit_signal(self):
        """
        look for whether data collection should stop.
        There are two ways to specify stopping:

           a) a file named _PVLOG_stop.txt written to the folder will stop collection
           b) if the end_datet specified in the configuration is exceeded
        """
        exit_request = ((self.end_timestamp > 65536) and
                        (time() > self.end_timestamp))
        stopfile = Path(STOP_FILE)
        if stopfile.exists():
            exit_request = True
            try:
                stopfile.unlink(missing_ok=True)
            except:
                pass
        if not check_pvlog_timestamp():
            with open(RUNLOG_FILE, 'a', encoding='utf-8') as fh:
                macid, pid = get_machineid_process()
                fh.write(f'{isotime()}: not logging process! mac={macid}, pid={pid}\n')
            exit_request = True

        return exit_request

    def finish(self):
        """finish data collection"""
        with open(RUNLOG_FILE, 'a', encoding='utf-8') as fh:
            fh.write(f'{isotime()}: got exit signal\n')
        for pv in self.pvs.values():
            pv.pv.clear_callbacks()
            pv.save_current_value()
        sleep(SLEEPTIME)
        for pv in self.pvs.values():
            pv.write_data()
            pv.flush()
        with open(RUNLOG_FILE, 'a', encoding='utf-8') as fh:
            fh.write(f'{isotime()}: finishing\n')

    def on_exit(self):
        with open(RUNLOG_FILE, 'a', encoding='utf-8') as fh:
            fh.write(f'{isotime()}: exit.\n')

        if self.exc is not None:
            with open(ERROR_FILE, 'a', encoding='utf-8') as fh:
                traceback.print_exception(self.exc, file=fh)

    def run(self):
        """run, collecting data until the exit signal is given"""
        self.connect_pvs()
        atexit.register(self.on_exit)

        last_update = 0
        last_logtime = 0
        while True:
            try:
                messages = []
                sleep(SLEEPTIME)
                now = time()
            except KeyboardInterrupt:
                self.exc = sys.exception()
                break
            except:
                self.exc = sys.exception()
            try:
                for pv in self.pvs.values():
                    try:
                        if len(pv.data) > 0:
                            pv.write_data()
                    except:
                        messages.append(f"{isotime()}: error writing data for {pv}")
            except:
                self.exc = sys.exception()

            if now > last_update + UPDATETIME:
                try:
                    save_pvlog_timestamp()
                    if self.look_for_exit_signal():
                        messages.append(f"{isotime()}: got exit signal")
                        self.finish()
                        break
                except:
                    self.exc = sys.exception()
                    messages.append(f"{isotime()}: error saving timestamps/looking for exit")
                try:
                    self.look_for_new_pvs()
                    last_update = now
                except:
                    self.exc = sys.exception()
                    messages.append(f"{isotime()}: error looking for new pvs")

            try:
                if now > last_logtime + LOGTIME:
                    messages.append(f'{isotime()}: collecting')

                if len(messages) > 0:
                    messages.append('')
                    with open(RUNLOG_FILE, 'a', encoding='utf-8') as fh:
                        fh.write("\n".join(messages))
                    last_logtime = now
            except:
                self.exc = sys.exception()

        with open(RUNLOG_FILE, 'a', encoding='utf-8') as fh:
            fh.write(f"{isotime()}: collection done.\n")
