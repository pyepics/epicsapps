#!/usr/bin/env python 

import sys
import os
import time
from epics import PV, Device

burt_command0 = 'burt -l /somefile'
burt_command0 = 'ls -l'

PVFILE1 = 'PVLIST.TXT'

class Collector:
    attrs = ('status', 'mode', 'request',
             'host', 'folder', 'filename', 'fileext', 'format',
             'message', 'timestamp', 'unixtime',
             'arg1', 'arg2', 'arg3', 'counttime')
    
    def __init__(self, prefix):
        self.device = Device(prefix, delim=':', attrs=self.attrs)

        time.sleep(0.1)
        self.read_pvfile()
        
        # self.device.add_callback('request', self.onRequest)
    def onRequest(self,  pvname=None, value=None, **kws):
        print 'Request changed to ', value

    def read_pvfile(self):
        try:
            f = open(PVFILE1, 'r')
            lines = f.readlines()
            f.close()
        except:
            self.env_pvs = None
            return
        self.env_pvs = []
        for i in lines:
            i = i[:-1].strip()
            if len(i)<2: continue
            words = i.split()
            pvname = words.pop(0)
            desc = ' '.join(words).strip()
            pv = PV(pvname)
            pv.get()
            if pv:
                if desc == '': desc = pv.desc
                self.env_pvs.append( (pv,desc) )
        print 'Will use %i  PVs from %s' % (len(self.env_pvs), PVFILE1)

        
    def setTime(self, ts=None):
        if ts is None:
            ts = time.time()
        self.device.timestamp = time.ctime(ts)  # self.device.timestamp = Py:EXT:timestamp
        self.device.unixtime  = ts

    def setMessage(self, msg):
        self.device.message = msg

    def setStatus(self, status):
        self.device.status  =status

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

        # Write to Master Mapping file:
        # maybe add PVs to epics py_example.db for
        # sampleX, sampleY, sampleName
        mapfile = open(MAPFILENAME, 'a')
        mapfile.write("%s , %s , %s  : %s\n" % (xpos, ypos, samplename, filename))
        mapfile.close()

        #
        # put real commands here
        if self.device.mode == 0:
            self.setMessage(' writing (Mode 0)....')
            time.sleep(2.0)            
            os.system(burt_command0)
            # newval = epics.caget(SOME_OTHER_PV)

            # write data from PVLIST
            try:
                fout = open(filename, 'w')
            except:
                print 'could not open file %s for writing ' % filename
            for pv, desc in self.env_pvs:
                try:
                    fout.write('%s || %s || %s \n' % (pv.pvname,pv.char_value,desc))
                except:
                    pass
            fout.close()
            
            self.setMessage(' wrote %s ' % filename)
            #
            
        elif self.device.mode == 1:
            self.setMessage(' writing (Mode 1)....')            
            time.sleep(3.0)
        self.setMessage(' cleaning up ....')
        time.sleep(1.0)

    def run(self):
        self.setMessage('Starting...')
        self.device.request = 0   # == 'caput Py:EXT:request 0'
        self.setTime()
        time.sleep(0.1)
        while True:
            time.sleep(0.1)
            self.setTime()
            if self.device.request == 1: # start # 'caget Py:EXT:request =? 1'
                self.setMessage(' Starting ....')
                self.setStatus(1)
                if self.device.mode == 0: #  Py:EXT:mode
                    self.write_file()

                elif self.device.mode == 1: #  Py:EXT:mode
                    # self.read_mode0_file()
                    # self.write_something_else()
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
