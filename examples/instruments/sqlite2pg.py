#!/usr/bin/env python
"""
This will convert an Epics Instruments file in SQLite
to one using PostgresQL ScanDB

requires epicsscan to be installed
"""

from epicsscan import ScanDB, InstrumentDB

# Name of the Sqlite3 file
fname   = '13BMC_Setup_2024-3.ein'

# Database connection information
dbname   = 'mydb'
username = 'db_user'
password = 'something_super_secret'
host     = 'cars4.cars.aps.anl.gov'

def sqlite2pg(fname, dbname, username, password, host):
    sdb = ScanDB(fname, server='sqlite3')
    pdb = ScanDB(dbname, server='postgresql', host=host,
                 user=username, password=password)

    s_idb = InstrumentDB(sdb)
    p_idb = InstrumentDB(pdb)

    for row in sdb.get_rows('pv'):
        pdb.add_row('pv', name=row.name, notes=row.notes,
                    pvtype_id=row.pvtype_id)

    for row in s_idb.get_all_instruments():
        instname = row.name
        print("Get Sqlite Instrument ", instname)
        inst = s_idb.get_instrument(instname)
        for posname in s_idb.get_positionlist(instname):
            pvals = s_idb.get_position_vals(instname, posname)

            if p_idb.get_instrument(instname) is None:
                print("Add PG Instrument ", instname)
                p_idb.add_instrument(instname, pvs=list(pvals.keys()))
            print("Save position ", instname, posname, pvals)
            p_idb.save_position(instname, posname, pvals)

    print("done")
