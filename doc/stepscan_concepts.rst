..  _scan_concepts-label:

=====================
Step Scan Concepts
=====================


A step scan is simply a **for loop** that iterates a collection of
**Positioners** (any Epics PV -- not restricted to Motors) through
a set of pre-determined position values.  At each position, a set
of detectors are **triggered** (which is to say, collection is
started), and then waited upon until they announce they are
complete.  At that point a collection of **Counters** (again, any
Epics PV, though for those holding waveform values see the notes
below) are read, and the loop starts over, moving on to the next
point in the list of positions.

A StepScan also contains several other components::
  *  extra_pvs: a set of PVs to record once (or a few times) for each
     scan, but not at every point in the scan.
  *  breakpoints: a series of points in the scan at which data collected
     so far is dumped to file, and perhaps other tasks are done.
  *  pre_scan: a set of functions to call just prior to beginning the scan.
  *  post_scan: a set of functions to call just after the scan completes.
  *  at_break: a set of functions to call at each breakpoint (after the
     data is written to disk).


Positioners
===============

Positioners are what is changed in the scan -- the dependent variables.
The can be represented by any Epics PV, such as Motors, temperatures,
currents, count times, or a combination of these.  Scans can have multiple
positioners, either moving in tandem to make a complex motion in the
positioner space, or independently to make a mesh in the positioner space.

In addition to a PV, each positioner will have an array of positions which
it should take during the scan.  The Positioner holds the full array
positions.  There are methods available for creating this from Start, Stop,
Step, and Npts parameters for simple linear scans, but you can also give it
a non-uniform array,

If you have multiple positioners, they must all have an array of positions
that is the same length.


Triggers
=============

A Trigger is something that starts a detector counting.  The general
assumption is that these start integrating detectors with a finite count
time (which may have been set prior to the scan, or set as one of the
Positioners).  The scan waits for these triggers to announce that they have
completed (ie, the Epics "put" has completed).  That means that not just
any PV can be used as a Trigger -- you really need a trigger that will
finish.

For many detectors using standard Epics Records (Scalers, MCAs,
multi-element MCAs, AreaDetectors), using a Detector (see below) will
include the appropriate Trigger.

Counters
=============

A Counter is any PV that you wish to measure at each point in the scan.

Counters for waveforms:

For many detectors using standard Epics Records (Scalers, MCAs,
multi-element MCAs, AreaDetectors), using a Detector (see below) will
automatically include a wide range of Counters.

Detectors
=============

Detectors are essentially a combination of Triggers and Counters that
represent a detector as defined by one of the common Epics detector
records.  These include Scalers, MCAs, multi-element MCAs, and
AreaDetectors.

