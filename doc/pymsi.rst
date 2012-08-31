====================================================
pymsi EPICS macro substitution and expansion tool
====================================================

The pymsi tool is a powerful alternative to the msi_ tool in
EPICS. Both tools allow you to structure your EPICS databases as
'source code' and build them into one final output database when you
compile your IOC application. The IOC can then load a single output
database when it boots.

pymi can be found under pymsi/ in the pyepics epicsapps distribution.

Advantages to using pymsi:

* Database functionality can be encapsulated in individual source
  databases, for easier comprehension.

* Reusable components can be created and reused for shorter, simpler
  descriptions of databases. Components can be nested hierarchically.

* Embedded database parser, verifies database syntax at compile time.

* dbd verification allows every field in the database to be checked against
  the database definition at compile time.

* Powerful macro expansion engine - local scopes, inline default values,
  errors on missing macros.

* Automatic dependency generator for Makefile integration.

* Detailed error messages with accurate line & column numbers for
  quick and accurate debugging.

History
-------

pymsi was originally developed by Angus Gratton at Australian National
University. It is currently used on the ANU 14UD accelerator to
process 109 very specific source databases (organised in
subdirectories by function) and produce 7 monolithic IOC databases. It
expands 638 source database records to 3363.

pymsi takes many ideas from VisualDCT_ by Cosylab, especially
VisualDCT's flatdb function.


Dependencies
-----------

* pyparsing_ python parsing module, version 1.5.6 or newer
  (can be installed via *pip install pyparsing* or *easy_install install pyparsing*)


Similarities to msi
-------------------

Some features from msi are supported verbatim:

* "substitute" and "include" directives
* Command line options to be used as an inline filter w/ stdin/stdout.

The msi "substitution file" format is not currently
supported. Instead, pymsi uses expand clauses that can be inserted
anywhere in a source database.


Workflow
--------

pymsi processes one or more "source database files", nested under a
parent source database, to produce a single EPICS database that can be
loaded by an IOC.

I suggest using file extension '.sdb' for source databases, but you can
use any extension you like.


Quick Example
-------------

The source databases used in this example can be found in the epicsapps
source under /pymsi/example/

The example generates an IOC to monitor a set of FAKECORP-1 vacuum
gauges, each outputting a single analog value to an ADC. The gauges
are all configured the same, but the alarm status cuts in at different
levels depending on the location of the gauge.

The first source database describes the vacuum gauge and its common
properties:

vacuum-fc-1.sdb::

   # A FAKECORP 1 model vacuum gauge

   record(ai, "$(section_name):vacuum") {
     field(DTYP, "asynInt32")
     field(INP, "@asyn($(port))")
     field(LINR, "LINEAR")
     field(EGU, "Torr")
     field(EGUL, "0")
     field(EGUF, "1")
     field(PREC, "8")
     field(HIGH, "$(warning_level)")
     field(HSV, "MAJOR")
   }

Then there is a source database describing all of the vacuum gauges controlled by the IOC:

top-section-gauges.sdb::

   expand("vacuum-fc-1.sdb") {
     macro(section_name, "section1")
     macro(port, "adcA 0")
     macro(warning_level, "0.00001")
   }

   expand("vacuum-fc-1.sdb") {
     macro(section_name, "section2")
     macro(port, "adcA 1")
     macro(warning_level, "0.000001")
   }

   expand("vacuum-fc-1.sdb") {
     macro(section_name, "midsection")
     macro(port, "adcB 3")
     macro(warning_level, "0.0000001")
   }

Finally, there is a "master" top-level source database for the IOC.
This references the major functions in that IOC (just one in this
example, probably more in practice!):

myioc.sdb::

  # IOC located near the top section of the device
  # supports vacuum monitoring, valve control, heating functions.

  expand("top-section-gauges.sdb")


To expand myioc.sdb into an output database myioc.db, run pymsi.py::

  pymsi.py -s -o myioc.db myioc.sdb

The '-s' option to pymsi instructs it to strip comments from the
source databases, producing a thinner output database. pymsi still inserts
comments describing the structure of the original source databases:

Generated output database myioc.db::

  # >>> expand "./top-section-gauges.sdb" at myioc.sdb:4
  # >>> expand "./vacuum-fc-1.sdb" at ./top-section-gauges.sdb:1

  record(ai, section1:vacuum) {
    field(DTYP, "asynInt32")
    field(INP, "@asyn(adcA 0)")
    field(LINR, "LINEAR")
    field(EGU, "Torr")
    field(EGUL, "0")
    field(EGUF, "1")
    field(PREC, "8")
    field(HIGH, "0.00001")
    field(HSV, "MAJOR")
  }

  # <<<< end expand "./vacuum-fc-1.sdb" at ./top-section-gauges.sdb:2
  # >>> expand "./vacuum-fc-1.sdb" at ./top-section-gauges.sdb:7

  record(ai, section2:vacuum) {
    field(DTYP, "asynInt32")
    field(INP, "@asyn(adcA 1)")
    field(LINR, "LINEAR")
    field(EGU, "Torr")
    field(EGUL, "0")
    field(EGUF, "1")
    field(PREC, "8")
    field(HIGH, "0.000001")
    field(HSV, "MAJOR")
  }

  # <<<< end expand "./vacuum-fc-1.sdb" at ./top-section-gauges.sdb:8
  # >>> expand "./vacuum-fc-1.sdb" at ./top-section-gauges.sdb:13

  record(ai, midsection:vacuum) {
    field(DTYP, "asynInt32")
    field(INP, "@asyn(adcB 3)")
    field(LINR, "LINEAR")
    field(EGU, "Torr")
    field(EGUL, "0")
    field(EGUF, "1")
    field(PREC, "8")
    field(HIGH, "0.0000001")
    field(HSV, "MAJOR")
  }

  # <<<< end expand "./vacuum-fc-1.sdb" at ./top-section-gauges.sdb:14
  # <<<< end expand "./top-section-gauges.sdb" at myioc.sdb:5

At this point, pymsi has also confirmed this is a valid EPICS database.

If you also want to confirm that all fields conform to the database
definition used by the IOC, you can run pymsi with the --dbd argument::

  pymsi.py --dbd /path/to/my.dbd -s -o myioc.db myioc.sdb


Source Database Options
-----------------------

As well as plain EPICS database syntax, source databases can contain the following various clauses:

**expand**::

  expand(<sourcefile>) [ {
    macro(macroname, macrovalue)
    ...
    } ]

Recursively expands a source database as a child of this one. Any
specified macros are defined in the child database, but not in the
parent database.

The following are all valid clauses for expansion::

   expand("cheese.sdb") {
     macro(name, "gorganzola")
   }

   expand("cheese.sdb") {
     macro(name, "gorgonzola")
     macro(odour_level, "9")
   }

  expand("delicious-cheeses.sdb")

Because the expanded "child" database is considered a nested scope,
any macros which are set inside that database will not be propagated
back up into the parent database.


**substitute clauses**::

  substitute "name=value,name2=value2"

These clauses immediately substitute the given macro names for the
given macro values. The values are set in the current database, and
any child databases which are expanded are included from this one.


**include clauses**::

  include "sourcedatabasefile"

This clause immediately includes the contents of the specified source
database. Unlike the expand clause, this is not considered a "child"
database with a separate scope - if macros are set in the included
database, they are also set in the parent database.


**macro values**::

  $(macro_name [ |default_value ])

Macros can be expanded anywhere that databases expect a field name,
record name or a macro value. $(macro_name) will be replaced with the
current value of the macro.

If a macro doesn't exist, pymsi reports an error. This behaviour can
be overriden with the "-m" pymsi command line flag to ignore missing
macros optional. This is the opposite to msi, which allows missing
macros by default.

Optionally, you can specify a default value for a macro by including a
pipe character (|) followed by the default value to use if the macro
is not defined. The default value itself can expand a macro.

This contrived example shows several possibilities for macro expansion::

  # analog readback
  #
  # use 'name' macro to set name
  # Optionally set macro 'prec' to precision, default is 3.
  #
  # Operator range:
  # 3 alternatives:
  # * Set macros 'low' and 'high' and the range becomes $(low) to $(high).
  # * Set the macro 'limit' and the range becomes -$(limit) to +$(limit).
  # * Set only the macro 'high' and the range becomes 0 - $(high)
  record(ai, $(name)) {
    field(PREC, "$(prec|3)")
    field(LOPR, "$(low|-$(limit|0))")
    field(HOPR, "$(high|$(limit))")
  }


Integration with EPICS Build System
-----------------------------------

pymsi can be easily integrated into an existing EPICS App database build system. Add rules like this to your TOP/configure/RULES file::

  $(COMMON_DIR)/%.db: $(COMMON_DIR)/../%.sdb $(INSTALL_DBD)
  	pymsi.py --dbd $(INSTALL_DBD)/mydbdfile.dbd --dbd-cache dbd.cache -MF $(@:.db=.d) -s -I $(COMMON_DIR)/.. -o $@ $<

  include $(wildcard $(COMMON_DIR)/*.d)

This rule assumes that for any output mydb.db file, there is a source file mydb.sdb. For example, if you create myApp/Db/mydb.sdb you also edit myApp/Db/Makefile with::

  DB += mydb.db

So that mydb.sdb gets expanded to create output database mydb.db

 also assumes pymsi.py is on the PATH. Otherwise you can specify a PYMSI variable with the full path, and use it here.

The additional options given in the RULES are::

  --dbd $(INSTALL_DBD)/mydbdfile.dbd --dbd-cache dbd.cache

You'll need to edit "mydbdfile.dbd" to the name of your dbd file. This
causes database output to be automatically verified against the dbd
file. The --dbd-cache option speeds up generation by only parsing the
dbd file when it changes, the cache used to support this is created in
the O.Common directory and automatically removed during 'make clean'.

::

  -MF $(@:.db=.d)

with
::

  include $(wildcard $(COMMON_DIR)/*.d)

pymsi will produce a Make-compatible mydb.d file giving the source
database files that are dependencies for the output database. This
means the output database will be automatically regenerated if any of
the source files change, but not otherwise.

::

  -s

Strips comments from the output database file.

  .. _msi: http://www.aps.anl.gov/epics/extensions/msi/index.php
  .. _VisualDCT: http://www.slac.stanford.edu/grp/cd/soft/epics/extensions/vdct/doc/MAN-VisualDCT_Users_Manual.html#flatdb
  .. _pyparsing: http://pyparsing.wikispaces.com/
