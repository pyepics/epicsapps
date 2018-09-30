#!/usr/bin/env python
''' Ion Chamber Current to  Ion Chamber Flux calculation

Closely dependent on Epics Record defined in IonChamber.db

Uses Mucal routine for actual calculation
'''
import time
import os
from math import exp

from epics import Device, caget
from  Mucal import mucal

PIDFILE = '/tmp/ionchamber.pid'

class IonChamber(Device):
    """Epics Device for Ion Chamber Flux Calculation"""
    
    attrs = ('Amp', 'Desc', 'Volts', 'Length', 'AbsPercent',
             'Gas', 'Current', 'FluxAbs', 'FluxOut', 'EnergyPV',
             'Energy', 'TimeStamp' )

    gasMapping = {'He': 2, 'N2': 7, 'Ar': 18, 'Kr': 36}
    
    def __init__(self, prefix='13XRM:ION:'):
        Device.__init__(self, prefix, attrs=self.attrs)

    def calculate(self):
        'the actual calculation'
        gas       = self.get('Gas', as_string=True)
        length    = self.get('Length')

        energy_pv = self.get('EnergyPV')        
        volt_pv   = self.get('Volts')
        amp_pv    = self.get('Amp')
        ampn_pv   = '%ssens_num'  % amp_pv
        ampu_pv   = '%ssens_unit' % amp_pv
        
        energy    = caget(energy_pv)
        if energy is None:
            energy = 9090.9090
            
        voltage   = caget(volt_pv)
        amp_num   = float(caget(ampn_pv, as_string=True))
        amp_unit  = int(caget(ampu_pv) )
        
        # this is fairly magic:
        #  amp_unit = 0 for pA/V, 1 for nA/V, 2 for microA/V, 3 for mA/V
        #  Thus, 10 ** (3*amp_unit-12)  !!
        sensitivity = amp_num * 10**(3*amp_unit-12)
        current     = 1.e6 * abs(voltage) * sensitivity
        flux_abs    = 2e14 * current / max(energy, 1000.0)

        kev = 0.001 * energy
        if gas in self.gasMapping:
            iz_gas = self.gasMapping[gas]
            mu = mucal(z=iz_gas, energy = kev)['mu']
        elif gas.lower().startswith('air'):
            m_n2 = mucal(z=7, energy=kev)['mu']
            m_o2 = mucal(z=8, energy=kev)['mu']
            m_ar = mucal(z=18, energy=kev)['mu']
            mu   = 0.78*m_n2 + 0.21 * m_o2  + 0.01 * m_ar

        frac  = (1-exp(-mu*length))
        flux_trans =  flux_abs*(1-frac)/frac

        self.put('Energy',    energy)

        self.put('AbsPercent', 100.0*frac)
        self.put('Current',   "%12.3g" % current)
        self.put('FluxAbs',   "%12.3e" % flux_abs)
        self.put('FluxOut',   "%12.3e" % flux_trans)

        self.put('TimeStamp',
                 time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()))

    def run(self):
        while True:
            self.calculate()
            time.sleep(0.25)

def start_ionchamber(prefix='13XRM:ION:'):    
    """ save pid for later killing """
    fpid = open(PIDFILE, 'w')
    fpid.write("%d\n" % os.getpid() )
    fpid.close()

    ion = IonChamber(prefix=prefix)
    ion.run()
 
def get_lastupdate(prefix='13XRM:ION:'):
    xtime = caget("%sTimeStamp" % prefix)
    xtime = xtime.strip()
    if len(xtime) > 1:
        try:
            for i in (':','-'):
                xtime = xtime.replace(i, ' ')
            print 'x: ', xtime, xtime.split()
            xtime = [int(i) for i in xtime.split()]
            ltime = list(time.localtime())
            for i in range(len(xtime)):
                ltime[i] = xtime[i]
            return time.mktime(ltime)
        except:
            pass
    return time.time() - 100000.

def kill_old_process():
    try:
        finp = open(pidfile)
        pid = int(finp.readlines()[0][:-1])
        finp.close()
        cmd = "kill -9 %d" % pid
        os.system(cmd)
        print ' killing pid=', pid, ' at ', time.ctime()
    except:
        pass
    
if __name__ == '__main__':
    oldtime = get_lastupdate()
    print oldtime, time.time()
    if abs(time.time() - oldtime) > 5.0:
        kill_old_process()
        time.sleep(1.0)
        start()
    else:
        print 'IonChamber running OK at ', time.ctime()
