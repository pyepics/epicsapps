#!/usr/bin/env python
''' Ion Chamber Current to  Ion Chamber Flux calculation

Closely dependent on Epics Record defined in IonChamber.db

Uses xraydb routine for actual calculation
'''
import time
import os
from numpy import exp
from pyshortcuts import gformat
from epics import Device, caget, get_pv
from xraydb import ionchamber_fluxes

PIDFILE = '/tmp/ionchamber.pid'

# # current amp sensitivities:
SUNITS = {'pA/V': 1.e-12, 'nA/V': 1.e-9, 'uA/V': 1.e-6, 'mA/V': 1.e-3}

class IonChamber(Device):
    """Epics Device for Ion Chamber Flux Calculation"""
    attrs = ('Amp', 'Desc', 'Volts', 'Length', 'AbsPercent', 'Gas', 'Current',
             'FluxAbs', 'FluxOut', 'Volts2Flux', 'EnergyPV', 'Energy',
             'TimeStamp')

    def __init__(self, prefix='13XRM:ION:'):
        Device.__init__(self, prefix, attrs=self.attrs)

    def calculate(self):
        'the actual calculation'
        gas      = self.get('Gas', as_string=True)
        length   = self.get('Length')
        energy_pv = self.get('EnergyPV')
        volt_pv  = self.get('Volts')
        amp_pv   = self.get('Amp')
        ampn_pv  = '%ssens_num'  % amp_pv
        ampu_pv  = '%ssens_unit' % amp_pv

        energy   = caget(energy_pv)
        if energy is None or energy < 100.0:
            energy = 100.0

        voltage  = caget(volt_pv)
        amp_val  = float(caget(ampn_pv, as_string=True))
        amp_unit = caget(ampu_pv, as_string=True)
        current  = voltage * amp_val * SUNITS.get(amp_unit, 1.e-6)

        flux = ionchamber_fluxes({gas: 1.0}, volts=voltage,
                                 length=length, energy=energy,
                                 sensitivity=amp_val,
                                 sensitivity_units=amp_unit)

        now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()
        frac_absorbed = 1.0-(flux.transmitted/(flux.incident+0.1))
        self.put('Energy',     energy)
        self.put('AbsPercent', f'{100*frac_absorbed:.2f}')
        self.put('Current',    gformat(current*1.e6, length=6))
        self.put('FluxAbs',    gformat(flux.photo+flux.incoherent, length=10))
        self.put('FluxOut',    gformat(flux.transmitted, length=10))
        self.put('TimeStamp',  now)

    def run(self):
        time.sleep(0.25)
        while True:
            self.calculate()
            time.sleep(0.5)

def start_ionchamber(prefix='13XRM:ION:'):
    """ save pid for later killing """
    fpid = open(PIDFILE, 'w')
    fpid.write("%d\n" % os.getpid() )
    fpid.close()
    ion = IonChamber(prefix=prefix)
    ion.run()

def get_lastupdate(prefix='13XRM:ION:'):
    ts_pv = get_pv("%sTimeStamp" % prefix)
    time.sleep(0.1)
    xtime = ts_pv.get().strip()
    if len(xtime) > 1:
        for i in (':','-'):
            xtime = xtime.replace(i, ' ')
        xtime = [int(i) for i in xtime.split()]
        ltime = list(time.localtime())
        for i in range(len(xtime)):
            ltime[i] = xtime[i]
        return time.mktime(tuple(ltime))
    return time.time() - 100000.

def kill_old_process():
    try:
        finp = open(pidfile)
        pid = int(finp.readlines()[0][:-1])
        finp.close()
    except:
        return
    cmd = "kill -9 %d" % pid
    os.system(cmd)
    print(' killing pid=', pid, ' at ', time.ctime())

if __name__ == '__main__':
    oldtime = get_lastupdate()
    if abs(time.time() - oldtime) > 5.0:
        kill_old_process()
        time.sleep(1.0)
        start()
    else:
        print('IonChamber running OK at ', time.ctime())
