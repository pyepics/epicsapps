#!/usr/bin/python

import IonChamber
import time

last_time = IonChamber.get_lastupdate()
if abs(time.time() - last_time) > 5.0:
    IonChamber.kill_old_process()
    time.sleep(1.0)
    IonChamber.start()
else:
    print 'IonChamber running OK at ', time.ctime()

