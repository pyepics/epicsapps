#!/usr/bin/env python 

# from  EpicsCA import PV,pend_event, pend_io, connect_all, caget
from epics import PV , caget
import sys
import os
import time
import numpy

# env_pvfile = '/home/epics/work/XRF_Collect/xrf_environment.txt'

basename = '13XRM:XRF:'
env_pvfile = 'XRM_XMAP_PVS.DAT'

# List of all allowed states for finite automaton
StateList = ('OFFLINE', 'IDLE','START_DETECTOR',
             'DONE', 'COUNTING',
             'NEEDS_WRITE', 'NO_WRITE', 'WRITING')

class Container:   pass
state = Container()
for s in StateList:   setattr(state, s, s)

def increment_filename(old_file):
    """
    Increments the file extension if it is numeric.  It preserves the number of
    characters in the extension.
    
    Examples:
    print increment_filename('test.001')
    test.002
    print increment_filename('test')
    test
    print increment_filename('file.1')
    file.2
    """
    dot = old_file.rfind('.')
    if (dot == -1): return old_file
    if (dot+1 == len(old_file)): return old_file
    
    ext = old_file[dot+1:]
    file = old_file[0:dot+1]
    nc = str(len(ext))
    try:
       ext = int(ext)+1      # Convert to number, add one, catch error
       format = '%' + nc + '.' + nc + 'd'
       ext = (format % ext)
       new_file = file + ext
       return new_file
    except:
       return old_file

        
def write_medfile(med_name, data, filename, env_pvs = None):
    """
    Writes mca spectra to file,
    """
    try:
        fp = open(filename, 'w')
    except IOError:
        return False
    nchan, nelem = data.shape

    fp.write('VERSION:    3.1\n')
    fp.write('ELEMENTS:   %i\n' % nelem)
    fp.write('DATE:       %s\n' % time.ctime())
    fp.write('CHANNELS:   %i\n' % nchan)
  
    mcas = ["%smca%i" %  (med_name,i+1) for i in range(nelem)]

    for key,suff in (('REAL_TIME','ERTM'),('LIVE_TIME','ELTM'),
                     ('CAL_OFFSET','CALO'),('CAL_SLOPE','CALS'),
                     ('CAL_QUAD','CALQ'),  ('TWO_THETA','TTH')):
        s = ["%s: "  % key]
        for mca in mcas:
            xpv = "%s.%s" % (mca,suff)
            xval = caget(xpv, as_string=True)
            s.append( xval)
        fp.write("%s\n" % ' '.join(s))

    # look up RIOS:
    roi_template ="""ROI_%i_LEFT:   %s
ROI_%i_RIGHT:  %s
ROI_%i_LABEL:  %s &
"""
    rois = []    
    total_rois = []
    look_for_rois = True
    i = -1
    while look_for_rois:
        i = i + 1
        look_for_rois = (i <= 32)
        names = []
        lo    = []
        hi    = []

        for mca in mcas:
            try:
                name = caget('%s.R%iNM'  % (mca,i)).strip()
                if name == '' or name is None:
                    look_for_rois = False
                    break
            except:
                look_for_rois = False
                break
            names.append(name)
            lo.append( caget('%s.R%iLO'  % (mca,i), as_string=True))
            hi.append( caget('%s.R%iHI'  % (mca,i), as_string=True))

        # print 'ROIS: ', names,  lo, hi
        if len(lo)>0:
            slo = ' '.join(lo)
            shi = ' '.join(hi)
            snm = ' & '.join(names) 
            rois.append((i,slo,shi,snm))
        else:
            look_for_rois = False

    for m in mcas:
        total_rois.append("%i" % len(rois))
    fp.write('ROIS:   %s\n' % ' '.join(total_rois))
    for r in rois:
        i,lo,hi,name = r
        fp.write(roi_template %(i,lo,i,hi,i,name))
        
    # Environment??
    if env_pvs is not None:
        for pv,desc in env_pvs:
            try:
                fp.write('ENVIRONMENT: %s="%s" (%s)\n' % (pv.pvname,pv.char_value,desc))
            except:
                pass
            
    fp.write('DATA:\n')
    for d in data:
        fp.write("%s\n" % " ".join(['%i' % i for i in d]))
    fp.close()
    return True

def connect_to_mca_pvs(med_name,nelem=4):
    mcas = ["%smca%i" %  (med_name,i+1) for i in range(nelem)]

    for key,suff in (('REAL_TIME','ERTM'),('LIVE_TIME','ELTM'),
                     ('CAL_OFFSET','CALO'),('CAL_SLOPE','CALS'),
                     ('CAL_QUAD','CALQ'),  ('TWO_THETA','TTH')):
        for mca in mcas:
            x = PV("%s.%s" % (mca,suff))

    i = 0
    look_for_rois = True
    while look_for_rois:
        i = i + 1
        look_for_rois = (i < 32)
        for mca in mcas:
            try:
                x = PV('%s.R%iNM'  % (mca,i))
                val = x.get()
                if val == '' or val is None:
                    look_for_rois = False
                    break
            except:
                look_for_rois = False                
                break
            lo = PV('%s.R%iLO'  % (mca,i))
            hi = PV('%s.R%iHI'  % (mca,i))

    return i
        

class MED_Collector:
    def __init__(self,prefix=basename,med='13SDD1:',nelem=4,env_pvfile=env_pvfile):
        class pvs:        pass
        self.state = state.OFFLINE

        self.med_name = med
        self.nelem    = nelem
        connect_to_mca_pvs(med,nelem)

        self.pv = pvs()
        self.med = pvs()
        self.med.start   = PV("%sEraseStart" % med)
        self.med.ctime   = PV("%sPresetReal" % med)
        self.med.status  = PV("%sAcquiring"  % med)
        self.med.presetmode = PV("%sPresetMode"  % med)

        self.pv.status = PV("%sStatus"   % prefix)
        self.pv.mode   = PV("%sMode"     % prefix)  
        self.pv.ctime  = PV("%sCountTime"% prefix) 
        self.pv.req    = PV("%sRequest"  % prefix)
        self.pv.host   = PV("%shost"     % prefix) 
        self.pv.dir    = PV("%sdir"      % prefix)
        self.pv.subdir = PV("%ssubdir"   % prefix) 
        self.pv.base   = PV("%sfilebase" % prefix) 
        self.pv.format = PV("%sformat"   % prefix) 
        self.pv.ext    = PV("%sfileext"  % prefix) 
        self.pv.msg    = PV("%sMSG"      % prefix)  
        self.pv.tstamp = PV("%sTSTAMP"   % prefix)
        self.pv.unixts = PV("%sUNIXTS"   % prefix) 

        time.sleep(0.1)
        
        self.pv.req.add_callback(self.onRequest)
        self.pv.mode.add_callback(self.onModeChange)
        self.med.status.add_callback(self.onDetectorState)
        
        self.automode = self.pv.mode.get()
        self.manual_collection = False
        
        self.datafile = 'Temp File'
        self.env_pvs = None
        self.read_envfile(env_pvfile)

        self.mcas = []
        for i in range(nelem):
            m  = PV( "%smca%i.VAL" % (self.med_name,i+1))
            m.get()
            self.mcas.append(m)

        self.state = state.IDLE
        
    def read_envfile(self,fname):
        print 'reading environmental variables form ', fname
        try:
            f = open(fname,'r')
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
        print 'Will use %i environmental PVs' % len(self.env_pvs)
        
            
    def onModeChange(self,pvname=None, value=None, **kw):
        if pvname is None: 
            return
        self.automode = value
        
    def onRequest(self,pvname=None, value=None, **kw):
        if pvname is None: return
        if value == 1:
            self.state = state.START_DETECTOR
            self.manual_collection = True
        else:
            self.state = state.DONE
            
    def onDetectorState(self,pvname=None, value=None, **kw):
        if pvname is None: return
        if value == 1:
            self.state = state.COUNTING
        elif (self.automode == 1 or self.manual_collection):
            self.state = state.NEEDS_WRITE
            self.manual_collection = False
        else:
            self.state = state.NO_WRITE
            
    def write_file(self):
        host = self.pv.host.get(as_string=True)
        dir  = self.pv.dir.get(as_string=True)
        dir2 = self.pv.subdir.get(as_string=True)
        base = self.pv.base.get(as_string=True)
        fmt  = self.pv.format.get().strip()
        ext  = int(self.pv.ext.get())
        data = [m.get() for m in self.mcas]

        time.sleep(0.1)


        # read (that is, copy) MCA data into a data array)
        med_data  = numpy.array(data).transpose()

        if not host.startswith('/'):  host = "/%s" % host
        try:
            folder = "%s/%s/%s" % (host,dir,dir2)
            folder = folder.replace('//','/')
        except:
            self.pv.msg.put( 'Not Saved: no folder %s' % folder)
            return

        if not os.path.isdir(folder):
            try:
                os.makedirs(folder)
            except:
                pass
        try:
            fname = fmt % (base,ext)
            fname = self.datafile = os.path.join(folder,fname)
        except:        
            fname = increment_filename(fname)

        worked = write_medfile(self.med_name, med_data, fname,
                               env_pvs = self.env_pvs)

        if worked:
            self.pv.msg.put('Wrote %s' % fname)
        else:
            self.pv.msg.put('Could Not write %s' % fname)

        self.pv.ext.put("%.3i" % (ext+1))
        time.sleep(0.1)
        
    def run(self):
        self.pv.status.put(0)
        self.pv.req.put(0)
        self.pv.msg.put('Ready ')
        time.sleep(0.1)
        while True:
            try:
                time.sleep(0.05)
                if self.state == state.START_DETECTOR:
                    self.pv.msg.put( 'Turning detector on...')
                    self.med.presetmode.put(1)
                    self.med.start.put(1)
                    
                elif self.state == state.NEEDS_WRITE:
                    self.pv.msg.put( 'Writing ...')
                    self.pv.status.put(2)
                    self.write_file()

                    self.pv.req.put(0)
                    self.state = state.DONE
                    
                elif self.state == state.NO_WRITE:
                    self.pv.msg.put( 'Spectra Not Saved ...')
                    self.state = state.IDLE

                elif self.state == state.COUNTING:
                    self.pv.msg.put( 'Collecting spectra')
                    self.pv.status.put(1)

                elif self.state == state.DONE:
                    self.pv.req.put(0)
                    self.state = state.IDLE
                    
                elif self.state == state.IDLE:
                    self.pv.status.put(0)

                self.pv.tstamp.put(time.ctime())
                self.pv.unixts.put(time.time())
                
            except KeyboardInterrupt:
                self.pv.tstamp.put(' ')
                self.pv.msg.put('OFFLINE')
                self.pv.status.put(3)
                sys.exit()
                
if __name__ == '__main__':
    x = MED_Collector()
    x.run()
