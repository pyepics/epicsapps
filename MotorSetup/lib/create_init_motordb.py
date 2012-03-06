#!/usr/bin/env python
"""
 provides make_newdb() function to create an empty Epics Instrument Library
"""
import motordb
if __name__ == '__main__':
    dbname = 'GSECARS_Motors.mdb'
    motordb.make_newdb(dbname)
    print '''%s  created and initialized.''' % dbname

