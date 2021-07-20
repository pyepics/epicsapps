#!/usr/bin/env python
''' Ion Chamber Current to  Ion Chamber Flux calculation

Closely dependent on Epics Record defined in IonChamber.db

Uses xraydb routine for actual calculation
'''
import time
import os
from numpy import exp

from epics import Device, caget, get_pv
from xraydb import material_mu

PIDFILE = '/tmp/ionchamber.pid'

# effective ionization potentials, energy in eV per ion pair, from Knoll

ion_potentials = {'argon': 26.4, 'helium': 41.3, 'hydrogen': 36.5,
                  'nitrogren': 34.8, 'air': 33.8, 'oxygen': 30.8,
                  'methane': 27.3, 'Ar': 26.4, 'He': 41.3,
                  'H2': 36.5, 'N2': 34.8, 'O2': 30.8, 'CO4': 27.3}

# current amp sensitivities:
sensitivities = {'pA/V': 1.e-12, 'nA/V': 1.e-9, 'uA/V': 1.e-6, 'mA/V': 1.e-3}

QCHARGE = 1.6021766208e-19

class IonChamber(Device):
    """Epics Device for Ion Chamber Flux Calculation"""

    attrs = ('Amp', 'Desc', 'Volts', 'Length', 'AbsPercent', 'Gas', 'Current',
             'FluxAbs', 'FluxOut', 'Volts2Flux', 'EnergyPV', 'Energy',
             'TimeStamp')

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
        if energy is None or energy < 100.0:
            energy = 100.0

        voltage   = caget(volt_pv)
        amp_num   = float(caget(ampn_pv, as_string=True))
        amp_unit  = caget(ampu_pv, as_string=True)
        sensitivity = amp_num * sensitivities.get(amp_unit, 1.e-6)
        current     = abs(voltage) * sensitivity

        # print("Current ", current, type(current))
        # print(voltage, energy, amp_num, amp_unit, sensitivity)

        # Ion Chamber flux to current (energies in eV):
        #     Current = flux_photo * (energy/ion_pot) * (2*q)
        # where q = 1.6e-19 Coulombs.  With ion_pot = 32 eV
        #   current = flux_photo * energy * 1.e-20
        #   photo_flux = 1.e20 * current / energy

        ion_pot = ion_potentials.get(gas, 32.0)/(2*QCHARGE*energy)
        flux_photo = current * ion_pot
        if gas == 'N2':
            gas = 'nitrogen'

        # note on Photo v Total attenuation:
        # the current is from the photo-electric cross-section, so that
        #   flux_photo = flux_in * [1 - exp(-t*mu_photo)]
        # while total attenuation means
        #   flux_out = flux_in * exp(-t*mu_total)
        # so that
        #   flux_out = flux_photo * exp(-t*mu_total) / [1 - exp(-t*mu_photo)]

        etmu_photo = exp(-length*material_mu(gas, energy=energy, kind='photo'))
        etmu_total = exp(-length*material_mu(gas, energy=energy, kind='total'))

        photo2fluxout = etmu_total/(1-etmu_photo)
        flux_out = flux_photo * photo2fluxout

        v2flux = sensitivity * ion_pot * photo2fluxout
        self.put('Energy',    energy)
        self.put('AbsPercent', 100.0*((1-etmu_total)/etmu_total))
        self.put('Current',    "%.6g" % (current*1.e6)) # report current in microAmp
        self.put('FluxAbs',    "%.6g" % flux_photo)
        self.put('FluxOut',    "%.6g" % flux_out)
        self.put('Volts2Flux', "%.6g" % v2flux)
        self.put('TimeStamp', time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()))

    def run(self):
        time.sleep(0.25)
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
