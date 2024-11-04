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
                             debugtimer)

from .configfile import PVLoggerConfig


SLEEPTME = 0.05
RUN_FOLDER = 'pvlog'
motor_fields = ('.VAL','.OFF','.FOFF','.SET','.HLS','.LLS',
                '.DIR','_able.VAL','.SPMG','.DESC')


class PVLogger():
    about_msg =  """Epics PV Logger, CLI
 Matt Newville <newville@cars.uchicago.edu>
"""
    def __init__(self, configfile=None, prompt=None, wxparent=None):
        self.data = {}
        self.pvs = []
        self.wxparent = wxparent
        print("PVLogger CONF FILE ", configfile)
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

        with open("Instruments.json", "w") as fh:
            json.dump(inst_map, fh)

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
            self.pvs.append(get_pv(pvname))
            if 'motor' == rtyppvs[pvname].get():
                prefix = pvname
                if pvname.endswith('.VAL'):
                    prefix = prefix[:-4]
                motor_lines.append(prefix + '.VAL')
                mot_names = [f"{prefix}{i}" for i in motor_fields]
                mot_names.extend([f"{prefix}.DESC"])
                for mname in mot_names:
                    self.pvs.append(get_pv(mname))


        motor_lines.append('')
        desc_lines.append('')
        with open("PVs.txt", "w") as fh:
            fh.write('\n'.join(desc_lines))
        with open("Motors.txt", "w") as fh:
            fh.write('\n'.join(motor_lines))



    def onChanges(self, pvname, value, char_value='', timestamp=0, **kws):
        self.data[pvname].append((value, char_value, timestamp))


    def run(self):
        self.connect_pvs()
        print(" Run: ", len(self.pvs))
