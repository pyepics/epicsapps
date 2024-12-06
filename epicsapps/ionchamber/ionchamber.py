#!/usr/bin/env python
''' Ion Chamber Current to  Ion Chamber Flux calculation

Closely dependent on Epics Record defined in IonChamber.db

Uses xraydb routine for actual calculation
'''
import time
from datetime import datetime
import os
from numpy import exp
from pyshortcuts import gformat
from epics import Device, caget, get_pv
from xraydb import ionchamber_fluxes

SUNITS = {'pA/V': 1.e-12, 'nA/V': 1.e-9, 'uA/V': 1.e-6, 'mA/V': 1.e-3}

class IonChamber(Device):
    """Epics Device for Ion Chamber Flux Calculation

    usage
    from epicsapps.ionchamber import IonChamber
    ionc = IonChamber(prefix='XX:IONC:', sleeptime=0.5)
    ionc.run()
    """
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

        amp_val  = float(caget(ampn_pv, as_string=True))
        voltage =  caget(volt_pv)
        energy   = caget(energy_pv)
        if energy is None or energy < 100.0:
            energy = 100.0

        amp_unit = caget(ampu_pv, as_string=True)
        cur_units = 1.e6 * SUNITS.get(amp_unit, 1.e-6) # to give uAmp
        current  = voltage * amp_val * cur_units

        flux = ionchamber_fluxes({gas: 1.0}, volts=voltage,
                                 length=length, energy=energy,
                                 sensitivity=amp_val,
                                 sensitivity_units=amp_unit)

        now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        frac_abs = 1.0-(flux.transmitted/(flux.incident+0.1))
        flux_abs = flux.incident - flux.transmitted
        flux_out = flux.transmitted
        self.put('Energy',     energy)
        self.put('AbsPercent', f'{100*frac_abs:.2f}')
        self.put('Current',    gformat(current, length=6))
        self.put('FluxAbs',    gformat(flux_abs, length=10))
        self.put('FluxOut',    gformat(flux_out, length=10))
        self.put('TimeStamp',  now)

    def run(self, sleeptime=0.5):
        while True:
            self.calculate()
            time.sleep(sleeptime)


def start_ionchamber(prefix='XX:ION:', sleeptime=0.5):
    """start ionchamber if not already running
    Arguments
    ---------
    prefix     prefix for IonChamber EPICS record
    sleeptime  sleep time when running.
    """
    ionc = IonChamber(prefix=prefix)

    time.sleep(0.1)
    now  = datetime.now()
    try:
        last_event = datetime.fromisoformat(ionc.TimeStamp)
    except:
        last_event = None

    if last_event is None or (now-last_event).seconds > 5:
        ionc.run(sleeptime=0.5)
    else:
        print(f'IonChamber {prefix} is running, last update at {last_event}')
