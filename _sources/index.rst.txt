.. PyEpics Applications

.. _pyepics: https://pyepics.github.io/pyepics
.. _EpicsApps: https://pyepics.github.io/epicsapps
.. _PyEpics: https://pyepics.github.io/pyepics
.. _wxPython: https://www.wxpython.org/
.. _matplotlib:  https://matplotlib.org/



Epics Applications with PyEpics
=====================================

EpicsApps is a collection of Epics Applications written in python,
using the `pyepics`_ library for interacting with Epics devices
through Channel Access.  Many of these are GUI Applications, built
with `wxPython`_, and some use other Python libraries for interacting
wih data. While a part of the goal for this project is to demonstrate
how one can build complex programs with `pyepics`_, the applications
here are intended to be useful to beamline scientists and end-users at
facilities such as synchrotrons that use the Epics control system.

The main applications included in EpicsApps include

  * :ref:`stripchart`: A GUI application to show a "live plot" of the recent
    history of a set of PV values.  Time ranges and ranges for Y
    values can be changed, and data can be saved to plain text files.

  * :ref:`ad_viewer`: A GUI application to control and view images
    from an Epics Area Detector.  Controls for stqrting acquistion,
    changing image mode, exposure time, and frame rate can also be
    included using a simple configuration file. The end-user can
    change color-table and contrast level, as well as use a Zoom Box
    to enhance portions of the image.

  * :ref:`instruments`: A GUI application to organize PVs, by grouping
    them into user-named "Instruments".  Each Instrument can have a
    set of named positions that the end-user can save and restore.

  * :ref:`pvlogger`: A command-line and GUI application to collect and log
    time-series of a handful of PV values into plain text files in a
    folder in a manner that can be easily reviewed.

  * *Sample Microscope*: A GSECARS-specific GUI for moving a set of
    motors for a sample stage, grabbing microscope images from a
    webcam, and saving named positions.



.. toctree::
   :maxdepth: 2

   installation
   stripchart
   ad_display
   instruments
   pvlogger
   other
