#!/usr/bin/env python

"""
connectors for scandb
"""

from sqlalchemy import create_engine
from sqlalchemy.pool import SingletonThreadPool

# needed for py2exe?
from sqlalchemy.dialects import sqlite, mysql, postgresql

def hasdb_pg(dbname, create=False,
             user='', password='', host='', port=5432):
    """
    return whether a database is known to the postgresql server,
    optionally creating (but leaving it empty) said database.

    Arguments
    ---------
      dbname    name of database
      create    bool (default False) whether to create new db
      user      str (default '') user name
      password  str (default '') user password
      host      str (default '') host name
      port      int (default 5432) port number

    Returns
    -------
      bool      whether db is available
    """
    dbname = dbname.lower()
    conn_str= 'postgresql://%s:%s@%s:%i/%s'
    engine = create_engine(conn_str % (user, password,
                                       host, port, 'postgres'))
    conn = engine.connect()
    conn.execution_options(autocommit=True)
    conn.execute("commit")

    query = "select datname from pg_database"
    dbs = [i[0] for i in conn.execute(query).fetchall()]
    if create and dbname not in dbs:
        conn.execute("create database %s" % dbname)
        conn.execute("commit")
    dbs = [i[0] for i in conn.execute(query).fetchall()]
    conn.close()
    return dbname in dbs

def get_dbengine(dbname, server='sqlite', create=False,
                user='', password='',  host='', port=None):
    """create databse engine

    Arguments
    ---------
      dbname    name of database
      server    str (default 'sqlite')
                   one of 'sqlite', 'mysql', or 'postgres'
      create    bool (default False) whether to create new db
      user      str (default '') user name
      password  str (default '') user password
      host      str (default '') host name
      port      int              port number
                    default port = 5432 for postgres, 3306 for mysql

    Returns
    -------
      sqlalchemy engine

    """
    if server == 'sqlite':
        return create_engine('sqlite:///%s' % (dbname),
                             poolclass=SingletonThreadPool)
    else:
        if server.startswith('my'):
            conn_str= 'mysql+mysqldb://%s:%s@%s:%i/%s'
            if port is None:
                port = 3306
        else:
            conn_str= 'postgresql://%s:%s@%s:%i/%s'
            if port is None:
                port = 5432
            hasdb = hasdb_pg(dbname, create=create, user=user,
                             password=password, host=host, port=port)
        return create_engine(conn_str % (user, password, host, port, dbname))
