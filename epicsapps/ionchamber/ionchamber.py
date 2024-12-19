#!/usr/bin/env python
''' Ion Chamber Current to  Ion Chamber Flux calculation

Closely dependent on Epics Record defined in IonChamber.db

Uses xraydb routine for actual calculation
'''
import time
import os
import json
from datetime import datetime
import numpy as np
from scipy.interpolate import CubicSpline

from pyshortcuts import gformat, isotime
from epics import Device, caget, get_pv
from xraydb import get_xraydb, get_material, chemparse, ionchamber_fluxes
from xraydb.utils import elam_spline, QCHARGE

SUNITS = {'pA/V': 1.e-12, 'nA/V': 1.e-9, 'uA/V': 1.e-6, 'mA/V': 1.e-3}

def index_of(array, value):
    if value < min(array):
        return 0
    return max(np.where(array<=value)[0])

def js2array(x):
    return np.array(json.loads(x))


class IonChamberDevice(Device):
    """Epics Device for Ion Chamber, used in flux calculations
    """
    attrs = ('AmpPV', 'VoltPV', 'EnergyPV', 'Energy', 'Volts', 'Desc',
             'Length', 'Gas', 'Current', 'FluxAbs', 'FluxOut', 'FluxOutS',
             'AbsPercent', 'TimeStamp')

    def __init__(self, prefix='13XRM:ION1:'):
        Device.__init__(self, prefix, attrs=self.attrs)
        time.sleep(0.1)
        message = f"IonChamber {prefix} connected."
        unconnected = []
        for x in self._pvs.values():
            if not x.wait_for_connection():
                unconnected.append(x.pvname)
        if len(unconnected) > 0:
            message  = f"IonChamber {prefix}: {len(unconnected)}/{len(self._pvs)} PV not connected"
        print(message, flush=True)

class IonChamber:
    """Epics Device for Ion Chamber Flux Calculation

    usage
    from epicsapps.ionchamber import IonChamber
    ionc = IonChamber(prefix='XX:IONC:', sleeptime=0.5)
    ionc.run()
    """
    def __init__(self, prefix='13XRM:IC0:'):
        self.ic = IonChamberDevice(prefix=prefix)

        xdb = get_xraydb()
        tab_photo = xdb.tables['photoabsorption']
        tab_scatt = xdb.tables['scattering']
        tab_ionp = xdb.tables['ionization_potentials']
        tab_comp = xdb.tables['Compton_energies']

        # ion potentials
        self.ion_pots = {}
        for row in xdb.session.execute(tab_ionp.select()).fetchall():
            self.ion_pots[row[0]] = row[1]

        # Compton data: get incident X-ray energy and mean energy
        #        of scattered electron beam
        comp_dat = xdb.session.execute(tab_comp.select()).fetchone()
        self.compton_xen = js2array(comp_dat.incident)
        self.compton_een = js2array(comp_dat.electron_mean)
        self.density = {}
        self.elements = {}
        for gas in ('He', 'N', 'Ar', 'Kr'):
            form, density = get_material(gas)
            self.density[gas] = density
            srow = xdb.session.execute(tab_scatt.select().filter(
                tab_scatt.c.element==gas) ).fetchone()
            prow = xdb.session.execute(tab_photo.select().filter(
                tab_photo.c.element==gas) ).fetchone()
            self.elements[gas] = {
                'scatt_lne': js2array(srow.log_energy),
                'scoh_dat': js2array(srow.log_coherent_scatter),
                'scoh_spl': js2array(srow.log_coherent_scatter_spline),
                'sincoh_dat': js2array(srow.log_incoherent_scatter),
                'sincoh_spl': js2array(srow.log_incoherent_scatter_spline),
                'photo_lne': js2array(prow.log_energy),
                'photo_dat': js2array(prow.log_photoabsorption),
                'photo_spl': js2array(prow.log_photoabsorption_spline)
            }
        del tab_photo, tab_scatt, tab_ionp, tab_comp, comp_dat, xdb

    def cross_section(self, elem, energy, kind='photo'):
        """
        returns Elam Cross Section values for an element and energy
        Parameters:
            elem (string:  symbol for Gas
            energy (float: X-ray energy (in eV)
            kind (string):  one of 'photo', 'coh', and 'incoh' for
                 photo-absorption, coherent scattering, and incoherent
                 scattering cross sections, respectively. ['photo'].

        Returns:
            ndarray of scattering data
        """
        if elem not in self.elements:
            raise ValueError(f"unknown gas '{elem}'")
        kind = kind.lower()
        if kind not in ('coh', 'incoh', 'photo'):
            raise ValueError(f"unknown cross section kind='{kind}'")

        loge = self.elements[elem]['scatt_lne']
        if kind == 'coh':
            logd = self.elements[elem]['scoh_dat']
            logs = self.elements[elem]['scoh_spl']
        elif kind == 'incoh':
            logd = self.elements[elem]['sincoh_dat']
            logs = self.elements[elem]['sincoh_spl']
        elif kind == 'photo':
            loge = self.elements[elem]['photo_lne']
            logd = self.elements[elem]['photo_dat']
            logs = self.elements[elem]['photo_spl']

        en = min(8.e5, max(100.0, energy))
        out = np.exp(elam_spline(loge, logd, logs, np.log(en)))
        return out[0]*self.density[elem]

    def calc_flux(self, gas, energy, length, amps):
        """
        calculation like Xraydb ionchamber_fluxes
        """
        ion_pot = self.ion_pots[gas]

        # use weighted sums for mu values and ionization potential
        mu_photo = self.cross_section(gas, energy, kind='photo')
        mu_incoh = self.cross_section(gas, energy, kind='incoh')
        mu_coh   = self.cross_section(gas, energy, kind='coh')
        mu_total = mu_coh + mu_incoh + mu_photo

        atten_total = 1.0 - np.exp(-length*mu_total)
        atten_photo = atten_total*mu_photo/mu_total
        atten_incoh = atten_total*mu_incoh/mu_total

        # energy of Compton electron (mean)
        i0 = index_of(self.compton_xen,  energy)
        i0 = max(0, i0-4)
        i1 = min(i0+8, len(self.compton_xen))

        energy_compton = CubicSpline(self.compton_xen[i0:i1],
                                     self.compton_een[i0:i1])(energy)
        # print("Compton Energy ", energy, energy_compton)

        absorbed_energy = 2*(energy*atten_photo + energy_compton*atten_incoh)
        flux_in  = amps*ion_pot/(QCHARGE*absorbed_energy)
        flux_out = flux_in * (1-atten_total)

        return flux_in, flux_out

    def calculate(self):
        'the actual calculation'
        gas       = self.ic.get('Gas', as_string=True)
        length    = self.ic.get('Length')
        energy_pv = self.ic.get('EnergyPV')
        volt_pv   = self.ic.get('VoltPV')
        amp_pv    = self.ic.get('AmpPV')
        ampn_pv  = f'{amp_pv}sens_num'
        ampu_pv  = f'{amp_pv}sens_unit'

        amp_val  = float(caget(ampn_pv, as_string=True))
        amp_unit = caget(ampu_pv, as_string=True)
        amp_unit = SUNITS.get(amp_unit, 1.e-6)
        voltage  = caget(volt_pv)
        energy   = caget(energy_pv)
        if energy is None:
            energy = 0.0
        energy = min(8e5, max(100, energy))
        # current in Amp
        current  = voltage * amp_val * amp_unit
        flux_in, flux_out = self.calc_flux(gas, energy, length, current)
        abs_percent = 100*(1.0-(flux_out/(flux_in+0.1)))
        try:
            self.ic.put('Energy',     energy)
            self.ic.put('AbsPercent', abs_percent)
            self.ic.put('Current',    current*1.e6)
            self.ic.put('FluxAbs',    flux_in-flux_out)
            self.ic.put('FluxOut',    flux_out)
            self.ic.put('FluxOutS',   gformat(flux_out, length=10))
            self.ic.put('TimeStamp',  isotime())
        except:
            print("Epics Put failed", flush=True)
        return flux_in, flux_out

    def run(self, sleep_time=0.5, report_time=300):
        last_message = time.time() - 5*report_time
        while True:
            try:
                self.calculate()
            except:
                pass
            now = time.time()
            if now > last_message + report_time:
                print(f"ionchamber running at {isotime()}", flush=True)
                last_message = now
            time.sleep(sleep_time)
        print("Ionchamber done ", isotime())


def start_ionchamber(prefix='XX:ION:', sleep_time=0.5, report_time=300):
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
        ionc.run(sleep_time=sleep_time, report_time=report_time)
    else:
        print(f'IonChamber {prefix} is running, last update at {last_event}')
