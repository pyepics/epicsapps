import os
import epics

def normalize_pvname(pvname):
    pvname = str(pvname)
    if '.' not in pvname:
        pvname = '%s.VAL' % pvname
    return pvname

def get_pvtypes(pvobj, instrument=None):
    """create tuple of choices for PV Type for database,
    which sets how to display PV entry.

    if pvobj is an epics.PV, the epics record type and
    pv.type are used to select the choices.

    if pvobj is an instrument.PV (ie, a db entry), the
    pvobj.pvtype.name field is used.
    """
    inst_pv = None
    if instrument is not None:
        inst_pv = instrument.PV

    choices = ['numeric', 'string']
    if isinstance(pvobj, epics.PV):
        prefix = pvobj.pvname
        suffix = None
        typename = pvobj.type
        if '.' in prefix:
            prefix, suffix = prefix.split('.')
        rectype = epics.caget("%s.RTYP" % prefix)
        if rectype == 'motor' and suffix in (None, 'VAL'):
            typename = 'motor'
        if pvobj.type == 'char' and pvobj.count > 1:
            typename = 'string'

    elif inst_pv is  not None and isinstance(pvobj, inst_pv):
        typename = str(pvobj.pvtype.name)

    # now we have typename: use as default, add alternate choices
    if typename == 'motor':
        choices = ['motor', 'numeric', 'string']
    elif typename in ('enum', 'time_enum'):
        choices = ['enum', 'numeric', 'string']
    elif typename in ('string', 'time_string'):
        choices = ['string', 'numeric']
    return tuple(choices)

def get_pvdesc(pvname):
    desc = pref = pvname
    if '.' in pvname:
        pref = pvname[:pvname.find('.')]
    descpv = epics.get_pv(pref + '.DESC', form='native')
    if descpv.connect():
        desc = descpv.get()
    return desc
