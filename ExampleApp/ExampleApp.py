#!/usr/bin/env python 

import sys
import os
import time
from epics import PV, Device

class Collector:
    attrs = ('status', 'mode', 'request',
             'host', 'folder', 'filename', 'fileext', 'format',
             'message', 'timestamp', 'unixtime',
             'arg1', 'arg2', 'arg3', 'counttime')
    
    def __init__(self, prefix):
        self.device = Device(prefix, delim=':', attrs=self.attrs)

        time.sleep(0.1)
        
        self.device.add_callback('request', self.onRequest)
        
    def setTime(self, ts=None):
        if ts is None:
            ts = time.time()
        self.device.timestamp = time.ctime(ts)
        self.device.unixtime  = ts

    def setMessage(self, msg):
        self.device.message = msg

    def setStatus(self, status):
        self.device.status  =status

    def onRequest(self,  pvname=None, value=None, **kws):
        print 'Request changed to ', value

    def write_file(self):
        host     = self.device.get('host', as_string=True)
        folder   = self.device.get('folder', as_string=True)
        filename = self.device.get('filename', as_string=True)
        fileext  = self.device.get('fileext', as_string=True)
        format   = self.device.get('format', as_string=True)
        if format == '':
            format = '%s.%s'
            
        filename = format % (filename, fileext)
        filename = os.path.join(host, folder, filename)

        print 'Write to File: ', filename
        print 'Mode =',  self.device.mode
        self.setMessage(' writing ....')
        time.sleep(2.0)
        self.setMessage(' cleaning up ....')
        time.sleep(1.0)

    def run(self):
        self.setMessage('Starting...')
        self.device.request = 0
        self.setTime()
        time.sleep(0.1)
        while True:
            time.sleep(0.1)
            self.setTime()
            if self.device.request == 1: # start
                self.setMessage(' Starting ....')
                self.setStatus(1)
                self.write_file()
                
                self.setMessage(' Done.')                    
                self.setStatus(0)
                self.device.request = 0
            elif self.device.request == 0: # stop
                pass
            elif self.device.request == 2: # pause
                print 'pause not implemented'
            elif self.device.request == 3: # resume
                print 'resume not implemented'
            elif self.device.request == 4: # shutdown
                break

        self.setMessage(' Shutting down ....')
        self.setStatus(3)
        self.setTime(0)

if __name__ == '__main__':
    prefix = 'Py:EXT'
    if len(sys.argv) > 1:
        prefix = sys.argv[1]

    c = Collector(prefix)
    c.run()
