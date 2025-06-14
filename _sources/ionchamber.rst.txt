.. _IonChamber.db: https://raw.githubusercontent.com/pyepics/epicsapps/refs/heads/master/epicsapps/ionchamber/iocApp/IonChamber.db
.. _IonChamber IOC Files: https://github.com/pyepics/epicsapps/tree/master/epicsapps/ionchamber/iocApp

.. _xraydb: https://xraypy.github.io/XrayDB/
.. _xraydb flux calculation: https://xraydb.seescience.org/ionchamber

.. _Ion Chamber flux calculations: https://xraypy.github.io/XrayDB/examples.html#x-ray-flux-calculations-for-ionization-chambers-and-photodiodes

.. _ionchamber:


Converting Ion Chamber readings to flux
===============================================

The Epicsapps Ion Chamber application is non-GUI application that uses
several Epics records to calculate the flux absorbed in and
transmitted through an Ionization Chamber.  uses a small Epics
database that needs to be loaded in a soft IOC to hold values.  A
python program can then be run which will read settings from this
database, calculate the fluxes, and write them back to the Epics
database.  An `adl` display file for the MEDM display manager is
provided as a simple UI.

Loading `IonChamber.db` into a soft IOC
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


To use the Ion Chamber application, the `IonChamber.db`_ file
(with related files at `IonChamber IOC Files`_), needs
to be loaded into a soft IOC, with a load command like::

   dbLoadRecords("IonChamber.db","P=13IDE:,Q=I0")

where the values for "P" and "Q" will be used to generate standard
PV prefixes. This will generate PV names listed in the
:ref:`Table of PVs for Ion Chamber <ionchamber_pv_table>`.


.. _ionchamber_pv_table:

**Table of PVs for Ion Chamber** These PVs will be used either as
input or output for the Ion Chamber calculations.  Here "In" means the
user is expected to provide these, while "Out" values will be written
to be the `stripchart` application.


  +-----------------------+------+-------------------------------------------+
  | PV Name               | I/O  | Description                               |
  +=======================+======+===========================================+
  | $(P)$(Q):AmpPV        | In   | Prefix for SRS570 Amp                     |
  +-----------------------+------+-------------------------------------------+
  | $(P)$(Q):VoltPV       | In   | PV for IonChamber Voltage                 |
  +-----------------------+------+-------------------------------------------+
  | $(P)$(Q):EnergyPV     | In   | PV for X-ray Energy Value in eV           |
  +-----------------------+------+-------------------------------------------+
  | $(P)$(Q):Desc         | In   | Description of Ion Chamber                |
  +-----------------------+------+-------------------------------------------+
  | $(P)$(Q):Length       | In   | IonChamber Length (cm)                    |
  +-----------------------+------+-------------------------------------------+
  | $(P)$(Q):Gas          | In   | IonChamber Gas (one of a selection)       |
  +-----------------------+------+-------------------------------------------+
  | $(P)$(Q):Volts        | Out  | IonChamber Voltage                        |
  +-----------------------+------+-------------------------------------------+
  | $(P)$(Q):Energy       | Out  | X-ray energy (eV)                         |
  +-----------------------+------+-------------------------------------------+
  | $(P)$(Q):AbsPercent   | Out  | percent of flux absorbed in Ion Chamber   |
  +-----------------------+------+-------------------------------------------+
  | $(P)$(Q):Current      | Out  | current generated in Ion Chamber (uA)     |
  | $(P)$(Q):FluxAbs      | Out  | flux absorbed in Ion Chamber (Hz)         |
  +-----------------------+------+-------------------------------------------+
  | $(P)$(Q):FluxOut      | Out  | flux transmitted out of Ion Chamber (Hz)  |
  +-----------------------+------+-------------------------------------------+
  | $(P)$(Q):FluxOutS     | Out  | string for flux transmitted               |
  +-----------------------+------+-------------------------------------------+
  | $(P)$(Q):TimeStamp    | Out  | timestamp of last update                  |
  +-----------------------+------+-------------------------------------------+


Running the Ionchamber script and Display
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Once the database is loaded, you will need to set the PV names for:

  1. the prefix for the current amplifier.  This is assumed to be a Stanford SRS70
     current amplifier.
  2. the PV for the output voltage of that amplifier.
  3. the PV for the X-ray energy, in eV.

You will also need to set the length of the ion chamber (in cm), and the gas in
the ion chamber.  The gas is assumed to be only one gas, either Air, He, N2,
Ar, or Kr.

With these inputs set, you can run a script like this::

    #!/usr/bin/python
    import sys
    from epicsapps.ionchamber import start_ionchamber

    prefix = '13XRM:IC0:'
    start_ionchamber(prefix=prefix)

which will continuously read the ion chamber sensitivity, voltages, and X-ray
energy, and so forth.  This will the compute the fluxes and update the output
PVs list in :ref:`Table of PVs for Ion Chamber <ionchamber_pv_table>`.


You can run a display file (available at `IonChamber IOC Files`_) to view these
values by running MEDM with::

    medm -x  -macro "P=13XRM:,Q=IC0" IonChamber.adl

or a similar Epics display command.


Calculation details
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The calculation of flux uses `xraydb`_.  Details of the calculation are given
at `Ion Chamber flux calculations`_.  This includes both photo-electric
absorption and the current generated from Compton scattering.  See also
`xraydb flux calculation`_ for examples.
