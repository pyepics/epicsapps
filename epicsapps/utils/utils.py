import os
import epics

def normalize_pvname(pvname):
    pvname = str(pvname)
    if '.' not in pvname:
        pvname = f'{pvname}.VAL'
    return pvname

def get_pvdesc(pvname):
    "get description value for a PV"
    desc = pref = pvname
    if '.' in pvname:
        pref = pvname[:pvname.find('.')]
    descpv = epics.get_pv(pref + '.DESC', form='native')
    if descpv.connect():
        desc = descpv.get()
    return desc
