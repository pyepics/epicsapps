#!/usr/bin/env python
"""
 provides make_newdb() function to create an empty Epics Instrument Library

"""
from datetime import datetime

from sqlalchemy import (MetaData, create_engine, Table, Column,
                        Integer, String, Text, DateTime,
                        ForeignKey, UniqueConstraint)

from .utils import backup_versions
from .simpledb import SimpleDB

def PointerCol(name, other=None, keyid='id', **kws):
    if other is None:
        other = name
    return Column("%s_%s" % (name, keyid), None,
                  ForeignKey('%s.%s' % (other, keyid), **kws))

def StrCol(name, size=None, **kws):
    if size is None:
        return Column(name, Text, **kws)
    else:
        return Column(name, String(size), **kws)

def NamedTable(tablename, metadata, keyid='id', nameid='name',
               name=True, name_unique=True,
               notes=True, attributes=True, cols=None):
    args  = [Column(keyid, Integer, primary_key=True)]
    if name:
        args.append(StrCol(nameid, nullable=False, unique=name_unique))
    if notes:
        args.append(StrCol('notes'))
    if attributes:
        args.append(StrCol('attributes'))
    if cols is not None:
        args.extend(cols)
    return Table(tablename, metadata, *args)

class InitialData:
    info    = [["version", "1.4"],
               ["verify_erase", "1"],
               ["verify_move",   "1"],
               ["verify_overwrite",  "1"],
               ["epics_prefix",   ""],
               ["create_date", '<now>'],
               ["modify_date", '<now>']]

    pvtype = [['numeric',   'Numeric Value'],
              ['enum',      'Enumeration Value'],
              ['string',    'String Value'],
              ['motor',     'Motor Value']]

def  make_newdb(dbname, server= 'sqlite'):
    engine  = create_engine('%s:///%s' % (server, dbname))
    metadata =  MetaData()
    metadata.reflect(engine)

    NamedTable('instrument', metadata,
               cols=[Column('show', Integer, default=1),
                     Column('display_order', Integer, default=0),
                     Column('modify_time', DateTime)])

    NamedTable('command', metadata,
               cols=[StrCol('command'),
                     StrCol('arguments'),
                     StrCol('output_value'),
                     StrCol('output_name')])


    Table('position', metadata,
          Column('id', Integer, primary_key=True),
          StrCol('name', nullable=False),
          StrCol('notes'),
          StrCol('attributes'),
          Column('date', DateTime),
          StrCol('image'),
          Column('modify_time', DateTime),
          Column("instrument_id",  ForeignKey('instrument.id')),
          UniqueConstraint('name', 'instrument_id'))

    NamedTable('instrument_precommand', metadata,
               cols=[Column('order', Integer),
                     PointerCol('command'),
                     PointerCol('instrument')])

    NamedTable('instrument_postcommand', metadata,
                cols=[Column('order', Integer),
                      PointerCol('command'),
                      PointerCol('instrument')])

    NamedTable('pvtype', metadata)
    NamedTable('pv', metadata, cols=[PointerCol('pvtype')])

    Table('instrument_pv', metadata,
          Column('id', Integer, primary_key=True),
          PointerCol('instrument'),
          PointerCol('pv'),
          Column('display_order', Integer, default=0),
          Column('order', Integer, default=1))

    Table('position_pv', metadata,
          Column('id', Integer, primary_key=True),
         StrCol('notes'),
         PointerCol('position'),
         PointerCol('pv'),
         StrCol('value'))

    Table('info', metadata,
          Column('key', Text, primary_key=True, unique=True),
          StrCol('value'))

    metadata.create_all(bind=engine)

    db = SimpleDB(dbname, server=server)
    for name, notes in InitialData.pvtype:
        db.insert('pvtype', name=name, notes=notes)

    now = datetime.isoformat(datetime.now(), sep=' ')

    for key, value in InitialData.info:
        if value == '<now>':
            value = now
        rows = db.get_rows('info', key=key)
        if len(rows) == 0:
            rows = db.insert('info', key=key, value=value)
        else:
            rows = db.update('info', where={'key': key}, value=value)
    db.close()

if __name__ == '__main__':
    dbname = 'Test.ein'
    backup_versions(dbname)
    make_newdb(dbname)
    print('''%s  created and initialized.''' % dbname)
