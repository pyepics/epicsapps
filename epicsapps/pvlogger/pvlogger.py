#!/usr/bin/python
"""
Epics PV Logger Application, CLI no GUI
"""
import os
import time
from collections import deque
from pathlib import Path

import toml
from epics import get_pv, caget
from pyshortcuts import debugtimer, fix_filename, new_filename, isotime

from ..instruments import InstrumentDB

from ..utils import (get_pvtypes, get_pvdesc, normalize_pvname)


from .configfile import PVLoggerConfig


ARCHIVE_DELTA = 1.e-8
FLUSHTIME = 30.0
SLEEPTIME = 0.5
RUN_FOLDER = 'pvlog'
motor_fields = ('.VAL', '.OFF', '.FOFF', '.SET', '.HLS', '.LLS',
                '.DIR', '_able.VAL', '.SPMG', '.DESC')

class LoggedPV():
    """wraps a PV for logging
    """
    def __init__(self, pvname, desc=None, adel=ARCHIVE_DELTA):
        self.desc = desc
        try:
            adel = float(adel)
        except:
            adel = ARCHIVE_DELTA
        self.adel = adel

        self.pvname = normalize_pvname(pvname)
        logname = self.pvname.replace('.', '_') + '.log'
        logname = fix_filename(logname)
        fpath = Path(new_filename(logname))
        self.datafile = open(fpath, 'a')
        self.filename = fpath.as_posix()
        self.needs_flush = False
        self.lastflush = 0.0

        self.data = deque()
        self.needs_header = False
        self.connected = None
        self.value = None
        self.pv = get_pv(self.pvname, callback=self.onChanges,
                         connection_callback=self.onConnect)

    def onConnect(self, pvname, conn, pv):
        if conn:
            if self.connected is None: # initial connection
                self.connected = True
                self.needs_header = True
            else:
                buff = [f"{time.time():.3f}   {self.value}   <reconnected>"]
                self.datafile.write('\n'.join(buff))
        else:
            buff = [f"{time.time():.3f}   {self.value}   <disconnected>"]
            self.datafile.write('\n'.join(buff))
        self.needs_flush = True

    def onChanges(self, pvname, value, char_value='', timestamp=0.0, **kws):
        try:
            skip = (abs(value - self.value) < self.adel)
        except:
            skip = False
        if not skip:
            self.value = value
            if timestamp is None:
                timestamp = time.time()
            self.data.append((timestamp, value, char_value))

    def flush(self):
        self.lastflush = time.time()
        self.needs_flush = False
        self.datafile.flush()

    def process(self):
        if self.needs_header:
            buff = ["# pvlog data file",
                    f"# pvname     = {self.pvname}",
                    f"# label      = {self.desc}",
                    f"# delta      = {self.adel}",
                    f"# start_time = {isotime()}"]

            for attr in ('count', 'nelm', 'type', 'units',
                    'precision', 'host', 'access'):
                val = getattr(self.pv, attr, 'unknown')
                buff.append(f"# {attr:10s} = {val}")
            enum_strs = getattr(self.pv, 'enum_strs', None)
            if enum_strs is not None:
                buff.append("# enum strings:")
                for index, nam in enumerate(enum_strs):
                    buff.append(f"#      {index} = {nam}")

            buff.extend(["#---------------------------------",
                         "# timestamp   value    char_value", ""])
            self.datafile.write('\n'.join(buff))
            self.needs_header = False
        n = len(self.data)
        if n > 0:
            buff = []
            for i in range(n):
                ts, val, cval = self.data.popleft()
                buff.append(f"{ts:.3f}  {val}   {cval}")
            buff.append('')
            self.datafile.write('\n'.join(buff))
            self.needs_flush = True
        if self.needs_flush and (time.time() > (self.lastflush + 15)):
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
        self.config = cnf = self.cfile.config

        self.update_secs = cnf.get('update_seconds', 5)
        self.folder = cnf.get('folder', 'pvlog')
        self.workdir = cnf.get('workdir', '')
        if len(self.workdir) < 1:
            self.workdir = os.getcwd()

        self.topfolder = Path(self.workdir, self.folder).absolute()
        self.topfolder.mkdir(mode=0o755, parents=False, exist_ok=True)
        os.chdir(self.topfolder)

    def connect_pvs(self):
        _pvnames, _pvdesc, _pvadel = [], [], []
        cnf = self.config
        for pvline in cnf.get('pvs', []):
            name = pvline.strip()
            desc = '<auto>'
            adel = str(ARCHIVE_DELTA)
            if '|' in pvline:
                words = pvline.split('|')
                name = words[0].strip()
                if len(words) > 1:
                    desc = words[1]
                if len(words) > 2:
                    adel = words[2].strip()

            _pvnames.append(name.strip())
            _pvdesc.append(desc.strip())
            _pvadel.append(adel.strip())
        inst_names = cnf.get('instruments', [])
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
                        _pvadel.append(str(ARCHIVE_DELTA))
                except AttributeError:
                    pass

        descpvs = {}
        rtyppvs = {}
        for ipv, pvname in enumerate(_pvnames):
            pref = pvname[:-4] if pvname.endswith('.VAL') else pvname
            rtyppvs[pvname] = get_pv(f"{pref}.RTYP")
            if _pvdesc[ipv] == '<auto>':
                descpvs[pvname] = get_pv(f"{pref}.DESC")

        time.sleep(0.01)
        out = {'folder': self.folder,
               'workdir': self.workdir,
               'update_seconds': self.update_secs,
               'pvs': [], 'motors': [], 'instruments': inst_map}

        self.pvs = {}
        for ipv, pvname in enumerate(_pvnames):
            desc = _pvdesc[ipv]
            adel = _pvadel[ipv]
            if desc == '<auto>' and pvname in descpvs:
                desc = descpvs[pvname].get()
            if adel == '<auto>':
                adel = ARCHIVE_DELTA
            out['pvs'].append(f" {pvname} | {desc} | {adel}")
            self.add_pv(pvname, desc=desc, adel=adel)
            if 'motor' == rtyppvs[pvname].get():
                prefix = pvname
                if pvname.endswith('.VAL'):
                    prefix = prefix[:-4]
                out['motors'].append(prefix + '.VAL')
                for mfield in motor_fields:
                    self.add_pv(f"{prefix}{mfield}",
                                desc=f"{desc} {mfield}",  adel=adel)

        with open("_PVLOG.toml", "w+") as fh:
            fh.write(toml.dumps(out))

        pfiles = ["# PV Name                                |    Log File "]
        for lpv in self.pvs.values():
            pfiles.append(f"{lpv.pvname:40s} | {lpv.filename:40s}")
        pfiles.append("")
        with open("_PVLOG_filelist.txt", "w+") as fh:
            fh.write('\n'.join(pfiles))

    def add_pv(self, pvname, desc=None, adel=ARCHIVE_DELTA):
        if pvname not in self.pvs:
            self.pvs[pvname] = LoggedPV(pvname, desc=desc, adel=adel)

    def run(self):
        self.connect_pvs()
        while True:
            time.sleep(SLEEPTIME)
            for pv in self.pvs.values():
                pv.process()
