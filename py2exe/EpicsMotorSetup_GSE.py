#!/usr/bin/python

import wx
import sys

from epicsapps.motorsetup import EpicsMotorSetupApp

app = EpicsMotorSetupApp(dbname=None, server='mysql')
app.MainLoop()
