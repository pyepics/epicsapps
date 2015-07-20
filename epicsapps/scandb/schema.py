#!/usr/bin/env python
"""
SQLAlchemy wrapping of scan database

Main Class for full Database:  ScanDB
"""
import os
import time
from datetime import datetime
import logging

# from utils import backup_versions, save_backup

from sqlalchemy import (MetaData, and_, create_engine, text, func,
                        Table, Column, ColumnDefault, ForeignKey,
                        Integer, Float, String, Text, DateTime)

from sqlalchemy.orm import sessionmaker, mapper, clear_mappers, relationship
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.pool import SingletonThreadPool

# needed for py2exe?
from sqlalchemy.dialects import sqlite, mysql, postgresql

from .connections import get_dbengine, hasdb_pg
from .sqla_utils import (IntCol, ArrayCol, StrCol, PointerCol,
                         NamedTable, BaseTable)

## status states for commands
CMD_STATUS = ('unknown', 'requested', 'canceled', 'starting', 'running',
               'aborting', 'stopping', 'aborted', 'finished')

PV_TYPES = (('numeric', 'Numeric Value'),
            ('enum',  'Enumeration Value'),
            ('string',  'String Value'),
            ('motor', 'Motor Value') )



class Info(BaseTable):
    "general information table (versions, etc)"
    keyname, value, notes, modify_time = [None]*4

    def __repr__(self):
        name = self.__class__.__name__
        return "<%s(%s='%s')>" % (name, self.keyname, str(self.value))

class Status(BaseTable):
    "status table"
    name, notes = None, None

class ScanPositioners(BaseTable):
    "positioners table"
    name, notes, drivepv, readpv, extrapvs, use = [None]*6

class SlewScanPositioners(BaseTable):
    "positioners table for slew scans"
    name, notes, drivepv, readpv, extrapvs, use = [None]*6

class ScanCounters(BaseTable):
    "counters table"
    name, notes, pvname, use = [None]*4

class ScanDetectors(BaseTable):
    "detectors table"
    name, notes, pvname, kind, options, use = [None]*6

class ExtraPVs(BaseTable):
    "extra pvs in scan table"
    name, notes, pvname, use = [None]*4

class ScanDefs(BaseTable):
    "scandefs table"
    name, notes, text, type, modify_time, last_used_time = [None]*6

class PVs(BaseTable):
    "pv table"
    name, notes, is_monitor = None, None, None

class PVTypes(BaseTable):
    "pvtype table"
    name, notes = None, None

class MonitorValues(BaseTable):
    "monitor PV Values table"
    id, modify_time, value = None, None, None

class Macros(BaseTable):
    "table of pre-defined macros"
    name, notes, arguments, text, output = None, None, None, None, None

class Commands(BaseTable):
    "commands-to-be-executed table"
    command, notes, arguments = None, None, None
    status, status_name = None, None
    request_time, start_time, modify_time = None, None, None
    output_value, output_file, nrepeat = None, None, None
    def __repr__(self):
        name = self.__class__.__name__
        fields = ['%s' % getattr(self, 'command', 'Unknown'),
                  'id=%d' % getattr(self, 'id', 'NOID')]
        return "<%s(%s)>" % (name, ', '.join(fields))

class ScanData(BaseTable):
    notes, pvname, data, units, breakpoints, modify_time = [None]*6

class Instruments(BaseTable):
    "instrument table"
    name, notes = None, None

class Positions(BaseTable):
    "position table"
    pvs, date, name, notes, image = None, None, None, None, None
    instrument, instrument_id = None, None

class Position_PV(BaseTable):
    "position-pv join table"
    name, notes, pv, value = None, None, None, None
    def __repr__(self):
        name = self.__class__.__name__
        fields = ['%s=%s' % (getattr(self, 'pvs_id', '?'),
                             getattr(self, 'value', '?'))]
        return "<%s(%s)>" % (name, ', '.join(fields))

class Instrument_PV(BaseTable):
    "intruemnt-pv join table"
    name, id, instrument, pv, display_order = None, None, None, None, None
    def __repr__(self):
        name = self.__class__.__name__
        fields = ['%s/%s' % (getattr(getattr(self, 'instrument', '?'),'name','?'),
                             getattr(getattr(self, 'pv', '?'), 'name', '?'))]
        return "<%s(%s)>" % (name, ', '.join(fields))

class Instrument_Precommands(BaseTable):
    "instrument precommand table"
    name, notes = None, None

class Instrument_Postcommands(BaseTable):
    "instrument postcommand table"
    name, notes = None, None

def create_scandb(dbname, server='sqlite', create=True, **kws):
    """Create a ScanDB:

    arguments:
    ---------
    dbname    name of database (filename for sqlite server)

    options:
    --------
    server    type of database server ([sqlite], mysql, postgresql)
    host      host serving database   (mysql,postgresql only)
    port      port number for database (mysql,postgresql only)
    user      user name for database (mysql,postgresql only)
    password  password for database (mysql,postgresql only)
    """

    engine  = get_dbengine(dbname, server=server, create=create, **kws)
    metadata =  MetaData(engine)
    print(" --- create ", engine, metadata)
    info = Table('info', metadata,
                 Column('keyname', Text, primary_key=True, unique=True),
                 StrCol('notes'),
                 StrCol('value'),
                 Column('modify_time', DateTime, default=datetime.now),
                 Column('create_time', DateTime, default=datetime.now))

    status  = NamedTable('status', metadata)
    slewpos = NamedTable('slewscanpositioners', metadata, with_use=True,
                            cols=[StrCol('drivepv', size=128),
                                  StrCol('readpv',  size=128),
                                  StrCol('extrapvs') ])

    pos    = NamedTable('scanpositioners', metadata, with_use=True,
                        cols=[StrCol('drivepv', size=128),
                              StrCol('readpv',  size=128),
                              StrCol('extrapvs') ])

    cnts   = NamedTable('scancounters', metadata, with_pv=True, with_use=True)
    det    = NamedTable('scandetectors', metadata, with_pv=True, with_use=True,
                        cols=[StrCol('kind',   size=128),
                              StrCol('options')])

    scans = NamedTable('scandefs', metadata,
                       cols=[StrCol('text'),
                             StrCol('type'),
                             Column('modify_time', DateTime),
                             Column('last_used_time', DateTime)])

    extrapvs = NamedTable('extrapvs', metadata, with_pv=True, with_use=True)

    macros = NamedTable('macros', metadata,
                        cols=[StrCol('arguments'),
                              StrCol('text'),
                              StrCol('output')])

    cmds = NamedTable('commands', metadata, name=False,
                      cols=[StrCol('command'),
                            StrCol('arguments'),
                            PointerCol('status', default=1),
                            IntCol('nrepeat',  default=1),
                            Column('request_time', DateTime,
                                   default=datetime.now),
                            Column('start_time',    DateTime),
                            Column('modify_time',   DateTime,
                                   default=datetime.now),
                            StrCol('output_value'),
                            StrCol('output_file')])

    pvtypes = NamedTable('pvtypes', metadata)
    pv      = NamedTable('pvs', metadata,
                         cols=[PointerCol('pvtypes'),
                               IntCol('is_monitor', default=0)])

    monvals = Table('monitorvalues', metadata,
                    IntCol('id', primary_key=True),
                    PointerCol('pvs'),
                    StrCol('value'),
                    Column('modify_time', DateTime))

    scandata = NamedTable('scandata', metadata, with_pv=True,
                         cols = [PointerCol('commands'),
                                 ArrayCol('data', server=server),
                                 StrCol('units', default=''),
                                 StrCol('breakpoints', default=''),
                                 Column('modify_time', DateTime)])

    instrument = NamedTable('instruments', metadata,
                            cols=[IntCol('show', default=1),
                                  IntCol('display_order', default=0)])

    position  = NamedTable('positions', metadata, name_unique=False,
                           cols=[Column('modify_time', DateTime),
                                 StrCol('image'),
                                 PointerCol('instruments')])

    instrument_precommand = NamedTable('instrument_precommands', metadata,
                                       cols=[IntCol('exec_order'),
                                             PointerCol('commands'),
                                             PointerCol('instruments')])

    instrument_postcommand = NamedTable('instrument_postcommands', metadata,
                                        cols=[IntCol('exec_order'),
                                              PointerCol('commands'),
                                              PointerCol('instruments')])

    instrument_pv = Table('instrument_pv', metadata,
                          IntCol('id', primary_key=True),
                          PointerCol('instruments'),
                          PointerCol('pvs'),
                          IntCol('display_order', default=0))


    position_pv = Table('position_pv', metadata,
                        IntCol('id', primary_key=True),
                        StrCol('notes'),
                        PointerCol('positions'),
                        PointerCol('pvs'),
                        StrCol('value'))

    metadata.create_all()
    session = sessionmaker(bind=engine)()

    # add some initial data:
    scans.insert().execute(name='NULL', text='')

    for name in CMD_STATUS:
        status.insert().execute(name=name)

    for name, notes in PV_TYPES:
        pvtypes.insert().execute(name=name, notes=notes)

    for keyname, value in (("version", "1.0"),
                           ("user_name", ""),
                           ("experiment_id",  ""),
                           ("user_folder",    ""),
                           ("request_abort", "0"),
                           ("request_pause", "0"),
                           ("request_resume", "0"),
                           ("request_killall", "0"),
                           ("request_shutdown", "0") ):
        info.insert().execute(keyname=keyname, value=value)
    session.commit()
    return engine, metadata

def map_scandb(metadata):
    """set up mapping of SQL metadata and classes
    returns two dictionaries, tables and classes
    each with entries
    tables:    {tablename: table instance}
    classes:   {tablename: table class}

    """
    tables = metadata.tables
    classes = {}
    map_props = {}
    keyattrs = {}
    try:
        clear_mappers()
    except:
        logging.exception("error clearing mappers")


    for cls in (Info, Status, PVs, PVTypes, MonitorValues, Macros, ExtraPVs,
                Commands, ScanData, ScanPositioners, ScanCounters,
                ScanDetectors, ScanDefs, SlewScanPositioners, Positions,
                Position_PV, Instruments, Instrument_PV,
                Instrument_Precommands, Instrument_Postcommands):

        name = cls.__name__.lower()
        props = {}
        if name == 'commands':
            props = {'status': relationship(Status)}
        elif name == 'scandata':
            props = {'commands': relationship(Commands)}
        elif name == 'monitorvalues':
            props = {'pv': relationship(PVs)}
        elif name == 'pvtypes':
            props = {'pv': relationship(PVs, backref='pvtypes')}
        elif name == 'instruments':
            props = {'pvs': relationship(PVs,
                                         backref='instruments',
                                         secondary=tables['instrument_pv'])}
        elif name == 'positions':
            props = {'instrument': relationship(Instruments,
                                                backref='positions'),
                     'pvs': relationship(Position_PV)}
        elif name == 'instrument_pv':
            props = {'pv': relationship(PVs),
                     'instrument': relationship(Instruments)}
        elif name == 'position_pv':
            props = {'pv': relationship(PVs)}
        elif name == 'instrument_precommands':
            props = {'instrument': relationship(Instruments,
                                                backref='precommands'),
                     'command': relationship(Commands)}
        elif name == 'instrument_postcommands':
            props = {'instrument': relationship(Instruments,
                                                backref='postcommands'),
                     'command': relationship(Commands)}

        mapper(cls, tables[name], properties=props)
        classes[name] = cls
        map_props[name] = props
        keyattrs[name] = 'name'

    keyattrs['info'] = 'keyname'
    keyattrs['commands'] = 'command'
    keyattrs['position_pv'] = 'id'
    keyattrs['instrument_pv'] = 'id'
    keyattrs['monitovalues'] = 'id'

    # set onupdate and default constraints for several datetime columns
    # note use of ColumnDefault to wrap onpudate/default func
    fnow = ColumnDefault(datetime.now)
    for tname in ('info', 'commands', 'positions','scandefs', 'scandata',
                  'monitorvalues', 'commands'):
        tables[tname].columns['modify_time'].onupdate =  fnow
        tables[tname].columns['modify_time'].default =  fnow

    for tname, cname in (('info', 'create_time'),
                         ('commands', 'request_time'),
                         ('scandefs', 'last_used_time')):
        tables[tname].columns[cname].default = fnow

    return tables, classes, map_props, keyattrs
