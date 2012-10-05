This repository contains Epics Channel Access Applications using PyEpics.
The intention herer is to include programs that are either general-purpose
stand-alone applications or specific-use applications that can be viewed as
examples.

Each application should live in its own folder, and have its own
installation scripts and documentation. The applicaions may vary in their
completeness and level of documentation.  In addition to pyepics, many of
these applications will require additional third party libraries, such as
wxPython, numpy, and matplotlib.  These should be explicitly listed in the
Dependencies below.

Some applications may expect to interact with specific Epics databases or
define new (usually small. trivial) databases and possibly Epics Display
files (.adls for MEDM, for example).  These should be included in the
directory.

Complete documentation can be found at http://pyepics.github.com/epicsapps/


A brief description of the current Epics Applications:

======================================
Folder: Instruments
App Name:  Epics Instruments
Dependencies: wxPython, sqlalchemy.

Epics Instruments is a GUI app that allows a user to group Epics PVs into a
named "Instrument".  Many Instruments can be defined, with each Instrument
having its own Tab in a Notebook window.  PVs will be displayed as
name/value pairs, in a "type-aware" manner for easier interaction and data
entry.  Each Instrument has a set of named positions that save the values
for all PVs in that instrument when the position is named.  Any of the
named positions can be "restored", that is, all the PVs moved to the values
when the position was named at any time.

The set of defined instruments shown in the application, and all the
named positions are stored in a single file -- an sqlite3 database
file.  Multiple instances of the program can be running on the same
subnet and even computer without stepping on one another, though
the application works hard to prevent a second instance from using
an open-and-working definition file.

======================================
Folder: IonChamber
App Name:  Ion Chamber
Dependencies: numpy

Ion Chamber reads ion chamber currents and amplifier settings, uses these
to calculate the absorbed, incident, and transmitted x-ray flux, and writes
these out to Epics PVs.  It probably makes several implicit assumptions
about units and equipment setup specific to APS/GSECARS, but may provide
useful example of writing a state-program with pyepics.

======================================
Folder: SampleStage
App Name:  GSECARS XYZ Sample Stage
Dependencies: wx

A GUI app for controlling a sample stage, including saving/restoring
positions and capturing images (web-cam only, currently) associated
with each position.

======================================

