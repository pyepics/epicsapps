#!/usr/bin/python

import sys
sys.path.insert(0, '/Users/epics/Codes/epicsapps/IonChamber')

from ionchamber import start_ionchamber, get_lastupdate, kill_old_process

import time

prefix = '13XRM:ION:'
if len(sys.argv) > 1:
    prefix = sys.argv[1]

last_time = get_lastupdate(prefix=prefix)
if abs(time.time() - last_time) > 5.0:
    kill_old_process()
    time.sleep(1.0)
    start_ionchamber(prefix=prefix)
else:
    print('IonChamber running OK at ', time.ctime())
