.. _PyInstrument.db: https://raw.githubusercontent.com/pyepics/epicsapps/refs/heads/master/examples/instruments/epics_client/PyInstrument.db
.. _PyInstrument.adl: https://raw.githubusercontent.com/pyepics/epicsapps/refs/heads/master/examples/instruments/epics_client/PyInstrument.adl

.. _instruments:

Epics Instruments
====================================

Epics Instruments is a GUI application (using wxPython) that lets any user:

  * Organize PVs into Instruments: a named collection of PVs
  * Manage Instruments with Notebook or tabbed interface.
  * Save Positions for any Instrument by name.
  * Restore Positions for any Instrument by name.
  * Remember Settings for all definitions into a single file that can be loaded later.
  * Multiple Users can be using multiple instrument files at any one time.

It was originally written to replace and organize the multitude of similar MEDM
screens that appear at many workstations using Epics.


Running Epics Instruments
~~~~~~~~~~~~~~~~~~~~~~~~~~

To run Epics Instruments, use::

   epicsapps instruments

or click on the icon.

A small window to select an Epics Instrument File, like this

.. image:: images/Inst_Startup.png
    :width: 80%

If this is your first time using the application, choose a name, and hit return
to start a new Instrument File.  The next time you run Epics Instruments, it
should remember which files you have recently used, and present you with a
drop-down list of Instrument Files.  Since all the definitions, positions, and
settings are saved in a single file, restoring this file will recall the
earlier session of instrument definitions and saved positions.

An Epics **Instrument** is a collection of PVs.  Each Instrument will also
have a collection of **Positions**, which are just the locations of all the
PVs in the instrument at the time the Position was saved.  Like a PV, each
Instrument and each Position for an Instrument has a unique name.


Defining a New Instrument
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To define a new Instrument, select **Create New Instrument** from the
Instruments Menu.  A screen will appear in which you can name the
instrument and the PVs that belong to the Instrument.

If you add a few PVs and click OK, the PVs will connect, and you will see a
screen something like this

.. image:: images/InstMain_Stage.png
    :width: 95%


Editing an Exisiting Instrument
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. image:: images/Inst_Edit.png
    :width: 50%


The Instrument File
~~~~~~~~~~~~~~~~~~~~~~~

All the information for definitions of your Instruments and their Positions
are saved in a single file -- the Instruments file, with a default
extension of '.ein' (Epics INstruments).   You can use many different
Instrument Files for different domains of use.

The Instrument File is an SQLite database file, and can be browsed and
manipulated with external tools.  Of course, this can be a very efficient
way of corrupting the data, so do this with caution.  A further note of
caution is to avoid having a single Instrument file open by multiple
applications -- this can also cause corruption.  The Instrument files can
be moved around and copied without problems.

Accessing Instruments and Positions with Epics
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You may want to be able to access Instrument and Positions from outside the
Instruments application.  For example, you may want to define an Instrument for
"Detector Stages", and save positions called "In" and "Out".  It would be
helpful if you could move the detector to "In" or "Out" from Epics Channel
Access, either from a script or a data collection application.

Instruments can be set up to respond to Channel Access puts and move an
Instrument to a Position.  To do this, use `PyInstrument.db`_, and load that
into an Epics IOC with a command like::

    dbLoadRecords("PyInstrument.db","P=13XRM:, Q=Inst")


From the Instruments app, you can go to the Options->General Settings menu, to
see a screen like

.. image:: images/Inst_Conf.png
    :width: 60%


Checking the "Use Epics Db" box and entering the Prefix defined with the
`dbLoadRecords` command will then enable the Instruments program to respond to
Channel Access requests to move Instruments to Positions.

Using the `PyInstrument.adl`_ display file and an MEDM command like::


    medm -x -macro "P=13XRM:,Q=Inst" /home/epics/adl/all/PyInstruments.adl

will then bring up a display screen like this

.. image:: images/Inst_PyInst.png
    :width: 60%


where you can enter the name of an Instrument, enter the name of a Position,
and hit the Move button to move to that position. Several Epics PVs listed in
the table below are used for this communication.  Note that the Instruments App
itself must be running in order for these moves to happen.



.. _instruments_pv_table:

**Table of CA interface to Instruments** These PVs will be used for the CA
interface to Epics Instruments.

  +-----------------------+-------------------------------------------------+
  | PV Name               |       Description                               |
  +=======================+=================================================+
  | $(P)$(Q):InstName     | Instrument Name                                 |
  +-----------------------+-------------------------------------------------+
  | $(P)$(Q):PosName      | Position Name                                   |
  +-----------------------+-------------------------------------------------+
  | $(P)$(Q):InstOK       | Flag for Instrument Name is valid               |
  +-----------------------+-------------------------------------------------+
  | $(P)$(Q):PosOK        | Flag for Position Name is valid                 |
  +-----------------------+-------------------------------------------------+
  | $(P)$(Q):Move         | Command to Move                                 |
  +-----------------------+-------------------------------------------------+
  | $(P)$(Q):Message      | Runtime message                                 |
  +-----------------------+-------------------------------------------------+
  | $(P)$(Q):TSTAMP       | timestamp, showing Instrument is connected.     |
  +-----------------------+-------------------------------------------------+


From pyepics, you could also do a move with::

    from epics import get_pv, poll
    prefix = '13XRM:Inst:'
    move_pv = get_pv(f'{prefix}Move')
    iname_pv = get_pv(f'{prefix}InstName')
    pname_pv = get_pv(f'{prefix}PosName')
    iok_pv = get_pv(f'{prefix}InstOK)
    pok_pv = get_pv(f'{prefix}PosOK')

    def move_instrument(instrument, position):
        iname_pv.put(instname)
        pname_pv.put(posname)
        poll()
        if iok_pv.get() == 0:
            print(f"Could not find instrument '{instname}'")
        elif pok_pv.get() == 0:
            print(f"Could not find position '{posname}' for '{instname}'")
        else:
            move_pv.put(1)

    move_instrument('SampleStage', 'Sample 1')



Using PostgresQL and epicsscan
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


If you are using the EpicsScan application for data collection, you can also
use its Postgres database as an Epics Instruments database.  This requires a
bit more setup, but allows mulitple client programs to access and use the
Instruments at the same time.
