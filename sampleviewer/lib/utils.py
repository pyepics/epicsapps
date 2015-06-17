
def normalize_pvname(pvname):
    if '.' not in pvname:
        pvname = '%s.VAL' % pvname
    return pvname
