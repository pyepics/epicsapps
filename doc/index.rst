.. PyEpics Applications

.. _pyepics: https://pyepics.github.io/pyepics
.. _EpicsApps: https://pyepics.github.io/epicsapps
.. _PyEpics: https://pyepics.github.io/pyepics
.. _wxPython: https://www.wxpython.org/
.. _matplotlib:  https://matplotlib.org/



Epics Applications with PyEpics
=====================================

EpicsApps is a collection of Epics Applications written in Python,
using the `pyepics`_ library for interacting with Epics devices
through Channel Access.  Mot of the applications are Graphical User
Interface programs built with `wxPython`_.

While a part of the goal for this project is to demonstrate how one
can build complex programs with `pyepics`_, the applications here are
intended to be useful to beamline scientists and users at facilities
such as synchrotrons that use the Epics control system.

The main applications included in EpicsApps are:

  * :ref:`stripchart`: A GUI application to show a live, real-time
    plot of the recent values for a set of PV values.  Time ranges and
    ranges for Y values can be changed, and data can be saved to plain
    text files.

  * :ref:`ad_viewer`: A GUI application to view live images and have basic
    control of data collection for an Epics Area Detector.  The standard
    controls allow starting and stopping acquistion, changing image
    mode, exposure time, and frame rate. More controls can be be
    added using a simple configuration file. The user can change the
    color table, contrast level, and orientation of the image, and
    use a Zoom Box to enhance portions of the image.

  * :ref:`instruments`: A GUI application to organize PVs, by grouping
    them into user-defined "Instruments".  Each Instrument can have
    any number of PVs included.  For each Instrument, positions can be
    saved by named, and then restored using that named position.

  * :ref:`pvlogger`: A pair of applications to collect and view time
    seriese of "metadata" PVs.  When run from a command-line with a
    configuration file listing PVs to save, this will save data for
    PVs into plain text files in a folder named `pvlog`.  When run as
    a GUI Application during or after acquisition, this application
    can read data from a `pvlog` folder and plot data as time-series
    for reviewing changes in these meta-data PVs.

  * :ref:`ionchamber`: A non-GUI application to read Ion Chamber
    voltages and amplifier setting, compute X-ray fluxes, and write
    these back to Epics PVs.


.. toctree::
   :maxdepth: 2

   installation
   stripchart
   ad_display
   instruments
   pvlogger
   ionchamber
