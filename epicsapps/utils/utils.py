import os
import epics

def get_pvroot(pvname):
    """strip prvoot from PV name"""
    out = str(pvname)
    if '.' in pvname:
        out = pvname[:pvname.find('.')]
    return out

def normalize_pvname(pvname):
    """return pvname, with ending .VAL if no suffix was given"""
    if '.' not in pvname:
        pvname = f'{pvname}.VAL'
    return pvname

def get_pvdesc(pvname):
    "get description value for a PV"
    desc = pvname
    pref = get_pvroot(pvname)
    descpv = epics.get_pv(f'{pref}.DESC', form='native')
    if descpv.connect():
        desc = descpv.get()
    return desc

def get_pvmdel(pvname):
    "get MDEL value for a PV"
    desc = pvname
    pref = get_pvroot(pvname)
    descpv = epics.get_pv(pref + '.MDEL', form='native')
    if descpv.connect():
        desc = descpv.get()
    return desc
 import os
 import epics

def get_pvroot(pvname):
    """strip prvoot from PV name"""
    out = str(pvname)
    if '.' in pvname:
        out = pvname[:pvname.find('.')]
    return out

 def normalize_pvname(pvname):
     """return pvname, with ending .VAL if no suffix was given"""
     if '.' not in pvname:
         pvname = f'{pvname}.VAL'
     return pvname

 def get_pvdesc(pvname):
     "get description value for a PV"
     desc = pref = pvname
     descpv = epics.get_pv(pref + '.DESC', form='native')
     desc = pvname
     pref = get_pvroot(pvname)
     descpv = epics.get_pv(f'{pref}.DESC', form='native')
     if descpv.connect():
         desc = descpv.get()
     return desc

def get_pvmdel(pvname):
    "get MDEL value for a PV"
    desc = pvname
    pref = get_pvroot(pvname)
    descpv = epics.get_pv(pref + '.MDEL', form='native')
    if descpv.connect():
        desc = descpv.get()
