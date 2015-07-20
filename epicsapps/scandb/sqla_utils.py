#!/usr/bin/env python

"""
wrappers for basic SQLAlchemy column types
"""

from sqlalchemy import (Table, Column, ColumnDefault, ForeignKey,
                        Integer, Float, String, Text, DateTime)

from sqlalchemy.dialects import sqlite, mysql, postgresql

def IntCol(name, **kws):
    return Column(name, Integer, **kws)

def ArrayCol(name,  server='sqlite', **kws):
    ArrayType = Text
    if server.startswith('post'):
        ArrayType = postgresql.ARRAY(Float)
    return Column(name, ArrayType, **kws)

def StrCol(name, size=None, **kws):
    val = Text
    if size is not None:
        val = String(size)
    return Column(name, val, **kws)

def PointerCol(name, other=None, keyid='id', **kws):
    if other is None:
        other = name
    return Column("%s_%s" % (name, keyid), None,
                  ForeignKey('%s.%s' % (other, keyid)), **kws)

def NamedTable(tablename, metadata, keyid='id', nameid='name',
               name_unique=True, name=True, notes=True, with_pv=False,
               with_use=False, cols=None):

    args  = [Column(keyid, Integer, primary_key=True)]

    if name:
        args.append(StrCol(nameid, size=512, nullable=False,
                           unique=name_unique))
    if notes:
        args.append(StrCol('notes'))
    if with_pv:
        args.append(StrCol('pvname', size=128))
    if with_use:
        args.append(IntCol('use', default=1))
    if cols is not None:
        args.extend(cols)
    return Table(tablename, metadata, *args)

class BaseTable(object):
    "generic class to encapsulate SQLAlchemy table"
    def __repr__(self):
        name = self.__class__.__name__
        fields = ['%s' % getattr(self, 'name', 'UNNAMED'),
                  'id=%s' % repr(getattr(self, 'id', 'NOID'))]
        return "<%s(%s)>" % (name, ', '.join(fields))
