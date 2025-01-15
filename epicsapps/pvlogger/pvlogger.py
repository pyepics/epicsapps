#!/usr/bin/python
"""
Epics PV Logger Application, CLI no GUI
"""
import os
import time
from collections import deque
from pathlib import Path
import numpy as np
import toml
from epics import get_pv, caget, PV
from pyshortcuts import debugtimer, fix_filename, new_filename, isotime, gformat

from ..instruments import InstrumentDB

from ..utils import (get_pvtypes, get_pvdesc, normalize_pvname)


from .configfile import PVLoggerConfig

STOP_FILE = '_PVLOG_stop.txt'
TIMESTAMP_FILE = '_PVLOG_timestamp.txt'
UPDATETIME = 30.0
SLEEPTIME = 0.5
RUN_FOLDER = 'pvlog'
motor_fields = ('.OFF', '.FOFF', '.SET', '.HLS', '.LLS',
                '.DIR', '_able.VAL', '.SPMG')

def look_for_exit_signal():
    """look for a file named _PVLOG_stop.txt to stop collection
    """
    exit_request = False
    stopfile = Path(STOP_FILE)
    if stopfile.exists():
        exit_request = True
        try:
            stopfile.unlink(missing_ok=True)
        except:
            pass
    return exit_request

def save_pvlog_timestamp():
    """
    save timestamp to _PVLOG_timestamp.txt to show when logger last ran
    """
    with open(TIMESTAMP_FILE, "w") as fh:
        fh.write(f'{time.time()}\n')

class LoggedPV():
    """wraps a PV for logging
    """
    def __init__(self, pvname, desc=None, mdel=None,
                 descpv=None, mdelpv=None, connection_timeout=0.25):
        self.pvname = normalize_pvname(pvname)
        self.connection_timeout = connection_timeout
        logname = self.pvname.replace('.', '_') + '.log'
        fpath = Path(new_filename(fix_filename(logname)))
        self.datafile = open(fpath, 'a')
        self.filename = fpath.as_posix()
        self.needs_flush = False
        self.lastflush = 0.0

        self.data = deque()
        self.needs_header = False
        self.connected = None
        self.value = None
        self.can_be_float = None  # decide later
        self.set_desc(desc, descpv)
        self.set_mdel(mdel, mdelpv)
        self.pv = get_pv(self.pvname, callback=self.onChanges,
                         connection_callback=self.onConnect)

    def set_mdel(self, mdel, mdelpv):
        self.mdel = mdel
        if self.pvname.endswith('.VAL'):
            if isinstance(mdelpv, PV):
                if mdelpv.wait_for_connection(timeout=self.connection_timeout):
                    if (mdelpv.write_access and
                        self.mdel not in (None, 'None', '<auto>')):
                        mdelpv.put(self.mdel)
                        time.sleep(0.001)
                        self.mdel = mdelpv.get()
                    elif self.mdel in (None, 'None', '<auto>'):
                        self.mdel = mdelpv.get()

        try:
            self.mdel = float(self.mdel)
            self.mdel_is_float = True
        except:
            self.mdel_is_float = False

    def set_desc(self, desc, descpv):
        "set description"
        self.desc = desc
        if self.desc in (None, 'None', '<auto>') and isinstance(descpv, PV):
            if not descpv.connected:
                descpv.wait_for_connection(timeout=self.connection_timeout)
            if descpv.connected:
                self.desc = descpv.get()


    def onConnect(self, pvname, conn, pv):
        ts = time.time()
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
            self.datafile.write(f"{ts:.3f}  {msg}\n")
        self.needs_flush = True

    def onChanges(self, pvname, value, char_value='', timestamp=None, **kws):
        skip = False
        if self.value is not None and self.mdel_is_float:
            try:
                skip = (abs(value - self.value) < self.mdel)
            except:
                skip = False
        if isinstance(skip, np.ndarray):
            skip = any(skip)
        if not skip:
            self.value = value
            self.char_value = char_value
            if timestamp is None:
                timestamp = time.time()
            self.timestamp = timestamp
            self.data.append((timestamp, value, char_value))

    def flush(self):
        self.lastflush = time.time()
        self.needs_flush = False
        self.datafile.flush()

    def write_data(self, with_flush=False):
        if self.needs_header:
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
                         "# timestamp       value               char_value", ""])
            self.datafile.write('\n'.join(buff))
            self.needs_header = False

        if self.can_be_float is None:  # decide now
            self.can_be_float = ((1 == self.pv.nelm) and
                                 ('char' not in self.pv.type))

        n = len(self.data)
        if n > 0:
            buff = []
            for i in range(n):
                ts, val, cval = self.data.popleft()
                xval = '<index>'
                if self.can_be_float:
                    try:
                        xval = gformat(val, length=18)
                    except:
                        pass
                buff.append(f"{ts:.3f}  {xval}   {cval}")
            buff.append('')
            self.datafile.write('\n'.join(buff))
            self.needs_flush = True
        if (with_flush or
            (self.needs_flush and (time.time() > (self.lastflush + 15)))):
            self.flush()


class PVLogger():
    about_msg =  """Epics PV Logger, CLI
 Matt Newville <newville@cars.uchicago.edu>
"""
    def __init__(self, configfile=None, prompt=None, wxparent=None):
        self.pvs = {}
        if configfile is not None:
            self.read_configfile(configfile)

    def read_configfile(self, configfile):
        print('read config file ', configfile)
        self.cfile = PVLoggerConfig(configfile)
        self.config = self.cfile.config

        self.folder = self.config.get('folder', 'pvlog')
        self.workdir = self.config.get('workdir', '')
        if len(self.workdir) < 1 or self.workdir == '.':
            self.workdir = os.getcwd()

        self.topfolder = Path(self.workdir, self.folder).absolute()
        self.topfolder.mkdir(mode=0o755, parents=False, exist_ok=True)
        os.chdir(self.topfolder)

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

        time.sleep(0.05)
        out = {'folder': self.folder,
               'workdir': self.workdir,
               'pvs': [], 'motors': [], 'instruments': inst_map}
        print("Connect A", len(_pvnames))
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
            print("ADD PV ", lpv.pvname, lpv.desc, str(lpv.mdel), descpv, mdelpv)
            rtype_pv = rtyppvs.get(pvname, None)
            if rtype_pv is not None and 'motor' == rtype_pv.get():
                desc = lpv.desc
                out['motors'].append(pvname)
                prefix = pvname[:-4]
                for mfield in motor_fields:
                    self.add_pv(f"{prefix}{mfield}",
                                desc=f"{lpv.desc} {mfield}",  mdel=None)

        with open("_PVLOG.toml", "w+") as fh:
            fh.write(toml.dumps(out))

        pfiles = ["# PV Name                                |    Log File "]
        for lpv in self.pvs.values():
            pfiles.append(f"{lpv.pvname:40s} | {lpv.filename:40s}")
        pfiles.append("")
        with open("_PVLOG_filelist.txt", "w+") as fh:
            fh.write('\n'.join(pfiles))

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
            print("read request file")
            rconfig = PVLoggerConfig(reqfile.as_posix())
            for section in ('pvs', 'instruments'):
                newdat = rconfig.get(section, [])
                if len(newdat) > 0:
                    self.config[section].extend(newdat)
            self.connect_pvs()
            print("Connected PVs from request file")
            try:
                reqfile.unlink(missing_ok=True)
            except:
                pass

    def run(self):
        self.connect_pvs()
        print("Connected ", len(self.pvs))
        last_update = 0
        while True:
            time.sleep(SLEEPTIME)
            now = time.time()
            if now > last_update + UPDATETIME:
                save_pvlog_timestamp()
                if look_for_exit_signal():
                    for pv in self.pvs.values():
                        pv.pv.clear_callbacks()
                    time.sleep(SLEEPTIME)
                    for pv in self.pvs.values():
                        pv.write_data(with_flush=True)
                    break
                self.look_for_new_pvs()
                last_update = now
            for pv in self.pvs.values():
                pv.write_data()
