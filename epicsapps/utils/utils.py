import os
from datetime import datetime
from pathlib import Path
import epics

BAD_FILECHARS = ';~,`!%$@$&^?*#:"/|\'\\\t\r\n (){}[]<>'
GOOD_FILECHARS = '_'*len(BAD_FILECHARS)

TRANS_FILE = str.maketrans(BAD_FILECHARS, GOOD_FILECHARS)

def get_timestamp():
    """return ISO format of current timestamp:
    2012-04-27 17:31:12
    """
    return datetime.isoformat(datetime.now(),
                              sep=' ', timespec='seconds')

def new_filename(filename):
    """
    increment filename to unused filename
    """
    fpath = Path(filename)
    if fpath.exists():
        fstem = fpath.stem
        fsuffix = fpath.suffix
        if fsuffix.startswith('.'):
            fsuffix = fsuffix[1:]
        if len(fsuffix) == 0:
            fsuffix = 'txt'
        int_suffix = True
        fsint = 0
        try:
            fsint = int(fsuffix)
        except (ValueError, TypeError):
            int_suffix = False
        while fpath.exists():
            fsint += 1
            if int_suffix:
                fpath = Path(f"{fstem}.{fsint:03d}")
            else:
                if '_' in fstem:
                    w = fstem.split('_')
                    try:
                        fsint = int(w[-1])
                        fstem = '_'.join(w[:-1])
                    except (ValueError, TypeError):
                        pass
                fpath = Path(f"{fstem}_{fsint:03d}.{fsuffix}")

    return fpath.as_posix()


def fix_filename(filename, new=True):
    """
    fix string to be a 'good' filename.
    This may be a more restrictive than the OS, but avoids nasty cases.

    new : increment filename if filename is in use.
    """
    fname = str(filename).translate(TRANS_FILE)
    if fname.count('.') > 1:
        for i in range(fnamecount('.') - 1):
            idot = fname.find('.')
            fname = f"{fname[:idot]}_{fname[idot+1:]}"
    if new:
        fname = new_filename(fname)
    return fname

def fix_varname(s):
    """fix string to be a 'good' variable name."""
    t = str(s).translate(TRANS_FILE)
    t = t.replace('.', '_').replace('-', '_')
    while t.endswith('_'):
        t = t[:-1]
    return t


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
