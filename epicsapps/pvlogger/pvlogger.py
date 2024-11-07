#!/usr/bin/python
"""
Epics PV Logger Application, CLI no GUI
"""
import os
import time
from collections import deque
from pathlib import Path
import json

from epics import get_pv, caget

from ..instruments import InstrumentDB

from ..utils import (get_pvtypes, get_pvdesc, normalize_pvname,
                     debugtimer, fix_filename)

from .configfile import PVLoggerConfig


FLUSHTIME = 30.0
SLEEPTIME = 0.5
RUN_FOLDER = 'pvlog'
motor_fields = ('.VAL', '.OFF', '.FOFF', '.SET', '.HLS', '.LLS',
                '.DIR', '_able.VAL', '.SPMG', '.DESC')

class PVLogger():
    about_msg =  """Epics PV Logger, CLI
 Matt Newville <newville@cars.uchicago.edu>
"""
    def __init__(self, configfile=None, prompt=None, wxparent=None):
        self.data = {}
        self.datafiles = {}
        self.lastflush = {}
        self.pvs = []
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
        _pvnames, _pvdesc = [], []
        cnf = self.config
        for pvline in cnf.get('pvs', []):
            name = pvline.strip()
            desc = '<auto>'
            if '|' in pvline:
                name, desc = pvline.split('|', 1)
            _pvnames.append(name.strip())
            _pvdesc.append(desc.strip())

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
                except AttributeError:
                    pass

        descpvs = {}
        rtyppvs = {}
        for ipv, pvname in enumerate(_pvnames):
            dpv = pvname + '.DESC'
            rpv = pvname + '.RTYP'
            if pvname.endswith('.VAL'):
                dpv = pvname[:-4] + '.DESC'
                rpv = pvname[:-4] + '.RTYP'
            if _pvdesc[ipv] == '<auto>':
                descpvs[pvname] = get_pv(dpv)
            rtyppvs[pvname] = get_pv(rpv)

        time.sleep(0.01)
        desc_lines = []
        motor_lines = []
        self.pvs = []
        for ipv, pvname in enumerate(_pvnames):
            desc  = _pvdesc[ipv]
            if desc == '<auto>' and pvname in descpvs:
                desc = descpvs[pvname].get()
            desc_lines.append(f"{ipv:04d}  | {pvname} | {desc}")
            self.add_pv(pvname)
            if 'motor' == rtyppvs[pvname].get():
                prefix = pvname
                if pvname.endswith('.VAL'):
                    prefix = prefix[:-4]
                motor_lines.append(prefix + '.VAL')
                for mfield in motor_fields:
                    self.add_pv(f"{prefix}{mfield}")

        motor_lines.append('')
        desc_lines.append('')

        with open("_PVs.txt", "w+") as fh:
            fh.write('\n'.join(desc_lines))

        with open("_Motors.txt", "w+") as fh:
            fh.write('\n'.join(motor_lines))

        with open("_Instruments.json", "w+") as fh:
            json.dump(inst_map, fh)

    def add_pv(self, pvname):
        if pvname not in self.pvs:
            self.pvs.append(get_pv(pvname))
            self.data[pvname] = deque()
            self.datafiles[pvname] = open(fix_filename(f"{pvname}.log"), 'w+')
            self.lastflush[pvname] = 0.

    def onChanges(self, pvname, value, char_value='', timestamp=0, **kws):
        self.data[pvname].append((timestamp, value, char_value))


    def run(self):
        self.connect_pvs()
        print(" Run: ", len(self.pvs))
        for pv in self.pvs:
            pv.clear_callbacks()
            pv.add_callback(self.onChanges)

        while True:
            time.sleep(SLEEPTIME)

            for pvname, data in self.data.items():
                if len(data) > 0:
                    n = len(data)   # use this to permit inserts while writing
                    now = time.time()
                    print(pvname, self.datafiles[pvname], len(data))
                    if now > self.lastflush[pvname] + FLUSHTIME:
                        self.datafiles[pvname].flush()
