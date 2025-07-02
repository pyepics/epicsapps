.. _GetEpicsApps.sh:   https://raw.githubusercontent.com/pyepics/epicsapps/master/installers/GetEpicsApps.sh
.. _GetEpicsApps.bat:   https://raw.githubusercontent.com/pyepics/epicsapps/master/installers/GetEpicsApps.bat


Installation and Getting Started
====================================


Installing Epics Apps
---------------------------

The latest version of the `epicsapps` package is |release|. For
existing Python installations, this can be installed with::

     pip install epicsapps

or upgraded with::

     pip install --upgrade epicsapps


For installation into an existing Python environment,

This ``pip`` command will all the required packages needed on Windows
and macOS.

On Linux, however, the ``pip install`` command will not have a binary
package for wxPython, and may try to build wxPython from source.  This
requires a large number of development packages on Linux, and rarely
works without some effort.

There are conda packages for wxPython from the `conda-forge` channel.
Since using Anaconda Python provides many othed common scientific
pacakges, and is common at many facilities using Epics.  If using
Anaconda Python, you can first do::

    conda install -c conda-forge wxpython

and then::

    pip install epicsapps

This approach will work on all systems, and is recommended on Linux.

Installation Scripts
---------------------------


**Table of EpicsApps Install scripts**

  +---------------------+------------------------+
  | Operating System    | Installer Script       |
  +=====================+========================+
  | Windows             | `GetEpicsApps.bat`_    |
  +---------------------+------------------------+
  | macOS or Linux      | `GetEpicsApps.sh`_     |
  +---------------------+------------------------+


To install a full standalone installation of Python with EpicsApps,
download `GetEpicsApps.bat`_ for Windows or `GetEpicsApps.sh`_ for
Linux and MacOS and run that script.  This will install a full
Anaconda Python environment in a folder named
``C:\Users\<YourName>\epicsapps`` or
``C:\Users\<YourName>\AppData\Local\epicsapps`` on Windows or in a
folder called ``epicsapps`` in you Home Folder on Linux or macOS, and
will also put folder called ``Epics Apps`` on your desktop with links
to the GUI Applications.


Getting Started
------------------------

Installing the epicsapps package will install a command-line script `epicsapps`
that can be used to launch the main epicsapps GUI applications.  This works
as::

   epicsapps [options] appname  [filename]


where `options` can be

* `-h`, `--help`:      show this help message and exit
* `-m`, `--makeicons`  create desktop and start menu icons
* `-p`, `--prompt`     prompt for configuration on startup
* `-n`, `--no-prompt`  suppress prompt, use default configuration
* `-c`, `--cli`        run as a command-line program.

and `appname` can be one of

* `stripchart`              PV Stripchart
* `adviewer`     [filename] Area Detector Viewer
* `instruments`  [filename] Epics Instruments
* `pvlogger`     [filename] PV Logger data collection
* `pvlogview`               PV Logger data Viewer
* `microscope`   [filename] Sample Microscope Viewer


and `filename` is an optional configuration YAML file.


.. _install_icons:

Creating Desktop Shortcuts
-----------------------------

Running::

    epicsapps -m

will create a folder called "Epics Apps" on your desktop with links to launch
the main GUI applications.
