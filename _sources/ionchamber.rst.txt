====================================
Ion Chamber
====================================

This application, like the XRF Collector, provides a simple Epics interface
control of a non-trivial device.  Again, the main point of showing it
here is as an example of using a python process to interact with a custom
Epics database to provide a customized way to acquire data.   While the
standard Epics solution would be to write a state-notation-language program
that runs in an IOC, the approach here minimizes Epics coding to writing a
simple database, and putting all the logic and control into a python script
that runs as a long-running process along-side an IOC process.    



