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


FLUSHTIME = 30.0
SLEEPTIME = 0.5
RUN_FOLDER = 'pvlog'
motor_fields = ('.OFF', '.FOFF', '.SET', '.HLS', '.LLS',
                '.DIR', '_able.VAL', '.SPMG')

class LoggedPV():
    """wraps a PV for logging
    """
    def __init__(self, pvname, desc=None, mdel=None,
                 descpv=None, mdelpv=None, connection_timeout=0.25):
        self.desc = desc
        self.mdel = mdel

        self.pvname = normalize_pvname(pvname)
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
        if self.pvname.endswith('.VAL'):
            if isinstance(mdelpv, PV):
                if mdelpv.wait_for_connection(timeout=connection_timeout):
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

        if self.desc in (None, 'None', '<auto>') and isinstance(descpv, PV):
            if not descpv.connected:
                descpv.wait_for_connection(timeout=connection_timeout)
            if descpv.connected:
                self.desc = descpv.get()
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

    def process(self):
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
                xval = cval
                if self.can_be_float:
                    try:
                        xval = gformat(val, length=18)
                    except:
                        pass
                buff.append(f"{ts:.3f}  {xval}   {cval}")
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
        _pvnames, _pvdesc, _pvmdel = [], [], []
        cnf = self.config
        for pvline in cnf.get('pvs', []):
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

            _pvnames.append(name)
            _pvdesc.append(desc)
            _pvmdel.append(mdel)
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
               'update_seconds': self.update_secs,
               'pvs': [], 'motors': [], 'instruments': inst_map}

        self.pvs = {}
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
            # print("ADD PV ", lpv.pvname, lpv.desc, str(lpv.mdel), descpv, mdelpv)
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
        return self.pvs[pvname]

    def run(self):
        self.connect_pvs()
        while True:
            time.sleep(SLEEPTIME)
            for pv in self.pvs.values():
                pv.process()
