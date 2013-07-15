This folder contains Epics Applications using Channel Access and pyepics.

A brief description of the current Epics Applications:

======================================
Epics Instruments   
 
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
Epics Area Detector Viewer

An application to control and view images from an Epics Area Detector.  The
controls available in this viewer are minimal, but you can change mode,
exposure time and frame rate, and start and stop the Area Detector.  The
image can be manipulated by zooming, rotating, and so on.


======================================
Epics StripChart

An application to draw a stripchart display of one or more PVs.  Time
ranges and ranges for Y values can be changed, and data can be saved to
plain text files.

======================================a
Epics Motor Setup (Local and GSE versions)

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


======================================
Question, Suggestions, Problems:  newville@cars.uchicago.edu

Last Update: 7-March-2012
