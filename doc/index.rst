.. PyEpics Applications

Python Epics Applications
================================

PyEpics Apps contains several Epics Applications written in python, using
the pyepics module (see `http://pyepics.github.com/pyepics/
<http://pyepics.github.com/pyepics/>`_).  Many of these are GUI
Application for interacting with Epics devices through Channel Access.  The
programs here are meant to be useful as end-user applications, or at least
as examples showing how one can build complex applications with
PyEpics. Many of the applications here rely on wxPython, and some also rely
on other 3rd party modules (such as Image and SQLAlchemy).

The list of applications should be expanding, but currently include:

AreaDetector Display
~~~~~~~~~~~~~~~~~~~~~~

A simple, live display for an Epics Area Detector.

Strip Chart
~~~~~~~~~~~~~~

A simple "live plot" of a set of PVs, similar to the common Epics
StripTool.

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

   overview
   installation
   ad_display
   stripchart
   instrument
   xrfcollect
   ionchamber




