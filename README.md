# Epics Applications

A collection of applications for Epics using Python

## install

On Linux, you will need to make sure that wxPython is installed.  For an Anaconda envirornment,

   conda -c conda-forge install wxpython

will work. Then,

   pip install epicsapps

will install everything else you need.


## StripChart

   A StripChart Application, showing live time series of Epics PVs

## areaDetector Viewer

   A viewer for areaDetector Viewers, with good image properties including
   automatic contrast levels, a user-configurable Zoom-box, and simple
   configuration file to add which control variables are shown.

## Epics Instruments

   A GUI application to group any PVs together into named Instruments, and then
   save and restore positions for these Instruments by name.  That is, you can
   group for 4 motors together, calling them "Slits", and then save and restore
   positions called "1x1 mm" and "2x2 mm", etc.

## Epics PV Logger

   Two related appplications to save and view time-series data for selected
   PVs.  Data collection can be run from a command line application, reading a
   YAML file to configure which PVs are saved. Data is saved into plain text
   files in a single folder.  A GUI application can help create and modify the
   configuration file, and start collection.  The GUI application can also
   browse and display the data collected into the PVlog folder.

## Microscope Viewer

  A GUI application for viewing an controlling a sample stage with a microscope
  camera.  This combines aspects of both areaDetector Viewer and Epics Instruments,
  as positions of the sample stege can be saved and restored by name.

## IonChamber calculations

  A commandline application to connect to and read Ion Chamber settings
  (voltages, amplifier gains) and X-ray energy to compute the fluxes absorbed
  and transmitted by an Ion Chamber.
