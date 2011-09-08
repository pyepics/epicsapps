#!/usr/bin/python2.3

from IonChamber import *
kill_old_process()
time.sleep(0.1)
daemonize_with_pidfile(main, pidfile=pidfile)
