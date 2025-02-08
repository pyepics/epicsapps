.. _pvlogger:


PV Logger
====================================

The Epics PV Logger collects timeseries of a set of PVs into plain
text data files in a folder.  This is intended for a modest number of
PVs that are not the primary data being collected, for a limited time.
This might be expressed as "around 100 PVs for a week", as is typical
for a single experiment at a synchrotron beamline.

For such an experiment, it is often useful to collect values like
Storage Ring Current, room temperature, positions and temperature of
beamline optics and components, and detector settings.  This sort of
*metadata* cold be put into every data fil. While some metadata surely
belongs in each data file, items like temperature of an upstream
mirror or values of beam position monitors are really not metadata
about the individual data file.  And, while there are several larger
systems for archiving and retrieving PV variables for the whole
facility or beamline, these are often meant to be global systems, and
not about individual experiments, and are ofen not easily available
after the experiment or away from the beamline.

We found that metadata stored in data file headers or large
databases oten makes it hard to investigate how the values changed
over the course of an experiment.  Sometimes, it would be nice to
browse and compare a few Time Series plots for a handful of PVs and
to compare those with timestamps of the primary data files.


The PVLogger application aims to fill this gap and is designed to
collect the meta-data you want during an experiment, and in a way that
can be easily digested and investigated.

The PVLogger application has two mode of operation: *collecting data*
and *viewing data*.  A command-line program run at the beamline will
collect the data into a dedicated folder using a simple configuration
file to control what data is collected.

The PVLogger GUI application can read the data collected into such a
folder and allow visualization of the logged data.  While at the
beamline, The PVLogger application can also be used to launch a
:ref:`stripchart` application to plot a live view of the changing
data.  Finally, the PVLogger application can be used to read, modify,
and save existing configuration files, listing which PVs to log, and
can start the data collection process.


Viewing PVLogger Data
--------------------------

For data that has already been collected, the PVLogger GUI Application
can read the data collected into the PVlog folder, and display
it. Opening an existing folder will give a main window display like:

.. image:: images/pvlogger_mainview.png

The Left-hand column will show the list of of PVs that were logged
into the folder.  The names shown will generally be the "description"
saved for the PV, sometimes with the PV name if the description is not
unique. Each has a Check Box that you can use to select many PVs at
once.  The "Clear Selections" button in the upper left will clear all
checked PVs.  The right-hand portion has 2 Notebook Tabs, labelled
"View Log Folder" and "Collect Data" -- we'll discuss the "View Log
Folder" tab here and the "Collect Data" tab in the next section.

The "View Log Folder" Panel allows you to select what edata to
visualize. The folder being read is If Epics Instruments were used in
the data collection, you can select these and then press "Select these
PVs" to check each of the PVs in that Instrument.

The central portion of the panel shows up to 4 PVs to be
displayed. Each of these has a Dropdown list will all the PV
descriptions.   Selecting any PV in the left-hand PV list will select that
for  "PV 1".  Clicking the "Use Selcected PVs" button will select
the first 4 checked PVs from the PV List.  Clicking "Clear PVs 2,3,4"
will clear those PVs (that is, select "None).

Below the list of PVs are buttons for what to display.  The "Show PV
1" button will display the data for the PV selected as "PV 1"  The
"Show Selected" will display the data for all (up to 4) selected PVs.
For most PVs, the data will be numerical, and the "Show" buttons will
display a graph of the time dependence of the PV(s).  As an example,
with "Storage Ring Current (mA)" as PV 1, clicking the "Show PV 1"
button will show:

.. image:: images/pvlogger_plotone.png

Up to 10 plot windows can be used.  You can select which to use for any
display by selecting "Window 1" through "Window 10".

Finally, when used at the beamline or from a computer that can connect
to the live beamline PVs, clicking on the "Live Plot for PV 1" will
show the corresponding PV in a live :ref:`stripchart` application.


Seeing "Event Data" -- non-numerica data
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~



Collecting PVLogger Data
----------------------------

PVLogger will read a YAML-formatted configuration file to tell it what
PVs to collect, and where to save the data.  A typical file might look
like this::

    folder: pvlog
    workdir: '/server/data/beamlineX/2025/userABC'
    pvs:
    - S:SRcurrentAI.VAL        | Storage Ring Current | 0.005
    - 'RF-ACIS:FePermit:Sect1To35IdM.VAL | Shutter Permit | 0 '
    - SXID:DSID:GapM.VAL      | ID Gap  (mm)      | 0.001
    - SXID:DSID:TaperGapM.VAL | ID Gap Taper (mm) | 0.001
    - XX:m1.VAL               | <auto>            | 0.001
    - XX:m2.VAL               | <auto>            | 0.001
    - XX:m3.VAL               | <auto>            | 0.001
    - XX:m4.VAL               | <auto>            | 0.001
    - XX:DMM1Ch1_calc.VAL     | Mono Temerpature 1   | 0.01
    - XX:DMM1Ch2_calc.VAL     | Mono Temperature 2   | 0.01
    - XX:DMM1Ch3_calc.VAL     | Mono Temperature 3   | 0.01
    - XX:E_BPMFoilPosition.VAL
    instruments:
    - SampleStage

Here, `workdir` gives the path to the working directory, and `folder`
give the name of the PVLogger folder in that working directory to put
the data collected.  In this case, a folder named
'/server/data/beamlineX/2025/userABC/pvlog` will be created and used
for data collection.

The `pvs` section gives a list of PVs to monitor and collect
data. Each line is formed as::

      PVName   |   Description  | Monitor_Delta

The PV name is required.  Note that, as for one of the examples
above where `-` is in the PV name that the entire line is in quotes.

The Description field is option. If left off, or the word '<auto>' is
used, the PVLogger will try to get this from the corresponding `.DESC`
field for the PV.

The `Monitor Delta` value gives the minimal change in the PV value
ethat will be recorded - it applies only to Analog, floating point
values.  This value is absolute, not relative, and it is referenced to
the last reported value so that slow cumulative changes are seen, just
with fewer intermediate values.

PVLogger will try to set the `.MDEL` field of the record. This will
limit the number of events sent for this PV from the CA server to only
those that exceed the last reported value by this amount.  If the
`.MDEL` field cannot be set (perhaps due to permission issues), all
events will be sent from the CA server, and PVLogger will emulate
this, recording only those values that change by this amount.

Note that many PVs will have `.MDEL` set to 0 by default so that all
events are captured.



Running PVLogger to collect data
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

With an existing PVLog configuration file, say `my_pvlog.yaml`,
Logging can be started with::

   epicsapps -c pvlogger my_pvlog.yaml



The PVLog Folder
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
