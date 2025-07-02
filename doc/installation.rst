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

To install a full installation of Python with EpicsApps, download
`GetEpicsApps.bat`_ for Windows or `GetEpicsApps.sh`_ for Linux and
MacOS and run that script.  This will install a full Anaconda Python
environment in a folder named ``C:\Users\<YourName>\epicsapps`` or
``C:\Users\<YourName>\AppData\Local\epicsapps`` on Windows or in a
folder called ``epicsapps`` in you Home Folder on Linux or macOS, and
will also put folder called ``Epics Apps`` on your desktop with links
to the GUI Applications.


For installation into an existing Python environment, all dependencies
can be reliably installed with the `pip` command above on Windows and
macOS.

On Linux, however, PyPI does not have a binary package for wxPython
for Linux, so `pip install` may try to build wxPython from source.
This requires a large number of development packages on Linux, and
rarely works without some effort.  On the other hand, there are conda
packages for wxPython from the `conda-forge` channel.  In addition,
some system-provided Python packaging also include wxPython with its
packaging tools.

Using Anaconda Python is recommended and common for many scientific
applications, and is common at many facilities using Epics.
If using Anaconda Python, you can first do::

    conda install -c conda-forge wxpython


and then::

    pip install epicsapps


This approach will work on all systems, and is recommended on Linux.



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

* `adviewer`     [filename] Area Detector Viewer
* `instruments`  [filename] Epics Instruments
* `microscope`   [filename] Sample Microscope Viewer
* `pvlogger`     [filename] PV Logger data collection
* `pvlogview`               PV Logger data Viewer
* `stripchart`              PV Stripchart


and `filename` is an optional configuration YAML file.


.. _install_icons:

Creating Desktop Shortcuts
-----------------------------

Running::

    epicsapps -m

will create a folder called "Epics Apps" on your desktop with links to launch
the main GUI applications.
