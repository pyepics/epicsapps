This folder contains example configuration files for

AreaDetector Viewer:
   three example yaml files are included.

Instruments:
   an empty sqlite database is included.

Microscope:
   one example yaml file is included.

## Using Epics_SCAN

Some of these applications make use of an ESCAN postgresql database,
as also used by the EpicsScan data collection software.

By default, the environmental variable ESCAN_CREDENTIALS is used to point to
the (yaml formatted) file that defines how to connect to the ESCAN postgresql
database.

   epics_scan/escan_credentials.dat
   epics_scan/escan_pgschema.sql
