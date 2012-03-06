#!/usr/bin/python

import wx
import sys

if (len(sys.argv) > 1 and sys.argv[1].startswith('-d')):
    from lib import EpicsMotorSetupApp
else:
    from epicsapps.motorsetup import EpicsMotorSetupApp

if __name__ == '__main__':
    server = 'sqlite'
    dbname = None # 'Motors.mdb'
    
    #dbname = 'GSECARS_Motors.mdb'
    #server='mysql'
    app = EpicsMotorSetupApp(dbname=dbname, server=server)
    app.MainLoop()


