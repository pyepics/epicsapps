.. PyEpics Applications

Python Epics Applications
================================

PyEpics Apps contains several Epics Applications written in python, using the
pyepics module (see `https://pyepics.github.com/pyepics/
<https://pyepics.github.com/pyepics/>`_).  Many of these are GUI Application
for interacting with Epics devices through Channel Access.  The programs here
are meant to be useful as end-user applications, or at least as examples
showing how one can build complex applications with PyEpics. Many of the
applications here rely on wxPython, and some also rely on other 3rd party
modules (such as Image and SQLAlchemy).

The list of applications should be expanding, but currently include:

AreaDetector Display
~~~~~~~~~~~~~~~~~~~~~~

An application to control and view images from an Epics Area Detector.  The
controls available in this viewer are minimal, but you can change mode,
exposure time and frame rate, and start and stop the Area Detector.  The
image can be manipulated by zooming, rotating, and so on.


Strip Chart
~~~~~~~~~~~~~~

A simple "live plot" of the recent history of a set of PV values, similar
to the common Epics StripTool.  Time ranges and ranges for Y values can be
changed, and data can be saved to plain text files.


Epics Instruments
~~~~~~~~~~~~~~~~~~~~

This application helps you organize PVs, by grouping them into instruments.
Each instrument is a loose collection of PVs, but can have a set of named
positions that you can tell it.  That is, you can save the current set of
PV values by giving it a simple name.  After that, you can recall the saved
values of each instrument, putting all or some of the PVs back to the saved
values.   The Epics Instrument application organizes instruments with
tabbed windows, so that you can have a compact view of many instruments,
saving and restoring positions as you wish.


Sample Stage
~~~~~~~~~~~~~~

A GSECARS-specific GUI for moving a set of motors for a sample stage,
grabbing microscope images from a webcam, and saving named positions.

Motor Setup
~~~~~~~~~~~~~~~~

An application for setting up and saving the configuration of Epics Motors.
For each opened motor, a full setup screen is shown in a tabbed notebook
display.  A paragraph for a Motors.template file can be saved for each
motor, or copied to the system clipboard.  In addition, you can save and
read "known motor types" to a database, which holds most of the motor
parameters.

The Local version uses a local sqlite database to store and read the known
motor types, while the GSE version (which works only at GSECARS, of course)
connects to a mysql server on the GSECARS network to store are read the
known motor types.


Ion Chamber
~~~~~~~~~~~~~~

This non-GUI application is synchrotron-beamline specific.  It reads
several settings for the photo-current of an ion chamber and calculates
absorbed and transmitted flux in photons/sec, and writes these back to PVs
(an associated .db file and medm .adl file are provided).  The script runs
in a loop, updating the flux values continuously.

XRF Collector
~~~~~~~~~~~~~~~~

This non-GUI application interacts with a small epics database to save data
from a multi-element fluorescence detector.  The script runs as a separate
process, watching PVs and saving data from the detector on demand.
Associated .db file and medm .adl file are provided.

.. toctree::
   :maxdepth: 2

   installation
   ad_display
   stripchart
   instrument
   motorsetup
   ionchamber
   xrfcollect
