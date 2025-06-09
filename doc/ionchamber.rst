.. _IonChamber.db: https://raw.githubusercontent.com/pyepics/epicsapps/refs/heads/master/epicsapps/ionchamber/iocApp/IonChamber.db
.. _IonChamber IOC Files: https://github.com/pyepics/epicsapps/tree/master/epicsapps/ionchamber/iocApp

.. _xraydb: https://xraypy.github.io/XrayDB/


.. _Ion Chamber flux calculations: https://xraypy.github.io/XrayDB/examples.html#ion-chamber-flux-calculations

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

`IonChamber.db` and loading into an soft IOC
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
  | $(P)$(Q):EnergyPV     | In   | PV for Energy Value                       |
  +-----------------------+------+-------------------------------------------+
  | $(P)$(Q):VoltPV       | In   | PV for IonChamber Voltage                 |
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


Runnint the Ionchamber script
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


Once the database is loaded,



Calculation details
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The calculation of flux uses `xraydb`_.  Details of the calculation
are given at `Ion Chamber flux calculations`_.
