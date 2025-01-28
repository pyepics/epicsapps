.. _pvlogger:


PV Logger
====================================

The Epics PV Logger collects timeseries of a set of PVs into plain
text data files in a folder.  This is intended for a modest number of
PVs that are not the primary data being collected, for a limited time.
This might be expressed as "around 100 PVs for a week", as for a
normal experiment time.

For an experiment at a synchrotron beamline, it is often useful to
collect values like Storage Ring Current, room temperature, positions
and temperature of beamline optics and components, and maybe detector
settings.  This sort of *metadata* cold be put into every data
fil. While some metadata surely belongs in each data file, items like
temperature of an upstream mirror or values of beam position monitors
are really not metadata about the individual data file.  And, while
there are several larger systems for archiving and retrieving PV
variables for the whole facility or beamline, these are often meant to
be global systems, and not about individual experiments, and are ofen
not available away from the beamline.

We found that metadata stored in headers of other data files or large
databases oten makes it hard to investigate how the values changed
over the course of an experiment.  Sometimes, it would be nice to
browse and compare a few Time Series plots for a handful of PVs and
toe compare those with timestamps of the primary data files.


PV Logger aims to fill this gap and is designed to collect the
data you want during an experiment, and in a way that can be easily
digested and investigated.

The PV Logger application runs in two mode: *collection* and *view*.
The GUI application can be used for both, though collection can also
be run purely from the command-line.  Data Collection always writes
data into files in a folder that is expected to be controlled only by
PVLogger.  By default, this folder will be named "pvlog", though that
can be set in the configuration.

Viewing PVLogger Data
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For data that has already been collected, the PVLogger GUI Application
can read the data collected into the PVlog folder, and display it.


Collecting PVLogger Data
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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
