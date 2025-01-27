PV Logger
====================================

The Epics PV Logger collects timeseries of a set of PVs into plain
text data files in a folder.  The idea is to collect a handful (say,
up to 100) PVs that are related to an experiment run (say, for a few
days or a week) but are not the primary data being collected.  For
example, for an experiment at a synchrotron beamline, it is often
useful to collect values like Storage Ring Current, room temperature,
positions and temperature of beamline optics and components, and maybe
detector settings.

This sort of *metadata* can be put into every data file, but that
often makes it hard to compare between data files, and the values may
only be saved once during a series of collections.  While some
metadata surely belongs in each data file, items like temperature of
an upstream mirror or values of beam position monitors are really not
metadata about the individual data file.

While there are several larger systems for archiving and retrieving PV
variables, these are often meant to be global or beamline-wide
systems, and not about individual experiments.

That is, sometimes you would like to be able to go back through a
dataset and see if something changed during data colletion.  Looking
through the headers of a bunch of text files or TIFF images is
painful, and sifting through mountains are archived PV data is also
painful.

The PV Logger app is designed to collect the data you want during an
experiment, and in a way that can be easily digested and investigated.
